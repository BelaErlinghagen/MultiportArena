# main_gui.py
print("Starting script...")

import dearpygui.dearpygui as dpg
import serial
import time
import math
from shared_states import buttons_trials, buttons_lickports2, buttons_lickports1, remembered_relays, active_theme, ser1, ser2
from utils import (
    clean_serial_line,
    update_plot_series,
    send_serial_command,
    setup_button_theme,
    shift_data_window,
    set_trial_phase,
    toggle_trial_button,
    toggle_lickport_button, 
    parse_sensor_line, 
    setup_dynamic_plots
)

print("Attempting serial connection to COM10 and COM11...")
try:
    ser1 = ser1
    ser2 = ser2
    time.sleep(3)
    print("Serial connections established.")
except serial.SerialException as e:
    print(f"Serial connection failed: {e}")
    ser1 = None
    ser2 = None


MAX_POINTS = 300  # or whatever window size you prefer

# We'll detect sensor counts later, but initialize with some max number
data_buffers_arduino1 = []
data_buffers_arduino2 = []
timestamps_arduino1 = []
timestamps_arduino2 = []

plots_initialized = False

# Data containers
counter_list = []
counter = 0

# Trial and relay setup
label_table = [[1,2,3,4,5,6,7,8],[9,10,11,12,13,14,15,16]]
trial_labels = [["Reward-Phase", "Intertrial-Phase"]]


# GUI setup
print("Creating context...")
dpg.create_context()
dpg.create_viewport(title='Multiport', width=1000, height=1000, x_pos=100, y_pos=100)
print("Setting up GUI...")
dpg.setup_dearpygui()

active_theme = setup_button_theme()

def start_main_window():
    dpg.hide_item("intro_window")
    dpg.show_item("main_window")

with dpg.window(label="Welcome / Setup", tag="intro_window", width=500, height=300, no_close=True):
    dpg.add_text("Welcome to the Multiport System")
    dpg.add_input_text(label="Experimenter Name", tag="experimenter_name")
    dpg.add_button(label="Start Experiment", callback=lambda: start_main_window())


with dpg.window(label="Main Window", tag="main_window"):
    dpg.add_text("Trial Name:", indent=50)
    experimenter = dpg.add_input_text(tag="TrialName")

    dpg.add_text("Trial State", indent=50)
    with dpg.table(width=700, header_row=False):
        dpg.add_table_column(); dpg.add_table_column()
        for row in trial_labels:
            with dpg.table_row():
                for label in row:
                    tag = f"button{label}"
                    dpg.add_button(
                        label=label,
                        tag=tag,
                        width=150,
                        height=40,
                        callback=lambda s=tag: toggle_trial_button(s, buttons_trials, active_theme, ser1, ser2)
                    )
                    buttons_trials[tag] = {"checked": False}

    for group, port_label, btn_dict in zip(
        ["Reward 1", "Reward 2"],
        ["1", "2"],
        [buttons_lickports1, buttons_lickports2]
    ):
        dpg.add_text(group, indent=50)
        with dpg.table(width=700, header_row=False):
            for _ in range(8): dpg.add_table_column()
            for row in label_table:
                with dpg.table_row():
                    for label in row:
                        tag = f"button{port_label}_{label}"
                        dpg.add_button(
                            label=str(label),
                            tag=tag,
                            width=100,
                            height=40,
                            callback=(lambda s=tag, d=btn_dict, p=port_label:lambda: toggle_lickport_button(s, d, p, active_theme))()
                        )
                        btn_dict[tag] = {"checked": False}

dpg.set_primary_window("main_window", True)

# Run the application
if __name__ == "__main__":
    print("Finished building GUI. Showing viewport...")
    dpg.show_viewport()
    print("Starting GUI loop...")

    while dpg.is_dearpygui_running():
        if ser1 is None or ser2 is None:
            time.sleep(0.1)
            dpg.render_dearpygui_frame()
            continue

        # === 1. Request sensor data ===
        ser1.write(b's')
        ser2.write(b's')

        # === 2. Read lines from each Arduino ===
        line1 = clean_serial_line(ser1.readline().decode('utf-8'))
        line2 = clean_serial_line(ser2.readline().decode('utf-8'))

        ts1, vals1 = parse_sensor_line(line1)
        ts2, vals2 = parse_sensor_line(line2)

        # === 3. Initialize buffers and plots if needed ===

        if not plots_initialized and vals1 and vals2:
            data_buffers_arduino1 = [[] for _ in vals1]
            data_buffers_arduino2 = [[] for _ in vals2]
            setup_dynamic_plots(len(vals1), len(vals2), parent="main_window")
            plots_initialized = True

        # === 4. Store timestamps and data ===
        if ts1:
            timestamps_arduino1.append(ts1)
            shift_data_window(timestamps_arduino1, MAX_POINTS)
            for buf, val in zip(data_buffers_arduino1, vals1):
                buf.append(val)
                shift_data_window(buf, MAX_POINTS)

        if ts2:
            timestamps_arduino2.append(ts2)
            shift_data_window(timestamps_arduino2, MAX_POINTS)
            for buf, val in zip(data_buffers_arduino2, vals2):
                buf.append(val)
                shift_data_window(buf, MAX_POINTS)

        # === 5. Plot using actual timestamps ===
        all_series = data_buffers_arduino1 + data_buffers_arduino2
        all_timestamps = [timestamps_arduino1] * len(data_buffers_arduino1) + \
                        [timestamps_arduino2] * len(data_buffers_arduino2)

        for i, (series, x_vals) in enumerate(zip(all_series, all_timestamps)):
            line_tag = f"line{i}"
            if dpg.does_item_exist(line_tag):
                update_plot_series(line_tag, x_vals, series)

            # Axis scaling using timestamps
                if x_vals:
                    dpg.set_axis_limits(f"xaxis{i}", x_vals[0], x_vals[-1])
                    dpg.set_axis_limits(f"yaxis{i}", 0, max(series) + 1000)

        dpg.render_dearpygui_frame()

print("GUI closed. Destroying context.")
dpg.destroy_context()
