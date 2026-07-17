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
        model_path = 'hand_landmarker.task'
        if not os.path.exists(model_path):
            print("Downloading MediaPipe hand landmark model...")
            url = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
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
            min_tracking_confidence=0.3
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        self.detection_result = None
        self.start_time = time.time()

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
        """Returns the coordinates of all landmarks."""
        lm_list = []
        if self.detection_result and self.detection_result.hand_landmarks:
            if hand_no < len(self.detection_result.hand_landmarks):
                my_hand = self.detection_result.hand_landmarks[hand_no]
                for id, lm in enumerate(my_hand):
                    lm_list.append([id, int(lm.x * frame_w), int(lm.y * frame_h), lm.z])
        return lm_list
