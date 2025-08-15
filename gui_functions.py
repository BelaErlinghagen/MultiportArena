import dearpygui.dearpygui as dpg
from engine import Engine
import threading

from shared_states import (
    label_table, buttons_lickports1, buttons_lickports2, buttons_trials,
    ser1, ser2, trial_labels
)

import shared_states

from utils import (
    toggle_lickport_button, shift_data_window, get_screen_dimensions,
    setup_fonts, setup_button_theme, toggle_trial_button, set_led, send_serial_command
)

from mouse_folder_creator import (
    mouse_file_selected, save_mouse_file_dialog_callback, create_mouse_file,
    cancel_mouse_overwrite, confirm_mouse_overwrite, confirm_session_number
)

from protocol_designer import (
    show_protocol_designer, confirm_protocol_overwrite, 
    protocol_selected, cancel_protocol_overwrite
)

from plot_window import start_plot_window

def start_recording_callback():
    if shared_states.engine_instance is None:
        shared_states.engine_instance = Engine(target_hz=30)
        shared_states.engine_instance.start()
        print("[GUI] Engine started")

    # Start plot thread if not running
    if shared_states.plot_thread is None or not shared_states.plot_thread.is_alive():
        # Ensure any previous stop event is cleared
        try:
            if getattr(shared_states, "plot_stop_event", None):
                shared_states.plot_stop_event.clear()
        except Exception:
            pass

        shared_states.plot_thread = threading.Thread(target=lambda: start_plot_window(update_hz=30), daemon=False)
        shared_states.plot_thread.start()
        print("[GUI] Plot thread started")
    try:
        if getattr(shared_states, "trial_controller", None):
            shared_states.trial_controller.start_session()
    except Exception as e:
        print(f"[TRIAL] Could not start TrialController: {e}")
    shared_states.is_recording = True
    print(f"[RECORDING STARTED] -> {shared_states.current_session_path}")

def stop_recording_callback():
    shared_states.is_recording = False

    if getattr(shared_states, "trial_controller", None):
        shared_states.trial_controller.stop_session()

    if shared_states.engine_instance:
        shared_states.engine_instance.stop()
        shared_states.engine_instance = None
        print("[GUI] Engine stopped")

    # Request plot window to close safely via its own thread
    if hasattr(shared_states, "plot_stop_event"):
        shared_states.plot_stop_event.set()

    # Wait for plot thread to exit
    if shared_states.plot_thread is not None:
        print("[GUI] Waiting for plot thread to exit...")
        shared_states.plot_thread.join(timeout=3)
        if shared_states.plot_thread.is_alive():
            print("[GUI] Plot thread did not exit within timeout.")
        else:
            print("[GUI] Plot thread exited cleanly.")
        shared_states.plot_thread = None
    
    



def create_reward_table(prefix, button_dict):
    screen_width, screen_height = get_screen_dimensions()
    with dpg.table(width=screen_width // 2, header_row=False):
        for _ in range(8):
            dpg.add_table_column()
        for row in label_table:
            with dpg.table_row():
                for label in row:
                    tag = f"{prefix}_{label}"
                    dpg.add_button(
                        label=str(label),
                        tag=tag,
                        width=100,
                        height=40,
                        callback=(lambda s=tag, d=button_dict, p=prefix[-1]: lambda: toggle_lickport_button(s, d, p, shared_states.active_theme))()
                    )
                    button_dict[tag] = {"checked": False}


def append_sensor_data(ts, values, port, sensor_mapping, timestamps, data_buffers, max_points):
    for i, val in enumerate(values):
        sensor_id = sensor_mapping[port][i]
        idx = sensor_id - 1
        # Store in main data arrays
        timestamps[idx].append(ts)
        shift_data_window(timestamps[idx], max_points)
        data_buffers[idx].append(val)
        shift_data_window(data_buffers[idx], max_points)
        # Also store in plot update buffer
        shared_states.plot_update_buffer[idx].append((ts, val))

def show_main_window():
    screen_width, screen_height = get_screen_dimensions()
    # Hide the welcome window
    dpg.hide_item("intro_window")
    # Show the main window
    dpg.show_item("main_window")
    # Resize the viewport to half the screen width
    dpg.set_viewport_width(screen_width // 2)
    dpg.set_viewport_height(screen_height)
    # Reposition the viewport to the left side
    dpg.set_viewport_pos([0, 0])
    # Optionally, resize the main window to fit the viewport
    dpg.set_item_width("main_window", screen_width // 2)
    dpg.set_item_height("main_window", screen_height)
    dpg.set_item_pos("main_window", [0, 0])



### Hardware Testing Panel
def create_hardware_test_panel(parent, width=250, height=500):
    dpg.push_container_stack(parent)
    dpg.add_text("=== Hardware Test Panel ===", color=(50, 200, 200))
    dpg.add_separator()

    dpg.add_text("LED Control")
    dpg.add_input_int(label="LED Number (1-16)", tag="test_led_number", min_value=1, max_value=16)
    dpg.add_button(label="LED ON", callback=lambda: set_led(None, dpg.get_value("test_led_number"), True))
    dpg.add_button(label="LED OFF", callback=lambda: set_led(None, dpg.get_value("test_led_number"), False))

    dpg.add_separator()
    dpg.add_text("Reward PWM Test")
    dpg.add_combo(label="Reward", items=["1", "2"], default_value="1", tag="test_reward_channel")
    dpg.add_input_int(label="PWM Value (0-255)", default_value=255, tag="test_pwm_value", min_value=0, max_value=255)
    dpg.add_button(label="Send PWM", callback=lambda: send_serial_command(
        ser1 if dpg.get_value("test_reward_channel") == "1" else ser2,
        f"P{dpg.get_value('test_reward_channel')}{chr(dpg.get_value('test_pwm_value'))}"
    ))

    dpg.add_separator()
    dpg.add_text("Light Sphere Test")
    dpg.add_input_float(label="Size", tag="test_sphere_size", default_value=40.0)
    dpg.add_combo(label="Location Mode", items=["random", "fixed"], default_value="random", tag="test_sphere_mode")
    dpg.add_button(label="Send Sphere Settings", callback=lambda: print("Sphere settings sent (implement serial cmd)"))

    dpg.add_separator()
    dpg.add_text("Digital/Analog Output Test")
    dpg.add_combo(label="Output Type", items=["session_start", "intertrial_phase", "light_sphere_dwell", "reward_phase", "reward_port_licks"], tag="test_output_type")
    dpg.add_input_int(label="Frequency", tag="test_output_freq", default_value=0)
    dpg.add_button(label="Send Output Command", callback=lambda: print("Output command sent (implement serial cmd)"))
    dpg.pop_container_stack()


def update_protocol_summary(container_tag=None):
    protocol = getattr(shared_states, "current_protocol", None)

    if not protocol:
        summary = "No protocol loaded."
    else:
        lines = []
        lines.append(f"Protocol: {protocol.get('protocol_name', 'Unnamed')}")
        lines.append(f"Experiment: {protocol.get('experiment_type', 'Unknown')}")
        lines.append("")

        mode = protocol.get("trial_settings", {}).get("mode", "fixed_trials")
        lines.append("Trial settings:")
        if mode == "fixed_trials":
            lines.append(f"Mode: fixed_trials, count={protocol['trial_settings'].get('trial_count', 0)}")
        else:
            lines.append(f"Mode: fixed_time, duration={protocol['trial_settings'].get('session_duration', 0)} s")
        lines.append("")

        lines.append("Phase lengths:")
        pl = protocol.get("phase_length_settings", {})
        lines.append(f"Mode: {pl.get('phase_length_mode', 'time')}")
        lines.append(f"Trial phase: {pl.get('trial_phase_length', 0)} s")
        lines.append(f"Intertrial phase: {pl.get('intertrial_phase_length', 0)} s")
        lines.append("")

        num_rewards = protocol.get("num_rewards", 0)
        lines.append(f"Rewards: {num_rewards}")
        lines.append(f"Reward 1: PWM={protocol.get('pwm_reward1', 255)}, "
                    f"Probability={protocol.get('reward1_probability', 1.0):.2f}")

        if num_rewards == 2:
            lines.append(f"Reward 2: PWM={protocol.get('pwm_reward2', 255)}, "
                        f"Probability={protocol.get('reward2_probability', 1.0):.2f}")

        lines.append("")

        lines.append("LED configuration:")
        lines.append(f"Mode: {protocol.get('led_configuration', {}).get('mode', 'single')}")
        lines.append("")

        ls = protocol.get("light_sphere", {})
        lines.append("Light sphere:")
        lines.append(f"Size: {ls.get('size', 'n/a')}")
        lines.append(f"Location: {ls.get('location_mode', 'n/a')}")
        lines.append(f"Dwell threshold: {ls.get('dwell_time_threshold', 'n/a')} s")
        lines.append("")

        ym = protocol.get("ymaze_settings", {})
        lines.append("Y-Maze:")
        lines.append(f"Enabled: {ym.get('enabled', False)}")
        if ym.get("enabled", False):
            lines.append(f"Cue switch probability: {ym.get('cue_switch_probability', 0.5)}")
        lines.append("")

        dao = protocol.get("digital_analog_outputs", {})
        lines.append("Digital/Analog output triggers:")
        for evt, cfg in dao.items():
            lines.append(f"{evt}: enabled={cfg.get('enabled', False)}, freq={cfg.get('frequency', 0)}")

        summary = "\n".join(lines)

    if container_tag:
        dpg.delete_item(container_tag, children_only=True)
        dpg.add_text(summary, parent=container_tag)
    else:
        return summary


def build_gui():
    screen_width, screen_height = get_screen_dimensions()
    dpg.create_context()
    setup_fonts()
    dpg.create_viewport(title='Multiport', width=screen_width, height=screen_height)
    dpg.setup_dearpygui()
    dpg.set_viewport_pos([0, 0])
    shared_states.active_theme = setup_button_theme()

    # === Welcome Window ===
    welcome_width = 600
    welcome_height = 400
    with dpg.window(label="Welcome / Setup", tag="intro_window",
                    width=welcome_width, height=welcome_height,
                    no_close=True, no_resize=True, no_move=True):
        with dpg.group(horizontal=False):
            dpg.add_text("Welcome to the Multiport System", indent=0)
            with dpg.group(horizontal=True):
                run_button = dpg.add_button(label="Run Experiment", width=200,
                                            callback=lambda: dpg.show_item("experiment_setup_group"))
                clean_button = dpg.add_button(label="Cleaning", width=200,
                                              callback=lambda: print("Cleaning protocol..."))
                dpg.bind_item_theme(run_button, shared_states.active_theme)
                dpg.bind_item_theme(clean_button, shared_states.active_theme)
            with dpg.group(tag="experiment_setup_group", show=False):
                dpg.add_separator()
                # Mouse File section
                dpg.add_text("Mouse File")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="mouse_file_path", readonly=True)
                    dpg.add_button(label="Browse", callback=lambda: dpg.show_item("mouse_file_dialog"))
                    dpg.add_button(label="New Folder", callback=lambda: dpg.show_item("new_mouse_file_window"))
                # Protocol File section
                dpg.add_text("Protocol File")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="protocol_file_path", readonly=True)
                    dpg.add_button(label="Browse", callback=lambda: dpg.show_item("protocol_file_dialog"))
                    dpg.add_button(label="New Protocol", callback=show_protocol_designer)
                dpg.add_button(label="Start Experiment", tag="start_experiment_button",
                               callback=show_main_window, show=False)

    dpg.set_item_pos("intro_window", [(screen_width - welcome_width) // 2, (screen_height - welcome_height) // 2])

    # File dialogs
    with dpg.file_dialog(directory_selector=False, show=False, callback=mouse_file_selected,
                         tag="mouse_file_dialog", width=700, height=400):
        dpg.add_file_extension(".json", color=(0, 255, 0, 255))

    with dpg.file_dialog(directory_selector=False, show=False, callback=protocol_selected,
                         tag="protocol_file_dialog", width=700, height=400):
        dpg.add_file_extension(".json", color=(0, 255, 0, 255))

    # === New Mouse File Window ===
    with dpg.window(label="Create New Mouse File", tag="new_mouse_file_window",
                    modal=True, show=False, width=400, height=300):
        dpg.add_text("Enter Mouse Information:")
        dpg.add_input_text(label="Mouse ID", tag="mouse_id_input")
        dpg.add_input_text(label="Notes", tag="mouse_notes_input")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Create", callback=create_mouse_file)
            dpg.add_button(label="Close", callback=lambda: dpg.hide_item("new_mouse_file_window"))

    with dpg.file_dialog(directory_selector=True, show=False, callback=save_mouse_file_dialog_callback,
                         tag="mouse_save_dialog", width=700, height=400):
        dpg.add_file_extension(".json", color=(0, 255, 0, 255))

    # Mouse overwrite popup
    with dpg.window(modal=True, show=False, tag="mouse_overwrite_popup", label="Overwrite Mouse Folder?"):
        dpg.add_text("A mouse folder with this name already exists. Overwrite?")
        dpg.add_button(label="Yes", callback=confirm_mouse_overwrite)
        dpg.add_button(label="No", callback=cancel_mouse_overwrite)

    # Protocol overwrite popup
    with dpg.window(modal=True, show=False, tag="protocol_overwrite_popup", label="Overwrite Protocol?"):
        dpg.add_text("A protocol with this name already exists. Overwrite?")
        dpg.add_button(label="Yes", callback=confirm_protocol_overwrite)
        dpg.add_button(label="No", callback=cancel_protocol_overwrite)

    # === Session Number Prompt Popup ===
    with dpg.window(label="Enter Session Number", tag="session_prompt_popup",
                    modal=True, show=False, width=300, height=150, no_title_bar=False):
        dpg.add_text("What session is this?")
        dpg.add_input_text(label="Session Number", tag="session_input")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Confirm", callback=confirm_session_number)
            dpg.add_button(label="Cancel", callback=lambda: dpg.configure_item("session_prompt_popup", show=False))

    # === Main Window Layout ===
    with dpg.window(label="Main Window", tag="main_window", show=False, no_resize=True, no_move=True):
        trial_button_width = 220
        trial_button_spacing = 20
        num_trial_buttons = 2  # Adjust based on your actual number of buttons

        # Calculate total width of all trial buttons + spacing
        total_trial_buttons_width = num_trial_buttons * trial_button_width + (num_trial_buttons - 1) * trial_button_spacing
        # Calculate the left indent to center the group
        left_indent = (screen_width // 2 - total_trial_buttons_width) // 2
        with dpg.group(horizontal=False):
            # Trial Phase (centered)
            dpg.add_spacer(height=50)
            dpg.add_text("Trial Phase", indent=(screen_width // 4))  # Adjust indent as needed
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=left_indent)
                for label in trial_labels[0]:
                    tag = f"button{label}"
                    dpg.add_button(
                        label=label,
                        tag=tag,
                        width=trial_button_width,
                        height=60,
                        callback=lambda s=tag: toggle_trial_button(
                            s, buttons_trials, shared_states.active_theme, ser1, ser2
                        )
                    )
                    buttons_trials[tag] = {"checked": False}
                    if label != trial_labels[0][-1]:
                        dpg.add_spacer(width=trial_button_spacing)
                dpg.add_spacer(width=left_indent)

            # Reward Tables (centered)
            dpg.add_spacer(height=100)
            with dpg.group():
                dpg.add_text("Reward 1", indent=(screen_width // 4))  # Adjust indent as needed
                create_reward_table("button1", buttons_lickports1)
            with dpg.group():
                dpg.add_text("Reward 2", indent=(screen_width // 4))  # Adjust indent as needed
                create_reward_table("button2", buttons_lickports2)

            # Start/Stop Recording Buttons (centered)
            rec_button_width = 200
            rec_button_spacing = 50

            # Calculate total width of both buttons + spacing
            total_rec_buttons_width = 2 * rec_button_width + rec_button_spacing
            # Calculate the left indent to center the group
            left_indent_rec = (screen_width // 2 - total_rec_buttons_width) // 2
            dpg.add_spacer(height=50)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=left_indent_rec)
                dpg.add_button(
                    label="Start Recording",
                    tag="start_recording_button",
                    callback=start_recording_callback,
                    width=rec_button_width,
                    height=70
                )
                dpg.add_spacer(width=rec_button_spacing)
                dpg.add_button(
                    label="Stop Recording",
                    tag="stop_recording_button",
                    callback=stop_recording_callback,
                    width=rec_button_width,
                    height=70
                )
                dpg.add_spacer(width=left_indent_rec)

            # Protocol summary + hardware panel (centered)
            dpg.add_spacer(height=50)
            child_width = screen_width // 4
            with dpg.group(horizontal=True):
                with dpg.child_window(width=child_width, height=700):
                    create_hardware_test_panel(dpg.last_container())
                with dpg.child_window(width=child_width, height=700, tag="protocol_summary_child_window"):
                    update_protocol_summary("protocol_summary_child_window")
