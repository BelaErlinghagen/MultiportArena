import serial

ser1 = serial.Serial('COM10', 9600, timeout=1)
ser2 = serial.Serial('COM11', 9600, timeout=1)
buttons_trials = {}
buttons_lickports1 = {}
buttons_lickports2 = {}
remembered_relays = {
    "1": None,  # For Reward 1
    "2": None   # For Reward 2
}
active_theme = None