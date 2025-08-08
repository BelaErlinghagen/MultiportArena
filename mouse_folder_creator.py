import os
import shared_states
import csv
import dearpygui.dearpygui as dpg
import json

from shared_states import (
    remembered_relays
)

from utils import (
    check_ready_state
)


def create_mouse_folder_structure(mouse_id: str, base_dir: str, notes: str = ""):
    mouse_folder = os.path.join(base_dir, mouse_id)
    os.makedirs(mouse_folder, exist_ok=True)
    session_name = "session1"
    session_folder = os.path.join(mouse_folder, session_name)
    os.makedirs(session_folder, exist_ok=True)
    shared_states.current_session_path = session_folder
    os.makedirs(os.path.join(session_folder, "frames"), exist_ok=True)

    sensor_csv = os.path.join(session_folder, "sensor_data.csv")
    pose_csv = os.path.join(session_folder, "pose_estimation.csv")

    with open(sensor_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "sensor1", "sensor2", "..."])

    with open(pose_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "x1", "y1", "likelihood1", "..."])

    return {
        "mouse_folder": mouse_folder,
        "session_name": session_name,
        "session_folder": session_folder,
        "json_path": os.path.join(mouse_folder, f"{mouse_id}.json")
    }

def create_mouse_file():
    mouse_id = dpg.get_value("mouse_id_input")

    if not mouse_id.strip():
        print("Mouse ID cannot be empty.")
        return
    dpg.configure_item("new_mouse_file_window", show = False)
    dpg.show_item("mouse_save_dialog")

def finalize_mouse_file(mouse_id, notes, base_dir, overwrite=False):
    mouse_folder = os.path.join(base_dir, mouse_id)

    # If folder exists and overwrite is False, trigger popup and save state, return False
    if os.path.exists(mouse_folder) and not overwrite:
        shared_states.pending_mouse_save = {
            "mouse_id": mouse_id,
            "notes": notes,
            "base_dir": base_dir
        }
        dpg.configure_item("mouse_overwrite_popup", show=True)
        return False

    # If overwrite == True or folder doesn't exist, create folder structure & JSON
    paths = create_mouse_folder_structure(mouse_id, base_dir, notes)
    mouse_json = {
        "MouseID": mouse_id,
        "relay_sessions": {
            paths["session_name"]: []
        },
        "Notes": notes
    }
    with open(paths["json_path"], "w") as f:
        json.dump(mouse_json, f, indent=4)

    global current_mouse_data, current_mouse_file, current_session_name
    current_mouse_data = mouse_json
    current_mouse_file = paths["json_path"]
    current_session_name = paths["session_name"]
    dpg.set_value("mouse_file_path", current_mouse_file)
    print(f"[INFO] Mouse file and folder created at: {paths['mouse_folder']}")
    check_ready_state()

    return True


def save_mouse_file_dialog_callback(sender, app_data):
    selected_directory = app_data['file_path_name']
    mouse_id = dpg.get_value("mouse_id_input")
    notes = dpg.get_value("mouse_notes_input")

    if not selected_directory:
        print("No directory selected.")
        return

    if not mouse_id.strip():
        print("Mouse ID cannot be empty.")
        return

    # Try to finalize mouse file creation without overwriting first
    finalize_mouse_file(mouse_id, notes, selected_directory, overwrite=False)


def confirm_mouse_overwrite():
    if hasattr(shared_states, 'pending_mouse_save'):
        data = shared_states.pending_mouse_save
        # Delete existing folder before overwrite
        import shutil
        target_folder = os.path.join(data["base_dir"], data["mouse_id"])
        if os.path.exists(target_folder):
            shutil.rmtree(target_folder)

        # Now finalize with overwrite=True to recreate folder
        finalize_mouse_file(data["mouse_id"], data["notes"], data["base_dir"], overwrite=True)

        del shared_states.pending_mouse_save
    dpg.configure_item("mouse_overwrite_popup", show=False)


def cancel_mouse_overwrite():
    if hasattr(shared_states, 'pending_mouse_save'):
        del shared_states.pending_mouse_save
    dpg.configure_item("mouse_overwrite_popup", show=False)

def setup_session_folder(mouse_folder_path, session_name):
    session_folder = os.path.join(mouse_folder_path, session_name)
    shared_states.current_session_path = session_folder
    os.makedirs(session_folder, exist_ok=True)
    os.makedirs(os.path.join(session_folder, "frames"), exist_ok=True)

    sensor_csv = os.path.join(session_folder, "sensor_data.csv")
    pose_csv = os.path.join(session_folder, "pose_estimation.csv")

    with open(sensor_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "sensor1", "sensor2", "..."])

    with open(pose_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "x1", "y1", "likelihood1", "..."])

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
        with open(mouse_file, "r") as f:
            global current_mouse_data
            current_mouse_data = json.load(f)

        dpg.configure_item("session_prompt_popup", show=True)
        relay_sessions = current_mouse_data.get("relay_sessions", {})
        if relay_sessions:
            last_session = sorted(relay_sessions.keys(), key=lambda x: int(x.replace("session", "")))[-1]
            last_relays = relay_sessions[last_session]
            remembered_relays["1"] = last_relays[-1][0]
            remembered_relays["2"] = last_relays[-1][1]
        else:
            print("No relay session history found.")

        print(f"Loaded remembered_relays: {remembered_relays}")
        check_ready_state()

def confirm_session_number():
    global current_mouse_data, current_session_name
    session_num = dpg.get_value("session_input")
    if not session_num.strip().isdigit():
        print("Invalid session number.")
        return

    session_tag = f"session{int(session_num)}"
    current_session_name = session_tag

    if session_tag not in current_mouse_data["relay_sessions"]:
        current_mouse_data["relay_sessions"][session_tag] = []
        current_session_path = setup_session_folder(mouse_folder_path, current_session_name)

    print(f"Using session: {session_tag}")
    dpg.configure_item("session_prompt_popup", show=False)
    check_ready_state()
