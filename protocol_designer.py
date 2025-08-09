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

# ===========================
# Save / Load
# ===========================

def finalize_protocol_file(protocol_data, overwrite=False):
    from utils import check_ready_state
    protocol_name = protocol_data["ProtocolName"]
    filename = f"Protocols/{protocol_name}.json"
    if not overwrite and os.path.exists(filename):
        dpg.configure_item("protocol_overwrite_popup", show=True)
        shared_states.pending_protocol_save = protocol_data
        return False
    with open(filename, "w") as f:
        json.dump(protocol_data, f, indent=4)
    dpg.set_value("protocol_file_path", filename)
    shared_states.current_protocol = protocol_data
    shared_states.protocol_file_path = filename
    print(f"[SAVED] Protocol saved to {filename}")
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
        "ProtocolName": dpg.get_value("protocol_name"),
        "Comments": dpg.get_value("protocol_comments"),
        "num_rewards": int(dpg.get_value("num_rewards")),
        "pwm_reward1": dpg.get_value("pwm_reward1"),
        "pwm_reward2": dpg.get_value("pwm_reward2"),
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
    from gui_functions import update_protocol_summary
    """Load protocol from file and populate UI."""
    file_path = app_data["file_path_name"]
    if not file_path:
        return
    try:
        with open(file_path, "r") as f:
            protocol = json.load(f)
        shared_states.current_protocol = protocol
        dpg.set_value("protocol_file_path", file_path)
        print(f"[LOADED] Protocol from {file_path}")
        update_protocol_summary()
        check_ready_state()
    except Exception as e:
        print(f"[ERROR] Failed to load protocol: {e}")

def set_protocol_values(protocol):
   # Set UI fields
    dpg.set_value("protocol_name", protocol.get("ProtocolName", ""))
    dpg.set_value("protocol_comments", protocol.get("Comments", ""))
    dpg.set_value("experiment_type", protocol.get("experiment_type", "Open-Field Experiment"))
    toggle_experiment_settings()

    dpg.set_value("num_rewards", str(protocol.get("num_rewards", 2)))
    dpg.set_value("pwm_reward1", protocol.get("pwm_reward1", 255))
    dpg.set_value("pwm_reward2", protocol.get("pwm_reward2", 255))
    dpg.set_value("led_mode", protocol.get("led_configuration", {}).get("mode", "single"))

    dpg.set_value("light_sphere_location_mode", protocol.get("light_sphere", {}).get("location_mode", "random"))
    dpg.set_value("light_sphere_size", protocol.get("light_sphere", {}).get("size", 40.0))
    dpg.set_value("dwell_time_threshold", protocol.get("light_sphere", {}).get("dwell_time_threshold", 2.0))

    trial_mode = "Fixed amount of trials" if protocol.get("trial_settings", {}).get("mode") == "fixed_trials" else "Fixed amount of time"
    dpg.set_value("trial_mode", trial_mode)
    toggle_trial_settings()
    dpg.set_value("trial_count", protocol.get("trial_settings", {}).get("trial_count", 100))
    dpg.set_value("session_duration", protocol.get("trial_settings", {}).get("session_duration", 1800.0))

    dpg.set_value("ymaze_enabled", protocol.get("ymaze_settings", {}).get("enabled", False))
    dpg.set_value("cue_switch_probability", protocol.get("ymaze_settings", {}).get("cue_switch_probability", 0.5))

    phase_length_mode = "Time" if protocol.get("phase_length_settings", {}).get("phase_length_mode") == "time" else "Mouse position"
    dpg.set_value("phase_length_mode", phase_length_mode)
    toggle_phase_length_settings()
    dpg.set_value("trial_phase_length", protocol.get("phase_length_settings", {}).get("trial_phase_length", 10.0))
    dpg.set_value("intertrial_phase_length", protocol.get("phase_length_settings", {}).get("intertrial_phase_length", 5.0))

    for key in protocol.get("digital_analog_outputs", {}):
        settings = protocol["digital_analog_outputs"][key]
        dpg.set_value(f"enable_{key}_output", settings.get("enabled", False))
        dpg.set_value(f"{key}_frequency", settings.get("frequency", 0))
    

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
                dpg.add_combo(label="Number of Rewards", items=["1", "2"], default_value=str(defaults["num_rewards"]), tag="num_rewards")
                dpg.add_slider_int(label="PWM Reward 1", default_value=defaults["pwm_reward1"], max_value=255, tag="pwm_reward1")
                dpg.add_slider_int(label="PWM Reward 2", default_value=defaults["pwm_reward2"], max_value=255, tag="pwm_reward2")
                with dpg.group(tag="led_configuration_group"):
                    dpg.add_combo(label="LED Mode", items=["single", "neighbor", "all"], default_value=defaults["led_configuration"]["mode"], tag="led_mode")

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
