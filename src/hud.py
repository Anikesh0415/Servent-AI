import customtkinter as ctk
import tkinter as tk
from src.event_bus import event_bus
import math


class ServentHUD(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Standard window with title bar so it can be moved/minimized
        self.title("FORGE HUD")
        self.geometry("300x180+20+20")  # Top left corner
        # self.overrideredirect(True) # Removed so it has a title bar
        # self.attributes("-topmost", True) # Removed so it doesn't block the screen
        self.configure(bg="black", fg_color="black")

        # Main Frame (Semi-transparent background for indicators)
        self.main_frame = ctk.CTkFrame(
            self, fg_color="#1e1e1e", corner_radius=10, bg_color="black"
        )
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 1. Vision Telemetry (MediaPipe Status)
        self.lbl_vision = ctk.CTkLabel(
            self.main_frame,
            text="👁 Vision:",
            font=("Helvetica", 12, "bold"),
            text_color="white",
        )
        self.lbl_vision.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.indicator_vision = ctk.CTkFrame(
            self.main_frame, width=15, height=15, corner_radius=15, fg_color="orange"
        )
        self.indicator_vision.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="w")

        # 2. Cognitive State (LLM Planner Status)
        self.lbl_cog = ctk.CTkLabel(
            self.main_frame,
            text="🧠 Planner:",
            font=("Helvetica", 12, "bold"),
            text_color="white",
        )
        self.lbl_cog.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.indicator_cog = ctk.CTkFrame(
            self.main_frame, width=15, height=15, corner_radius=15, fg_color="gray"
        )
        self.indicator_cog.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # 3. Acoustic Telemetry (Volume Level)
        self.lbl_audio = ctk.CTkLabel(
            self.main_frame,
            text="🎙 Audio:",
            font=("Helvetica", 12, "bold"),
            text_color="white",
        )
        self.lbl_audio.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="w")

        self.audio_bar = ctk.CTkProgressBar(
            self.main_frame,
            width=100,
            height=10,
            progress_color="green",
            fg_color="gray",
        )
        self.audio_bar.set(0.0)
        self.audio_bar.grid(row=2, column=1, padx=10, pady=(5, 10), sticky="w")

        # 4. Noise Gate Slider
        self.lbl_gate = ctk.CTkLabel(
            self.main_frame, text="Gate:", font=("Helvetica", 10), text_color="#aaaaaa"
        )
        self.lbl_gate.grid(row=3, column=0, padx=10, pady=2, sticky="w")

        from src.config import NOISE_GATE_THRESHOLD

        self.gate_slider = ctk.CTkSlider(
            self.main_frame,
            from_=0.01,
            to=0.5,
            width=100,
            height=10,
            command=self.on_gate_change,
        )
        self.gate_slider.set(NOISE_GATE_THRESHOLD)
        self.gate_slider.grid(row=3, column=1, padx=10, pady=2, sticky="w")

        # Action Queue / Context Label
        self.lbl_action = ctk.CTkLabel(
            self.main_frame,
            text="Status: IDLE",
            font=("Helvetica", 10),
            text_color="#aaaaaa",
            justify="left",
            wraplength=260,
        )
        self.lbl_action.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Stop Button (Kill-Switch)
        self.btn_stop = ctk.CTkButton(
            self.main_frame,
            text="STOP",
            font=("Helvetica", 12, "bold"),
            fg_color="red",
            text_color="white",
            width=60,
            height=20,
            command=self.trigger_killswitch,
        )
        self.btn_stop.grid(row=0, column=2, rowspan=2, padx=10, pady=10)

        # Event Bus Subscriptions
        event_bus.subscribe("vision_telemetry", self.update_vision)
        event_bus.subscribe("cognitive_state", self.update_cognitive)
        event_bus.subscribe("audio_telemetry", self.update_audio)
        event_bus.subscribe("ui_status", self.update_status)
        event_bus.subscribe("clutch_status", self.update_clutch)

        self.killswitch_callback = None

    def on_gate_change(self, value):
        event_bus.publish("update_noise_gate", float(value))

    def trigger_killswitch(self):
        self.update_status("🛑 TASK ABORTED!")
        if self.killswitch_callback:
            self.killswitch_callback()

    def set_killswitch_callback(self, cb):
        self.killswitch_callback = cb

    def update_vision(self, active: bool):
        color = "green" if active else "orange"
        self.indicator_vision.configure(fg_color=color)

    def update_cognitive(self, thinking: bool):
        color = "#00a2ff" if thinking else "gray"  # Blue when thinking
        self.indicator_cog.configure(fg_color=color)

    def update_audio(self, volume_level: float):
        # Normalize volume to 0.0 - 1.0 safely
        val = max(0.0, min(1.0, volume_level))
        self.audio_bar.set(val)

    def update_status(self, text: str):
        self.lbl_action.configure(text=f"Status: {text}", text_color="#aaaaaa")

    def update_clutch(self, engaged: bool):
        if engaged:
            self.lbl_action.configure(
                text="[ TRACKING PAUSED (CLUTCH) ]", text_color="yellow"
            )
        else:
            self.lbl_action.configure(text="Status: IDLE", text_color="#aaaaaa")


def launch_hud(killswitch_cb=None):
    ctk.set_appearance_mode("dark")
    app = ServentHUD()
    if killswitch_cb:
        app.set_killswitch_callback(killswitch_cb)
    app.mainloop()


if __name__ == "__main__":
    launch_hud()
