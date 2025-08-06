import dearpygui.dearpygui as dpg
from shared_states import (buttons_trials, buttons_lickports2, buttons_lickports1, remembered_relays, active_theme, ser1, ser2, 
                           label_table, temp_mouse_data, temp_protocol_data, trial_labels, timestamps, current_mouse_file, current_mouse_data,
                           current_session_name, camera_image_tag, camera_initialized, camera_texture_tag, CAMERA_HEIGHT, CAMERA_WIDTH,
                           current_session_path)
import shared_states
import ctypes
import os
import json
import time
import serial
import csv
import numpy as np
import cv2




### serial connection functions

def initialize_serial_connections():
    global ser1, ser2
    try:
        time.sleep(2)
        print("Serial connections established.")
    except serial.SerialException as e:
        print(f"Serial connection failed: {e}")
        ser1 = None
        ser2 = None

def clean_serial_line(line):
    try:
        return line.strip()
    except Exception:
        return ""  # Or str(line).strip()
    
def parse_sensor_line(line):
    """
    Parses: 'ts:12345 cs:400,1200,...'
    Returns (timestamp, [sensor_values])
    """
    try:
        parts = line.strip().split()
        ts = int(parts[0].split(":")[1])
        values = list(map(int, parts[1].split(":")[1].split(",")))
        return ts, values
    except Exception as e:
        print(f"[Parse error]: {e} | Line: {line}")
        return None, []

def send_serial_command(serial_obj, command):
    if serial_obj is None:
        print(f"[WARNING] Tried to send '{command}' to '{serial_obj.port}' but serial connection is not available.")
        return
    try:
        serial_obj.write(command.encode('utf-8'))
        #print(f"[INFO] Sent command: {command} to '{serial_obj.port}'")
    except Exception as e:
        print(f"[ERROR] Failed to send command to '{serial_obj.port}': {e}")

### Buttons that trigger serial connection

def set_trial_phase(button_label, ser1, ser2, active_theme):
    """Send trial phase command and reactivate remembered relays and UI."""

    if button_label == 'Reward-Phase':
        send_serial_command(ser1, 'r')
        send_serial_command(ser2, 'r')

        # Re-activate previously selected relays
        for port, tag in remembered_relays.items():
            if tag:
                # Extract button number from tag
                relay_number = int(tag.split("_")[1])

                # Re-send appropriate serial command
                if 1 <= relay_number <= 8:
                    send_serial_command(ser1, f"{relay_number}")
                elif 9 <= relay_number <= 16:
                    send_serial_command(ser2, f"{relay_number - 8}")

                # Visually reactivate the button
                if port == "1":
                    dpg.set_value(tag, True)
                    dpg.bind_item_theme(tag, active_theme)
                    buttons_lickports1[tag]["checked"] = True
                elif port == "2":
                    dpg.set_value(tag, True)
                    dpg.bind_item_theme(tag, active_theme)
                    buttons_lickports2[tag]["checked"] = True

    elif button_label == 'Intertrial-Phase':
        send_serial_command(ser1, 'i')
        send_serial_command(ser2, 'i')

        # Clear visuals but keep memory
        for d in [buttons_lickports1, buttons_lickports2]:
            for tag in d:
                dpg.set_value(tag, False)
                dpg.bind_item_theme(tag, None)
                d[tag]["checked"] = False

def toggle_trial_button(sender, button_dict, active_theme, ser1, ser2):
    label = dpg.get_item_label(sender)
    set_trial_phase(label, ser1, ser2, active_theme)

    for tag, info in button_dict.items():
        if tag != sender:
            info["checked"] = False
            dpg.set_value(tag, False)
            dpg.bind_item_theme(tag, None)
        else:
            info["checked"] = True
            dpg.bind_item_theme(tag, active_theme)
            if not dpg.get_value(tag):
                dpg.set_value(tag, True)

def toggle_lickport_button(sender, button_dict, port_label, active_theme):
    global current_mouse_data, current_mouse_file

    gui_relay_number = int(sender.split("_")[1])
    other_dict = buttons_lickports2 if button_dict is buttons_lickports1 else buttons_lickports1
    other_port = "2" if port_label == "1" else "1"
    conflicting_tag = f"button{other_port}_{gui_relay_number}"

    if other_dict.get(conflicting_tag, {}).get("checked"):
        print(f"[BLOCKED] Relay {gui_relay_number} is already active in the other group.")
        return

    for tag, info in button_dict.items():
        if tag != sender:
            info["checked"] = False
            dpg.set_value(tag, False)
            dpg.bind_item_theme(tag, None)
        else:
            info["checked"] = True
            dpg.set_value(tag, True)
            dpg.bind_item_theme(tag, active_theme)
            remembered_relays[port_label] = tag

            # Send command to Arduino
            if gui_relay_number <= 8:
                send_serial_command(ser1, f"{gui_relay_number}")
            else:
                send_serial_command(ser2, f"{gui_relay_number - 8}")

            # Append relay state with timestamp to current_mouse_data
            if current_mouse_data and current_mouse_file:
                relay_sessions = current_mouse_data.setdefault("relay_sessions", {})
                timestamp = timestamps[0][-1] if timestamps[0] else time.strftime("%Y-%m-%d %H:%M:%S")
                entry = [remembered_relays.get('1'), remembered_relays.get('2'), timestamp]
                relay_sessions.setdefault(current_session_name, []).append(entry)
                # Save back to disk
                with open(current_mouse_file, "w") as f:
                    json.dump(current_mouse_data, f, indent=4)

                print(f"Relay state saved: {entry}")

# Camera stuff

def get_camera_frame():
    # Return a dummy black frame if real camera is not available
    return np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)

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

def update_camera_feed():
    black_frame = get_camera_frame()
    black_frame = cv2.cvtColor(black_frame, cv2.COLOR_BGR2RGBA)
    black_frame = np.flip(black_frame, 0) / 255.0
    dpg.set_value(camera_texture_tag, black_frame)

def render_callback(sender, data):
    update_camera_feed()  # Update live feed image every frame

### GUI functions
def shift_data_window(data_list, max_length):
    """Keep the data list within the maximum number of elements."""
    if len(data_list) > max_length:
        del data_list[0]

def update_plot_series(tag, x_data, y_data):
    """Update a plot series with new x and y data."""
    dpg.set_value(tag, [x_data, y_data])

def setup_fonts():
    with dpg.font_registry():
        default_font = dpg.add_font("Dependencies/lemon_milk/LEMONMILK-Regular.otf", 18)
    dpg.bind_font(default_font)

def setup_button_theme():
    """Create and return a theme for clicked buttons."""
    with dpg.theme() as theme:
        with dpg.theme_component():
            dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 100, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (115, 160, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 190, 255))
    return theme

def get_screen_dimensions():
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

def check_ready_state():
    mouse_file = dpg.get_value("mouse_file_path")
    protocol_file = dpg.get_value("protocol_file_path")
    ready = mouse_file.endswith(".json") and protocol_file.endswith(".json")
    dpg.configure_item("start_experiment_button", show=ready)

### File Management

def create_mouse_folder_structure(mouse_id: str, base_dir: str, notes: str = ""):
    mouse_folder = os.path.join(base_dir, f"{mouse_id}")
    os.makedirs(mouse_folder, exist_ok=True)

    # Create session1 subfolder and nested folders
    session_name = "session1"
    session_folder = os.path.join(mouse_folder, session_name)
    os.makedirs(session_folder, exist_ok=True)
    global current_session_path
    current_session_path = session_folder
    os.makedirs(os.path.join(session_folder, "frames"), exist_ok=True)

    # Create empty CSV files
    sensor_csv = os.path.join(session_folder, "sensor_data.csv")
    pose_csv = os.path.join(session_folder, "pose_estimation.csv")

    with open(sensor_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "sensor1", "sensor2", "..."])  # adjust columns later

    with open(pose_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "x1", "y1", "likelihood1", "..."])  # adjust for DLC output

    # Return paths for use
    return {
        "mouse_folder": mouse_folder,
        "session_name": session_name,
        "session_folder": session_folder,
        "json_path": os.path.join(mouse_folder, f"{mouse_id}.json")
    }

def setup_session_folder(mouse_folder_path, session_name):
    """
    Ensures the session folder exists under the given mouse folder path.
    Returns the path to the session folder.
    """
    session_folder = os.path.join(mouse_folder_path, session_name)
    global current_session_path
    current_session_path = session_folder
    os.makedirs(session_folder, exist_ok=True)
    os.makedirs(os.path.join(session_folder, "frames"), exist_ok=True)

    # Create empty CSV files
    sensor_csv = os.path.join(session_folder, "sensor_data.csv")
    pose_csv = os.path.join(session_folder, "pose_estimation.csv")

    with open(sensor_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "sensor1", "sensor2", "..."])  # adjust columns later

    with open(pose_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "x1", "y1", "likelihood1", "..."])  # adjust for DLC output
    print(f"[SESSION FOLDER CREATED]: {session_folder}")
    return session_folder

def mouse_file_selected(sender, app_data):
        global current_mouse_file, current_mouse_data

        mouse_file = app_data['file_path_name']
        current_mouse_file = mouse_file
        global mouse_folder_path
        mouse_folder_path = os.path.dirname(os.path.abspath(mouse_file))
        if mouse_file.endswith(".json"):
            dpg.set_value("mouse_file_path", mouse_file)

        # Load the JSON content
            with open(mouse_file, "r") as f:
                global current_mouse_data
                current_mouse_data = json.load(f)
            dpg.configure_item("session_prompt_popup", show=True)
            relay_sessions = current_mouse_data.get("relay_sessions", {})
            if relay_sessions:
                last_session = sorted(relay_sessions.keys(), key=lambda x: int(x.replace("session", "")))[-1]
                last_relays = relay_sessions[last_session]

                # Parse and assign to remembered_relays
                remembered_relays["1"] = last_relays[-1][0]
                remembered_relays["2"] = last_relays[-1][1]
            else:
                print("No relay session history found.")

        print(f"Loaded remembered_relays: {remembered_relays}")
        check_ready_state()

def finalize_mouse_file(data, path):
    global current_mouse_data, current_mouse_file, current_session_name

    # Write to disk
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Mouse file created: {path}")

    # Set globals so session logic works
    current_mouse_data = data
    current_mouse_file = path
    current_session_name = "session1"

    # Update GUI
    dpg.set_value("mouse_file_path", path)

    # Ensure overwrite popup is hidden
    dpg.configure_item("mouse_overwrite_popup", show=False)

def create_mouse_file():
    mouse_id = dpg.get_value("mouse_id_input")
    notes = dpg.get_value("mouse_notes_input")

    if not mouse_id.strip():
        print("Mouse ID cannot be empty.")
        return

    temp_mouse_data.clear()
    temp_mouse_data.update({
        "MouseID": mouse_id,
        "relay_sessions": {},
        "Notes": notes
    })

    # Prompt user for session name (optional: auto-set to session1)
    session_name = "session1"
    temp_mouse_data["relay_sessions"][session_name] = []

    # Open file dialog to choose save location
    dpg.hide_item("new_mouse_file_window")
    dpg.show_item("mouse_save_dialog")

def save_mouse_file_dialog_callback(sender, app_data):
    selected_directory = app_data['file_path_name']
    mouse_id = temp_mouse_data.get("MouseID", "unknown")
    notes = temp_mouse_data.get("Notes", "")
    
    # Create full folder structure
    paths = create_mouse_folder_structure(mouse_id, selected_directory, notes)

    # Save initial JSON
    mouse_json = {
        "MouseID": mouse_id,
        "relay_sessions": {
            paths["session_name"]: []
        },
        "Notes": notes
    }

    with open(paths["json_path"], "w") as f:
        json.dump(mouse_json, f, indent=4)

    # Update state
    global current_mouse_data, current_mouse_file, current_session_name
    current_mouse_data = mouse_json
    current_mouse_file = paths["json_path"]
    dpg.set_value("mouse_file_path", current_mouse_file)
    current_session_name = paths["session_name"]

    print(f"[INFO] Mouse file and folder created at: {paths['mouse_folder']}")

def confirm_session_number():
    global current_mouse_data, current_session_name

    session_num = dpg.get_value("session_input")
    if not session_num.strip().isdigit():
        print("Invalid session number.")
        return

    session_tag = f"session{int(session_num)}"
    current_session_name = session_tag  # Store globally

    # Ensure session exists in data
    if session_tag not in current_mouse_data["relay_sessions"]:
        current_mouse_data["relay_sessions"][session_tag] = []
        current_session_path = setup_session_folder(mouse_folder_path, current_session_name)

    print(f"Using session: {session_tag}")
    dpg.configure_item("session_prompt_popup", show=False)

def protocol_file_selected(sender, app_data):
        path = app_data['file_path_name']
        if path.endswith(".json"):
            dpg.set_value("protocol_file_path", path)
        check_ready_state()

def finalize_protocol_file(temp_protocol_data, overwrite=False):
    protocol_name = temp_protocol_data["ProtocolName"]
    filename = f"Protocol_{protocol_name}.json"
    if not overwrite and os.path.exists(filename):
        dpg.configure_item("protocol_overwrite_popup", show=True)
        return False
    with open(filename, "w") as f:
        json.dump(temp_protocol_data, f, indent=4)
    dpg.set_value("protocol_file_path", filename)
    dpg.hide_item("new_protocol_file_window")
    check_ready_state()
    return True

def create_protocol_file():
        protocol_name = dpg.get_value("protocol_name_input")
        comments = dpg.get_value("protocol_comments_input")

        if not protocol_name.strip():
            print("Protocol name cannot be empty.")
            return

        temp_protocol_data.clear()
        temp_protocol_data.update({
            "ProtocolName": protocol_name,
            "Comments": comments
        })

        filename = f"Protocol_{protocol_name}.json"
        if os.path.exists(filename):
            dpg.configure_item("protocol_overwrite_popup", show=True)
        else:
            finalize_protocol_file(temp_protocol_data)

### Data saving

def start_recording_callback():
    global current_session_path, active_theme
    try:
        if not current_session_path:
            print("[ERROR] No session path set.")
            return

        sensor_csv_path = os.path.join(current_session_path, "sensor_data.csv")
        shared_states.csv_file = open(sensor_csv_path, mode='w', newline='')
        shared_states.csv_writer = csv.writer(shared_states.csv_file)
    
        # Header: timestamp + 16 sensor values
        shared_states.csv_writer.writerow(["timestamp"] + [f"sensor_{i+1}" for i in range(16)])
    
        shared_states.is_recording = True
        print(f"[RECORDING STARTED] -> {sensor_csv_path}")
        dpg.bind_item_theme("start_recording_button", active_theme)
        dpg.bind_item_theme("stop_recording_button", None)
    except Exception as e:
        print(f"[ERROR] in start_recording_callback: {e}")
    dpg.split_frame()

def stop_recording_callback():
    shared_states.is_recording = False
    dpg.bind_item_theme("start_recording_button", None)
    dpg.bind_item_theme("stop_recording_button", active_theme)
    if shared_states.csv_file:
        shared_states.csv_file.close()
        print("[RECORDING STOPPED]")
        shared_states.csv_file = None   

### Building the GUI

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
            pos=(1200, 1200)  # try some visible position on the screen
        )
        dpg.add_button(
            label="Stop Recording",
            tag="stop_recording_button",
            callback=stop_recording_callback,
            width=150,
            pos=(1500, 1200)
        )

def show_main_window():
        dpg.hide_item("intro_window")
        dpg.show_item("main_window")

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
    with dpg.window(label="Welcome / Setup", tag="intro_window", width=welcome_width, height=welcome_height, no_close=True, no_resize=True, no_move=True):
        with dpg.group(horizontal=False):
            dpg.add_text("Welcome to the Multiport System", indent=00)
            with dpg.group(horizontal=True):
                run_button = dpg.add_button(label="Run Experiment", width=200, callback=lambda: dpg.show_item("experiment_setup_group"))
                clean_button = dpg.add_button(label="Cleaning", width=200, callback=lambda: print("Cleaning protocol..."))
                dpg.bind_item_theme(run_button, active_theme)
                dpg.bind_item_theme(clean_button, active_theme)

            with dpg.group(tag="experiment_setup_group", show=False):
                dpg.add_separator()

                dpg.add_text("Mouse File")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="mouse_file_path", readonly=True)
                    dpg.add_button(label="Browse", callback=lambda: dpg.show_item("mouse_file_dialog"))
                    dpg.add_button(label="New Folder", callback=lambda: dpg.show_item("new_mouse_file_window"))

                dpg.add_text("Protocol File")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(tag="protocol_file_path", readonly=True)
                    dpg.add_button(label="Browse", callback=lambda: dpg.show_item("protocol_file_dialog"))
                    dpg.add_button(label="New File", callback=lambda: dpg.show_item("new_protocol_file_window"))

                dpg.add_button(label="Start Experiment", tag="start_experiment_button", callback=show_main_window, show=False)

    dpg.set_item_pos("intro_window", [(screen_width - welcome_width) // 2, (screen_height - welcome_height) // 2])

    with dpg.file_dialog(directory_selector=False, show=False, callback=mouse_file_selected, tag="mouse_file_dialog", width=700, height=400):
        dpg.add_file_extension(".json", color=(0, 255, 0, 255))
    


    with dpg.file_dialog(directory_selector=False, show=False, callback=protocol_file_selected, tag="protocol_file_dialog", width=700, height=400):
        dpg.add_file_extension(".json", color=(0, 255, 0, 255))

    # === New Mouse File Window ===

    with dpg.window(label="Create New Mouse File", tag="new_mouse_file_window", modal=True, show=False, width=400, height=300):
        dpg.add_text("Enter Mouse Information:")
        dpg.add_input_text(label="Mouse ID", tag="mouse_id_input")
        dpg.add_input_text(label="Notes", tag="mouse_notes_input")
        with dpg.group(horizontal=True):
            create_mouse_btn = dpg.add_button(label="Create", callback=create_mouse_file)
            dpg.add_button(label="Close", callback=lambda: dpg.hide_item("new_mouse_file_window"))

    with dpg.file_dialog(directory_selector=True, show=False, callback=save_mouse_file_dialog_callback, tag="mouse_save_dialog", width=700, height=400):
        dpg.add_file_extension(".json", color=(0, 255, 0, 255))

    # Popup attached to the create button (not the window)
    with dpg.popup(parent=create_mouse_btn, tag="mouse_overwrite_popup", modal=True):
        dpg.add_text("Mouse file already exists. Overwrite?")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Yes", callback=lambda: finalize_mouse_file(temp_mouse_data, path=temp_mouse_data["save_path"]))
            dpg.add_button(label="No", callback=lambda: dpg.configure_item("mouse_overwrite_popup", show=False))

    # === New Protocol File Window ===

    with dpg.window(label="Create New Protocol File", tag="new_protocol_file_window", modal=True, show=False, width=400, height=300):
        dpg.add_text("Enter Protocol Information:")
        dpg.add_input_text(label="Protocol Name", tag="protocol_name_input")
        dpg.add_input_int(label="Number of Trials", tag="protocol_trials_input", default_value=10)
        dpg.add_input_int(label="Reward Duration (ms)", tag="protocol_duration_input", default_value=500)
        dpg.add_input_text(label="Comments", tag="protocol_comments_input", multiline=True)
        with dpg.group(horizontal=True):
            create_protocol_btn = dpg.add_button(label="Create", callback=create_protocol_file)
            dpg.add_button(label="Close", callback=lambda: dpg.hide_item("new_protocol_file_window"))

    # Popup attached to the create protocol button
    with dpg.popup(parent=create_protocol_btn, tag="protocol_overwrite_popup", modal=True):
        dpg.add_text("Protocol file already exists. Overwrite?")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Yes", callback=lambda: finalize_protocol_file(overwrite=True))
            dpg.add_button(label="No", callback=lambda: dpg.configure_item("protocol_overwrite_popup", show=False))

    # === Session Number Prompt Popup ===
    with dpg.window(label="Enter Session Number", tag="session_prompt_popup", modal=True, show=False, width=300, height=150, no_title_bar=False):
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
            dpg.add_spacer(width=50, height = 50)
            dpg.add_text("Trial Phase", indent = 480)
            with dpg.group(horizontal=True):
                with dpg.table(width=1100, header_row=False):  # width adjustable
                    # Add two columns for two buttons
                    dpg.add_table_column()
                    dpg.add_table_column()
                    with dpg.table_row():
                        for label in trial_labels[0]:  # ["Reward-Phase", "Intertrial-Phase"]
                            tag = f"button{label}"
                            dpg.add_button(
                                label=label,
                                tag=tag,
                                width=220,
                                height=60,
                                indent = 150,
                                callback=lambda s=tag: toggle_trial_button(s, buttons_trials, active_theme, ser1, ser2)
                            )
                            buttons_trials[tag] = {"checked": False}

            # Relay buttons below, aligned left with indent
            with dpg.group(horizontal=False):
                dpg.add_spacer(width=50, height = 100)

                # Reward 1 table
                with dpg.group():
                    dpg.add_text("Reward 1", indent=500)
                    create_reward_table("button1", buttons_lickports1)

                # Reward 2 table
                with dpg.group():
                    dpg.add_text("Reward 2", indent=500)
                    create_reward_table("button2", buttons_lickports2)

            # --- Sensor plots table ---
            with dpg.group(horizontal=False):
                dpg.add_text("Sensor Plots:")

            with dpg.table(header_row=False, resizable=False, policy=dpg.mvTable_SizingFixedFit,
                           borders_innerV=True, borders_outerH=True, width=screen_width - 100):
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

            # camera 
            setup_camera_ui()

            add_recording_buttons()