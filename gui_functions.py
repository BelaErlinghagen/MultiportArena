import dearpygui.dearpygui as dpg
import cv2
import numpy as np

from shared_states import (
    label_table, buttons_lickports1, buttons_lickports2, buttons_trials,
    ser1, ser2, trial_labels, camera_image_tag, camera_texture_tag,
    CAMERA_HEIGHT, CAMERA_WIDTH, camera_initialized
)

import shared_states

from utils import (
    toggle_lickport_button, shift_data_window, start_recording_callback, stop_recording_callback, get_screen_dimensions,
    setup_fonts, setup_button_theme, toggle_trial_button, set_led, send_serial_command, get_camera_frame
)

from mouse_folder_creator import (
    mouse_file_selected, save_mouse_file_dialog_callback, create_mouse_file,
    cancel_mouse_overwrite, confirm_mouse_overwrite, confirm_session_number
)

from protocol_designer import (
    show_protocol_designer, confirm_protocol_overwrite, 
    protocol_selected, cancel_protocol_overwrite
)


def create_reward_table(prefix, button_dict):
    with dpg.table(width=1100, header_row=False):
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
                        callback=(lambda s=tag, d=button_dict, p=prefix[-1]: lambda: toggle_lickport_button(s, d, p, active_theme))()
                    )
                    button_dict[tag] = {"checked": False}

def create_sensor_plot(sensor_id):
    with dpg.plot(label=f"Sensor {sensor_id+1}", tag=f"sensor_plot_{sensor_id}", height=200, width=260):
        dpg.add_plot_axis(dpg.mvXAxis, tag=f"sensor_plot_{sensor_id}_xaxis")
        dpg.add_plot_axis(dpg.mvYAxis, tag=f"sensor_plot_{sensor_id}_yaxis")
        dpg.add_line_series([], [], label=f"Sensor {sensor_id+1} data",
                            parent=f"sensor_plot_{sensor_id}_yaxis",
                            tag=f"sensor_plot_{sensor_id}_line")

def append_sensor_data(ts, values, port, sensor_mapping, timestamps, data_buffers, max_points):
    for i, val in enumerate(values):
        sensor_id = sensor_mapping[port][i]
        idx = sensor_id - 1
        timestamps[idx].append(ts)
        shift_data_window(timestamps[idx], max_points)
        data_buffers[idx].append(val)
        shift_data_window(data_buffers[idx], max_points)

def add_recording_buttons():
    with dpg.group(horizontal=True):
        dpg.add_button(
            label="Start Recording",
            tag="start_recording_button",
            callback=start_recording_callback,
            width=150,
            height=120,
            pos=(1600, 870)  # try some visible position on the screen
        )
        dpg.add_button(
            label="Stop Recording",
            tag="stop_recording_button",
            callback=stop_recording_callback,
            width=150,
            height=120,
            pos=(1800, 870)
        )

def show_main_window():
        dpg.hide_item("intro_window")
        dpg.show_item("main_window")

def setup_camera_ui():
    """Sets up the black texture and image widget"""
    global camera_initialized
    if camera_initialized:
        return

    black_frame = get_camera_frame()
    black_frame = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGBA)
    black_frame = np.flip(black_frame, 0) / 255.0  # Normalize for DPG

    # You MUST add textures inside a texture registry
    with dpg.texture_registry(show=False):
        dpg.add_static_texture(CAMERA_WIDTH, CAMERA_HEIGHT, black_frame, tag=camera_texture_tag)

    # Now place the image inside a child window or layout container
    with dpg.child_window(label="Camera Feed", width=CAMERA_WIDTH + 20, height=CAMERA_HEIGHT + 40, pos=[1100, 10]):
        dpg.add_image(camera_texture_tag, tag=camera_image_tag)

    camera_initialized = True

### Hardware Testing Panel
def create_hardware_test_panel():
    with dpg.collapsing_header(label="Hardware Test Panel", default_open=False):
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



def update_protocol_summary():
    if not hasattr(shared_states, 'current_protocol'):
        return

    protocol = shared_states.current_protocol

    if dpg.does_item_exist("protocol_summary_group"):
        dpg.delete_item("protocol_summary_group", children_only=True)
    else:
        with dpg.group(horizontal=True, parent="main_window") as summary_group:
            dpg.add_group(tag="protocol_summary_group")

    with dpg.group(parent="protocol_summary_group"):
        dpg.add_text(f"Protocol: {protocol['ProtocolName']}")
        dpg.add_text(f"Comments: {protocol.get('Comments', '')}")
        dpg.add_text(f"Experiment Type: {protocol.get('experiment_type', '')}")
        if protocol.get('experiment_type') == "Open-Field Experiment":
            dpg.add_text(f"Number of Rewards: {protocol['num_rewards']}")
            dpg.add_text(f"PWM Reward 1: {protocol['pwm_reward1']}")
            dpg.add_text(f"PWM Reward 2: {protocol['pwm_reward2']}")
            dpg.add_text(f"Light Sphere Size: {protocol['light_sphere']['size']}")
            dpg.add_text(f"Light Sphere Location Mode: {protocol['light_sphere']['location_mode']}")
            dpg.add_text(f"LED Mode: {protocol['led_configuration']['mode']}")
        dpg.add_text(f"Dwell Time Threshold: {protocol['light_sphere']['dwell_time_threshold']}")
        trial_mode = "Fixed amount of trials" if protocol['trial_settings']['mode'] == "fixed_trials" else "Fixed amount of time"
        dpg.add_text(f"Trial Mode: {trial_mode}")
        if protocol['trial_settings']['mode'] == "fixed_trials":
            dpg.add_text(f"Trial Count: {protocol['trial_settings']['trial_count']}")
        else:
            dpg.add_text(f"Session Duration: {protocol['trial_settings']['session_duration']} seconds")
        if protocol.get('experiment_type') == "Y-Maze":
            dpg.add_text(f"Y-Maze Enabled: {protocol['ymaze_settings']['enabled']}")
            dpg.add_text(f"Cue Switch Probability: {protocol['ymaze_settings']['cue_switch_probability']}")
        phase_length_mode = "Time" if protocol['phase_length_settings']['phase_length_mode'] == "time" else "Mouse position"
        dpg.add_text(f"Phase Length Mode: {phase_length_mode}")
        dpg.add_text(f"Trial Phase Length: {protocol['phase_length_settings']['trial_phase_length']}")
        dpg.add_text(f"Intertrial Phase Length: {protocol['phase_length_settings']['intertrial_phase_length']}")

    window_width = dpg.get_item_width("main_window")
    dpg.set_item_pos("protocol_summary_group", [window_width - 300, dpg.get_item_height("main_window") - 400])


def build_gui():
    global active_theme
    screen_width, screen_height = get_screen_dimensions()


    dpg.create_context()
    setup_fonts()
    dpg.create_viewport(title='Multiport', width=screen_width, height=screen_height)
    dpg.setup_dearpygui()
    dpg.set_viewport_pos([0, 0])

    active_theme = setup_button_theme()



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
                dpg.bind_item_theme(run_button, active_theme)
                dpg.bind_item_theme(clean_button, active_theme)

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
                    # UPDATED: use new protocol designer
                    dpg.add_button(label="New Protocol", callback=show_protocol_designer)

                dpg.add_button(label="Start Experiment", tag="start_experiment_button",
                               callback=show_main_window, show=False)

    dpg.set_item_pos("intro_window",
                     [(screen_width - welcome_width) // 2, (screen_height - welcome_height) // 2])

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
    with dpg.window(label="Main Window", tag="main_window", show=False,
                    no_resize=True, no_move=True,
                    width=screen_width, height=screen_height):

        with dpg.group(horizontal=False):
            dpg.add_spacer(width=50, height=50)
            dpg.add_text("Trial Phase", indent=480)
            with dpg.group(horizontal=True):
                with dpg.table(width=1100, header_row=False):
                    dpg.add_table_column()
                    dpg.add_table_column()
                    with dpg.table_row():
                        for label in trial_labels[0]:
                            tag = f"button{label}"
                            dpg.add_button(
                                label=label,
                                tag=tag,
                                width=220,
                                height=60,
                                indent=150,
                                callback=lambda s=tag: toggle_trial_button(s, buttons_trials, active_theme, ser1, ser2)
                            )
                            buttons_trials[tag] = {"checked": False}

            # Relay tables
            dpg.add_spacer(width=50, height=100)
            with dpg.group():
                dpg.add_text("Reward 1", indent=500)
                create_reward_table("button1", buttons_lickports1)

            with dpg.group():
                dpg.add_text("Reward 2", indent=500)
                create_reward_table("button2", buttons_lickports2)

            # Sensor plots
            dpg.add_text("Sensor Plots:")
            with dpg.table(header_row=False, resizable=False,
                           policy=dpg.mvTable_SizingFixedFit,
                           borders_innerV=True, borders_outerH=True,
                           width=screen_width - 100):
                cols = 4
                for _ in range(cols):
                    dpg.add_table_column()
                for i in range(0, 16, cols):
                    with dpg.table_row():
                        for j in range(cols):
                            idx = i + j
                            if idx >= 16:
                                break
                            with dpg.table_cell():
                                create_sensor_plot(idx)

            # Camera feed
            setup_camera_ui()

            # Hardware test panel
            create_hardware_test_panel()

            # Recording buttons
            add_recording_buttons()