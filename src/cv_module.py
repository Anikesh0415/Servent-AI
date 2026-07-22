import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision.core import vision_task_running_mode
import urllib.request
import os
import time


class HandTracker:
    def __init__(self, max_num_hands=2):
        model_path = "hand_landmarker.task"
        if not os.path.exists(model_path):
            print("Downloading MediaPipe hand landmark model...")
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            urllib.request.urlretrieve(url, model_path)

        base_options = python.BaseOptions(model_asset_path=model_path)

        def result_callback(result, output_image, timestamp_ms):
            self.detection_result = result

        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision_task_running_mode.VisionTaskRunningMode.LIVE_STREAM,
            result_callback=result_callback,
            num_hands=max_num_hands,
            min_hand_detection_confidence=0.3,
            min_hand_presence_confidence=0.3,
            min_tracking_confidence=0.3,
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        self.detection_result = None
        self.start_time = time.time()

        # EMA Smoothing state
        self.ema_alpha = 0.3  # Smoothing factor (lower = smoother but more lag)
        self.smoothed_x = None
        self.smoothed_y = None

    def process_frame(self, img):
        """Pass frame to MediaPipe async engine."""
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_img)
        timestamp_ms = int((time.time() - self.start_time) * 1000)
        try:
            self.detector.detect_async(mp_image, timestamp_ms)
        except Exception:
            pass

    def get_position(self, frame_w, frame_h, hand_no=0):
        """Returns the smoothed coordinates of all landmarks, pinch state, and fist state."""
        lm_list = []
        is_pinching = False
        is_fist = False
        is_peace_sign = False

        if self.detection_result and self.detection_result.hand_landmarks:
            if hand_no < len(self.detection_result.hand_landmarks):
                my_hand = self.detection_result.hand_landmarks[hand_no]

                if len(my_hand) > 20:
                    # Check for pinch (Thumb tip [4] and Index tip [8] distance)
                    thumb_tip = my_hand[4]
                    index_tip = my_hand[8]
                    dist = (
                        (thumb_tip.x - index_tip.x) ** 2
                        + (thumb_tip.y - index_tip.y) ** 2
                    ) ** 0.5
                    if dist < 0.03:  # Pinch threshold
                        is_pinching = True

                    # Check for fist (All fingertips close to wrist)
                    wrist = my_hand[0]
                    middle_mcp = my_hand[9]
                    hand_size = (
                        (wrist.x - middle_mcp.x) ** 2 + (wrist.y - middle_mcp.y) ** 2
                    ) ** 0.5

                    tips = [my_hand[8], my_hand[12], my_hand[16], my_hand[20]]
                    curled_fingers = 0
                    for tip in tips:
                        dist_to_wrist = (
                            (wrist.x - tip.x) ** 2 + (wrist.y - tip.y) ** 2
                        ) ** 0.5
                        if dist_to_wrist < (
                            hand_size * 1.5
                        ):  # Threshold for curled finger
                            curled_fingers += 1

                    if curled_fingers == 4:
                        is_fist = True
                        
                    # Check for peace sign (Index and Middle extended, Ring and Pinky curled)
                    index_tip = my_hand[8]
                    middle_tip = my_hand[12]
                    ring_tip = my_hand[16]
                    pinky_tip = my_hand[20]
                    
                    index_extended = ((wrist.x - index_tip.x)**2 + (wrist.y - index_tip.y)**2)**0.5 > (hand_size * 2)
                    middle_extended = ((wrist.x - middle_tip.x)**2 + (wrist.y - middle_tip.y)**2)**0.5 > (hand_size * 2)
                    ring_curled = ((wrist.x - ring_tip.x)**2 + (wrist.y - ring_tip.y)**2)**0.5 < (hand_size * 1.5)
                    pinky_curled = ((wrist.x - pinky_tip.x)**2 + (wrist.y - pinky_tip.y)**2)**0.5 < (hand_size * 1.5)
                    
                    if index_extended and middle_extended and ring_curled and pinky_curled:
                        is_peace_sign = True

                for id, lm in enumerate(my_hand):
                    raw_x = int(lm.x * frame_w)
                    raw_y = int(lm.y * frame_h)

                    # Apply EMA smoothing to the Index Finger tip (ID 8)
                    if id == 8:
                        if self.smoothed_x is None:
                            self.smoothed_x = raw_x
                            self.smoothed_y = raw_y
                        else:
                            dx = raw_x - self.smoothed_x
                            dy = raw_y - self.smoothed_y

                            # Dynamic EMA: If moving fast/tremoring, increase smoothing (lower alpha).
                            # If moving deliberately, decrease smoothing (higher alpha).
                            tremor_magnitude = (dx**2 + dy**2) ** 0.5
                            if tremor_magnitude < 30:  # Tremor or micro-movement
                                dynamic_alpha = 0.15  # Heavy smoothing
                            else:
                                dynamic_alpha = 0.4  # Responsive movement

                            # Deadzone of 5 pixels to stop micro-jitter completely when still
                            if abs(dx) > 5 or abs(dy) > 5:
                                self.smoothed_x = int(
                                    dynamic_alpha * raw_x
                                    + (1 - dynamic_alpha) * self.smoothed_x
                                )
                                self.smoothed_y = int(
                                    dynamic_alpha * raw_y
                                    + (1 - dynamic_alpha) * self.smoothed_y
                                )

                        lm_list.append([id, self.smoothed_x, self.smoothed_y, lm.z])
                    else:
                        lm_list.append([id, raw_x, raw_y, lm.z])

        return lm_list, is_pinching, is_fist, is_peace_sign
