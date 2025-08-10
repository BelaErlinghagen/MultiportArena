# Serial Communication
import serial
import dearpygui as dpg


ser1 = serial.Serial('COM10', 115200, timeout=1)
ser2 = serial.Serial('COM11', 115200, timeout=1)

sensor_mapping = {
    "ser1": [1, 2],  # Maps ser1 values to sensors 1 and 2
    "ser2": [9],     # Maps ser2 values to sensor 9
}

remembered_relays = {
    "1": None,  # For Reward 1
    "2": None   # For Reward 2
}

data_buffers = [[] for _ in range(16)]  # Support for 16 sensors
timestamps = [[] for _ in range(16)]

trial_controller = None

#file management stuff

mouse_folder_path = ""
current_session_name = "session1"
current_mouse_file = None
current_mouse_data = {}
temp_mouse_data = {}
temp_protocol_data = {}
current_session_path = None
current_protocol = None
protocol_file_path = None
pending_protocol_save = None
csv_file = None
csv_writer = None
protocol_loaded = False

protocol_template = {
    "experiment_type": "Open-Field Experiment",
    "protocol_name": "ExampleName",
    "num_rewards": 2,
    "pwm_reward1": 255,
    "pwm_reward2": 255,
    "light_sphere": {
        "size": 40.0,
        "location_mode": "random",
        "dwell_time_threshold": 2.0
    },
    "trial_settings": {
        "mode": "fixed_trials",
        "trial_count": 100,
        "session_duration": 1800.0
    },
    "ymaze_settings": {
        "enabled": False,
        "cue_switch_probability": 0.5
    },
    "phase_length_settings": {
        "trial_phase_length": 10.0,
        "intertrial_phase_length": 5.0,
        "phase_length_mode": "time"
    },
    "led_configuration": {
        "mode": "single"
    },
    "digital_analog_outputs": {
        "session_start": {"enabled": False, "frequency": 0},
        "intertrial_phase": {"enabled": False, "frequency": 0},
        "light_sphere_dwell": {"enabled": False, "frequency": 0},
        "reward_phase": {"enabled": False, "frequency": 0},
        "reward_port_licks": {"enabled": False, "frequency": 0}
    }
}

# camera stuff

CAMERA_WIDTH = 1440
CAMERA_HEIGHT = 810
camera_texture_tag = "camera_texture"
camera_image_tag = "camera_image"
camera_initialized = False
is_recording = False

# GUI stuff


buttons_trials = {}
buttons_lickports1 = {}
buttons_lickports2 = {}
active_theme = None
plots_initialized = False
frame_counter = 0
label_table = [[1,2,3,4,5,6,7,8],[9,10,11,12,13,14,15,16]]
trial_labels = [["Reward-Phase", "Intertrial-Phase"]]
MAX_POINTS = 200
UPDATE_PLOT_EVERY_N_FRAMES = 3