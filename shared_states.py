# Serial Communication
import serial
ser1 = serial.Serial('COM10', 9600, timeout=1)
ser2 = serial.Serial('COM11', 9600, timeout=1)

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

#file management stuff

mouse_folder_path = ""
current_session_name = "session1"
current_mouse_file = None
current_mouse_data = {}
temp_mouse_data = {}
temp_protocol_data = {}
current_session_path = None
csv_file = None
csv_writer = None

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
MAX_POINTS = 300
UPDATE_PLOT_EVERY_N_FRAMES = 2