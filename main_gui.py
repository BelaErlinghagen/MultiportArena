import dearpygui.dearpygui as dpg
import time
import shared_states
from gui_functions import build_gui
from utils import initialize_serial_connections
import trial_functionality

TARGET_FPS = shared_states.TARGET_FPS
FRAME_PERIOD = 1.0 / TARGET_FPS

def main_loop():
    # Process queued GUI actions if any
    while shared_states.gui_actions:
        try:
            action = shared_states.gui_actions.pop(0)
            action()
        except Exception as e:
            print(f"[GUI ACTION ERROR]: {e}")

    # Render a single DearPyGUI frame
    dpg.render_dearpygui_frame()

    # Sleep to maintain target FPS
    time.sleep(FRAME_PERIOD)

def main():
    initialize_serial_connections()
    shared_states.trial_controller = trial_functionality.TrialController()
    build_gui()
    dpg.show_viewport()
    print(f"Starting GUI loop at target {TARGET_FPS} FPS...")

    while dpg.is_dearpygui_running():
        main_loop()

    print("GUI closed. Destroying context.")
    dpg.destroy_context()

if __name__ == "__main__":
    main()
