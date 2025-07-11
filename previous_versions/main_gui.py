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
    toggle_lickport_button
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

# Constants
MAX_POINTS = 800

# Data containers
data_lp1, data_lp2, data_lp3 = [], [], []
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

    for i in range(3):
        with dpg.plot(height=300, width=800):
            dpg.add_plot_axis(dpg.mvXAxis, label=f"Time", tag=f"xaxis{i}", no_tick_labels=True)
            dpg.add_plot_axis(dpg.mvYAxis, label="Amplitude", tag=f"yaxis{i}")
            dpg.add_line_series([], [], tag=f'line{i+1}', parent=f"yaxis{i}")

dpg.set_primary_window("main_window", True)

# Run the application
if __name__ == "__main__":
    print("Finished building GUI. Showing viewport...")
    dpg.show_viewport()
    print("Starting GUI loop...")
    # dpg.start_dearpygui()
    print("GUI started. Waiting for data...")

    while dpg.is_dearpygui_running():
        # Skip if no serial connection
        if ser1 is None or ser2 is None:
            time.sleep(0.1)
            dpg.render_dearpygui_frame()
            continue  
        new_vals = [
            clean_serial_line(ser1.readline().decode('utf-8')),
            clean_serial_line(ser1.readline().decode('utf-8')),
            clean_serial_line(ser2.readline().decode('utf-8'))
        ]

        for lst, val in zip([data_lp1, data_lp2, data_lp3], new_vals):
            lst.append(val)
            shift_data_window(lst, MAX_POINTS)

        counter += 1
        counter_list.append(counter)
        shift_data_window(counter_list, MAX_POINTS)

        update_plot_series('line1', counter_list, data_lp1)
        update_plot_series('line2', counter_list, data_lp2)
        update_plot_series('line3', counter_list, data_lp3)

        for i, data_series in enumerate([data_lp1, data_lp2, data_lp3]):
        # X-axis scrolling window
            dpg.set_axis_limits(f"xaxis{i}", max(0, counter - MAX_POINTS), counter)
            dpg.set_axis_limits(f"yaxis{i}", 0, 20000)

        dpg.render_dearpygui_frame()

print("GUI closed. Destroying context.")
dpg.destroy_context()
