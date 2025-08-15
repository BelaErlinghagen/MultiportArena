import dearpygui.dearpygui as dpg
import json
import os
import shared_states

# ===========================
# Internal helpers
# ===========================

def toggle_experiment_settings():
    """Show/hide Y-Maze vs Open-Field settings."""
    experiment_type = dpg.get_value("experiment_type")
    if experiment_type == "Y-Maze":
        dpg.show_item("ymaze_settings_group")
        dpg.hide_item("reward_settings_group")
        dpg.hide_item("led_configuration_group")
        dpg.hide_item("light_sphere_settings_group")
    else:
        dpg.hide_item("ymaze_settings_group")
        dpg.show_item("reward_settings_group")
        dpg.show_item("led_configuration_group")
        dpg.show_item("light_sphere_settings_group")

def toggle_trial_settings():
    """Enable trial count or time input based on mode."""
    mode = dpg.get_value("trial_mode")
    if mode == "Fixed amount of trials":
        dpg.enable_item("trial_count")
        dpg.disable_item("session_duration")
    else:
        dpg.disable_item("trial_count")
        dpg.enable_item("session_duration")

def toggle_phase_length_settings():
    """Enable/disable phase length inputs based on mode."""
    mode = dpg.get_value("phase_length_mode")
    if mode == "Time":
        dpg.enable_item("trial_phase_length")
        dpg.enable_item("intertrial_phase_length")
    else:
        dpg.disable_item("trial_phase_length")
        dpg.disable_item("intertrial_phase_length")

def on_num_rewards_changed(sender, app_data):
    num_rewards = int(app_data)
    if num_rewards == 1:
        dpg.disable_item("pwm_reward2_input")
        dpg.disable_item("reward2_probability_input")
    else:
        dpg.enable_item("pwm_reward2_input")
        dpg.enable_item("reward2_probability_input")

# ===========================
# Save / Load
# ===========================

def finalize_protocol_file(protocol_data, overwrite=False):
    from utils import check_ready_state
    protocol_name = protocol_data["protocol_name"]
    filename = f"Protocols/{protocol_name}.json"
    if not overwrite and os.path.exists(filename):
        dpg.configure_item("protocol_overwrite_popup", show=True)
        shared_states.pending_protocol_save = protocol_data
        return False
    with open(filename, "w") as f:
        json.dump(protocol_data, f, indent=4)
    if shared_states.current_mouse_file:
        mouse_folder_path = os.path.dirname(os.path.abspath(shared_states.current_mouse_file))
        with open(f"{mouse_folder_path}\\{shared_states.current_session_name}\\Protocol_{protocol_name}.json", "w") as f:
            json.dump(protocol_data, f, indent = 4)
    dpg.set_value("protocol_file_path", filename)
    shared_states.current_protocol = protocol_data
    shared_states.protocol_file_path = filename
    print(f"[SAVED] Protocol saved to {filename}")
    from gui_functions import update_protocol_summary
    update_protocol_summary("protocol_summary_child_window")    
    shared_states.trial_controller.load_protocol(protocol_data)
    check_ready_state()
    return True

def confirm_protocol_overwrite():
    if hasattr(shared_states, 'pending_protocol_save'):
        finalize_protocol_file(shared_states.pending_protocol_save, overwrite=True)
        del shared_states.pending_protocol_save
        dpg.configure_item("protocol_overwrite_popup", show=False)

def cancel_protocol_overwrite():
    if hasattr(shared_states, 'pending_protocol_save'):
        del shared_states.pending_protocol_save
    dpg.configure_item("protocol_overwrite_popup", show=False)

def save_protocol():
    """Gather UI values and save protocol to JSON."""
    protocol_data = {
        "experiment_type": dpg.get_value("experiment_type"),
        "protocol_name": dpg.get_value("protocol_name"),
        "Comments": dpg.get_value("protocol_comments"),
        "num_rewards": int(dpg.get_value("num_rewards_input")),
        "pwm_reward1": dpg.get_value("pwm_reward1"),
        "pwm_reward2": dpg.get_value("pwm_reward2"),
        "reward1_probability": dpg.get_value("reward1_probability"),
        "reward2_probability": dpg.get_value("reward2_probability"),
        "light_sphere": {
            "size": dpg.get_value("light_sphere_size"),
            "location_mode": dpg.get_value("light_sphere_location_mode"),
            "dwell_time_threshold": dpg.get_value("dwell_time_threshold")
        },
        "trial_settings": {
            "mode": "fixed_trials" if dpg.get_value("trial_mode") == "Fixed amount of trials" else "fixed_time",
            "trial_count": dpg.get_value("trial_count"),
            "session_duration": dpg.get_value("session_duration")
        },
        "ymaze_settings": {
            "enabled": dpg.get_value("ymaze_enabled"),
            "cue_switch_probability": dpg.get_value("cue_switch_probability")
        },
        "phase_length_settings": {
            "trial_phase_length": dpg.get_value("trial_phase_length"),
            "intertrial_phase_length": dpg.get_value("intertrial_phase_length"),
            "phase_length_mode": "time" if dpg.get_value("phase_length_mode") == "Time" else "mouse_position"
        },
        "led_configuration": {
            "mode": dpg.get_value("led_mode")
        },
        "digital_analog_outputs": {
            "session_start": {
                "enabled": dpg.get_value("enable_session_start_output"),
                "frequency": dpg.get_value("session_start_frequency")
            },
            "intertrial_phase": {
                "enabled": dpg.get_value("enable_intertrial_phase_output"),
                "frequency": dpg.get_value("intertrial_phase_frequency")
            },
            "light_sphere_dwell": {
                "enabled": dpg.get_value("enable_light_sphere_dwell_output"),
                "frequency": dpg.get_value("light_sphere_dwell_frequency")
            },
            "reward_phase": {
                "enabled": dpg.get_value("enable_reward_phase_output"),
                "frequency": dpg.get_value("reward_phase_frequency")
            },
            "reward_port_licks": {
                "enabled": dpg.get_value("enable_reward_port_licks_output"),
                "frequency": dpg.get_value("reward_port_licks_frequency")
            }
        }
    }
    finalize_protocol_file(protocol_data)

def protocol_selected(sender, app_data):
    from utils import check_ready_state
    """Load protocol from file and populate UI."""
    file_path = app_data["file_path_name"]
    if not file_path:
        return
    try:
        with open(file_path, "r") as f:
            protocol = json.load(f)
        shared_states.current_protocol = protocol
        if shared_states.current_mouse_file:
            mouse_folder_path = os.path.dirname(os.path.abspath(shared_states.current_mouse_file))
            with open(f"{mouse_folder_path}\\{shared_states.current_session_name}\\Protocol_{protocol["protocol_name"]}.json", "w") as f:
                json.dump(protocol, f, indent = 4)
        dpg.set_value("protocol_file_path", file_path)
        print(f"[LOADED] Protocol from {file_path}")
        shared_states.protocol_loaded = True
        from gui_functions import update_protocol_summary
        update_protocol_summary("protocol_summary_child_window")
        shared_states.trial_controller.load_protocol(protocol)
        check_ready_state()
    except Exception as e:
        print(f"[ERROR] Failed to load protocol: {e}")


# ===========================
# Main UI Builder
# ===========================

def create_protocol_designer_gui():
    defaults = shared_states.protocol_template
    with dpg.window(label="Protocol Designer", width=850, height=650, tag="protocol_designer_window"):
        with dpg.tab_bar():
            # General
            with dpg.tab(label="General"):
                dpg.add_combo(label="Experiment Type", items=["Y-Maze", "Open-Field Experiment"],
                              default_value=defaults["experiment_type"], tag="experiment_type", callback=toggle_experiment_settings)
                dpg.add_input_text(label="Protocol Name", default_value=defaults["protocol_name"], tag="protocol_name")
                dpg.add_input_text(label="Comments", tag="protocol_comments")

            # Rewards
            with dpg.tab(label="Rewards", tag="reward_settings_group"):
                dpg.add_combo(
                    label="Number of Rewards",
                    items=["1", "2"],
                    default_value="2",
                    callback=on_num_rewards_changed,
                    tag="num_rewards_input"
                )
                dpg.add_input_int(label="Reward 1 PWM", default_value=255, min_value=0, max_value=255, tag="pwm_reward1_input")
                dpg.add_input_float(label="Reward 1 Probability", default_value=1.0, min_value=0.0, max_value=1.0, tag="reward1_probability_input")
                dpg.add_input_int(label="Reward 2 PWM", default_value=255, min_value=0, max_value=255, tag="pwm_reward2_input")
                dpg.add_input_float(label="Reward 2 Probability", default_value=1.0, min_value=0.0, max_value=1.0, tag="reward2_probability_input")
                on_num_rewards_changed(None, dpg.get_value("num_rewards_input"))
                with dpg.group(tag="led_configuration_group"):
                    dpg.add_combo(label="LED Mode", items=["single", "neighbor", "all"], default_value=defaults["led_configuration"]["mode"], tag="led_mode")
                with dpg.group(horizontal=True):
                    dpg.add_text("Reward 1 Probability:")
                    dpg.add_input_float(tag="reward1_probability", default_value=defaults.get("reward1_probability", 1.0), min_value=0.0, max_value=1.0, format="%.2f")
                with dpg.group(horizontal=True):
                    dpg.add_text("Reward 2 Probability:")
                    dpg.add_input_float(tag="reward2_probability", default_value=defaults.get("reward2_probability", 1.0), min_value=0.0, max_value=1.0, format="%.2f")

            # Light Sphere
            with dpg.tab(label="Light Sphere", tag="light_sphere_settings_group"):
                dpg.add_combo(label="Location Mode", items=["random", "fixed"], default_value=defaults["light_sphere"]["location_mode"], tag="light_sphere_location_mode")
                dpg.add_input_float(label="Size", default_value=defaults["light_sphere"]["size"], tag="light_sphere_size")
                dpg.add_input_float(label="Dwell Time Threshold (s)", default_value=defaults["light_sphere"]["dwell_time_threshold"], tag="dwell_time_threshold")

            # Trials
            with dpg.tab(label="Trials"):
                dpg.add_combo(label="Trial Mode", items=["Fixed amount of trials", "Fixed amount of time"],
                              default_value="Fixed amount of trials" if defaults["trial_settings"]["mode"] == "fixed_trials" else "Fixed amount of time",
                              tag="trial_mode", callback=toggle_trial_settings)
                dpg.add_input_int(label="Trial Count", default_value=defaults["trial_settings"]["trial_count"], tag="trial_count")
                dpg.add_input_float(label="Session Duration (s)", default_value=defaults["trial_settings"]["session_duration"], tag="session_duration")
                dpg.add_combo(label="Phase Length Mode", items=["Time", "Mouse position"],
                              default_value="Time" if defaults["phase_length_settings"]["phase_length_mode"] == "time" else "Mouse position",
                              tag="phase_length_mode", callback=toggle_phase_length_settings)
                dpg.add_input_float(label="Trial Phase Length (s)", default_value=defaults["phase_length_settings"]["trial_phase_length"], tag="trial_phase_length")
                dpg.add_input_float(label="Intertrial Phase Length (s)", default_value=defaults["phase_length_settings"]["intertrial_phase_length"], tag="intertrial_phase_length")

            # Y-Maze
            with dpg.tab(label="Y-Maze", tag="ymaze_settings_group"):
                dpg.add_checkbox(label="Enable Y-Maze Mode", default_value=defaults["ymaze_settings"]["enabled"], tag="ymaze_enabled")
                dpg.add_slider_float(label="Cue Switch Probability", default_value=defaults["ymaze_settings"]["cue_switch_probability"], max_value=1.0, tag="cue_switch_probability")

            # Digital/Analog Outputs
            with dpg.tab(label="Digital/Analog Outputs"):
                for key, label in [
                    ("session_start", "Session Start"),
                    ("intertrial_phase", "Intertrial Phase"),
                    ("light_sphere_dwell", "Light Sphere Dwell"),
                    ("reward_phase", "Reward Phase"),
                    ("reward_port_licks", "Reward Port Licks")
                ]:
                    dpg.add_checkbox(label=f"Enable {label} Output", default_value=defaults["digital_analog_outputs"][key]["enabled"], tag=f"enable_{key}_output")
                    dpg.add_input_int(label=f"{label} Frequency", default_value=defaults["digital_analog_outputs"][key]["frequency"], tag=f"{key}_frequency")

        # Save / Load buttons
        dpg.add_button(label="Save Protocol", callback=save_protocol)
        dpg.add_button(label="Load Protocol", callback=lambda: dpg.show_item("protocol_file_dialog"))

def show_protocol_designer():
    create_protocol_designer_gui()
    dpg.show_item("protocol_designer_window")
