import dearpygui.dearpygui as dpg
import ctypes
import json
import time
import serial
import numpy as np

import shared_states
from shared_states import (
    buttons_lickports2, buttons_lickports1, remembered_relays, ser1, ser2, timestamps
)



### Serial connection functions

def initialize_serial_connections():
    global ser1, ser2
    try:
        time.sleep(2)  # Give time for Arduinos to reset
        for ser in [ser1, ser2]:
            ready = False
            start = time.time()
            while time.time() - start < 5:
                if ser.in_waiting:
                    line = ser.readline().decode("utf-8").strip()
                    if line == "READY":
                        print(f"[INFO] {ser.port} is ready.")
                        ready = True
                        break
            if not ready:
                print(f"[ERROR] {ser.port} did not send READY signal.")
        print("[INFO] Serial connections initialized.")
    except serial.SerialException as e:
        print(f"[ERROR] Serial connection failed: {e}")
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

def set_led(serial_obj, led_number, on=True):
    """
    Controls an LED via appropriate Arduino.
    LED numbers: 1–16
    """
    try:
        if 1 <= led_number <= 8:
            target_serial = shared_states.ser1
            local_led = led_number
        elif 9 <= led_number <= 16:
            target_serial = shared_states.ser2
            local_led = led_number - 8
        else:
            print(f"[ERROR] Invalid LED number: {led_number}")
            return

        cmd = 'L' if on else 'l'
        target_serial.write(f"{cmd}{local_led}".encode())
    except Exception as e:
        print(f"[ERROR] Failed to send LED command: {e}")

def push_relay_mappings(mapping: dict):
    """
    Send reward group assignment to each Arduino
    mapping: {relay_num: reward_group}, both 1-based
    """
    for relay_num_str, reward_group in mapping.items():
        relay_num = int(relay_num_str)
        reward_group = int(reward_group)

        if not (1 <= relay_num <= 16) or reward_group not in [1, 2]:
            print(f"[WARNING] Invalid mapping: Relay {relay_num} -> Reward {reward_group}")
            continue

        if relay_num <= 8:
            serial_obj = shared_states.ser1
            relay_index = relay_num
        else:
            serial_obj = shared_states.ser2
            relay_index = relay_num - 8

        try:
            serial_obj.write(f"M{relay_index}{reward_group}".encode())
        except Exception as e:
            print(f"[ERROR] Failed to send mapping for relay {relay_num}: {e}")

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
    current_mouse_data = shared_states.current_mouse_data
    current_mouse_file = shared_states.current_mouse_file
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
                #timestamp = timestamps[0][-1] if timestamps[0] else time.strftime("%Y-%m-%d %H:%M:%S")
                #entry = [remembered_relays.get('1'), remembered_relays.get('2'), timestamp]
                entry = [remembered_relays.get('1'), remembered_relays.get('2')]
                relay_sessions.setdefault(shared_states.current_session_name, []).append(entry)
                # Save back to disk
                with open(current_mouse_file, "w") as f:
                    json.dump(current_mouse_data, f, indent=4)

                print(f"Relay state saved: {entry}")


### Camera functions 

def get_camera_frame():
    # Return a dummy black frame if real camera is not available
    return np.zeros((200, 200, 3), dtype=np.uint8)

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
        default_font = dpg.add_font("Dependencies/BerlinSans/BRLNSR.TTF", 20)
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


