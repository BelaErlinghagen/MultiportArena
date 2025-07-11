import dearpygui.dearpygui as dpg
from shared_states import buttons_trials, buttons_lickports2, buttons_lickports1, remembered_relays, active_theme, ser1, ser2

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

# def setup_dynamic_plots(num_sensors1, num_sensors2, parent="main_window"):

#     # Clean previous dynamic plots if needed here
#     # (optional: delete old plots to avoid duplicates)

#     total_plots = num_sensors1 + num_sensors2

#     for i in range(total_plots):
#         with dpg.plot(height=300, width=800, label=f"Sensor {i+1}", parent=parent) as plot_id:
#             dpg.add_plot_axis(dpg.mvXAxis, label="Time", tag=f"xaxis{i}", no_tick_labels=True)
#             dpg.add_plot_axis(dpg.mvYAxis, label="Amplitude", tag=f"yaxis{i}")
#             dpg.add_line_series([], [], tag=f"line{i}", parent=f"yaxis{i}")

def setup_dynamic_plots(n1, n2, parent):
    import dearpygui.dearpygui as dpg

    total = n1 + n2

    # Remove existing plot group if it exists
    if dpg.does_item_exist("sensor_plot_grid"):
        dpg.delete_item("sensor_plot_grid")

    with dpg.group(horizontal=False, parent=parent, tag="sensor_plot_grid"):
        for idx in range(total):
            plot_prefix = f"sensor_plot_{idx}"
            with dpg.child_window(width=240, height=180, autosize_x=False, autosize_y=False):
                with dpg.plot(label=f"Sensor {idx + 1}", height=-1, width=-1, tag=f"{plot_prefix}_plot"):
                    if not dpg.does_item_exist(f"{plot_prefix}_xaxis"):
                        dpg.add_plot_axis(dpg.mvXAxis, tag=f"{plot_prefix}_xaxis")
                    if not dpg.does_item_exist(f"{plot_prefix}_yaxis"):
                        with dpg.plot_axis(dpg.mvYAxis, tag=f"{plot_prefix}_yaxis"):
                            dpg.add_line_series([], [], tag=f"{plot_prefix}_line", label=f"Sensor {idx + 1}")



def shift_data_window(data_list, max_length):
    """Keep the data list within the maximum number of elements."""
    if len(data_list) > max_length:
        del data_list[0]

def update_plot_series(tag, x_data, y_data):
    """Update a plot series with new x and y data."""
    dpg.set_value(tag, [x_data, y_data])

def send_serial_command(serial_obj, command):
    if serial_obj is None:
        print(f"[WARNING] Tried to send '{command}' to '{serial_obj.port}' but serial connection is not available.")
        return
    try:
        serial_obj.write(command.encode('utf-8'))
        print(f"[INFO] Sent command: {command} to '{serial_obj.port}'")
    except Exception as e:
        print(f"[ERROR] Failed to send command to '{serial_obj.port}': {e}")

def setup_button_theme():
    """Create and return a theme for clicked buttons."""
    with dpg.theme() as theme:
        with dpg.theme_component():
            dpg.add_theme_color(dpg.mvThemeCol_Button, (50, 100, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (115, 160, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 190, 255))
    return theme

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
    """Toggle lickport relay buttons, prevent overlap between groups and send correct command."""
    gui_relay_number = int(sender.split("_")[1])

    # Determine other port and tag
    other_dict = buttons_lickports2 if button_dict is buttons_lickports1 else buttons_lickports1
    other_port = "2" if port_label == "1" else "1"
    conflicting_tag = f"button{other_port}_{gui_relay_number}"

    # Block if the same relay is active on the other group
    if other_dict.get(conflicting_tag, {}).get("checked"):
        print(f"[BLOCKED] Relay {gui_relay_number} is already active in the other group.")
        return

    # Toggle logic
    for tag, info in button_dict.items():
        if tag != sender:
            info["checked"] = False
            dpg.set_value(tag, False)
            dpg.bind_item_theme(tag, None)
        else:
            # Toggle on
            info["checked"] = True
            dpg.set_value(tag, True)
            dpg.bind_item_theme(tag, active_theme)

            # Track relay assignment
            remembered_relays[port_label] = tag

            # Compute actual relay number for Arduino
            if gui_relay_number <= 8:
                command = f"{gui_relay_number}"
                send_serial_command(ser1, command)
            elif gui_relay_number > 8:
                command = f"{gui_relay_number-8}"
                send_serial_command(ser2, command)

            
            print(remembered_relays)
