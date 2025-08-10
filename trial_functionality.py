import threading
import time
import random
import math
from typing import Dict, Any, Optional, Tuple, List

import shared_states
from utils import send_serial_command, set_led

import csv
import dearpygui.dearpygui as dpg
import os
from shared_states import active_theme, buttons_lickports1, buttons_lickports2

# Suggestion for neighbour_leds_map to place into shared_states (example)
# neighbour_leds_map = {
#     1: [2, 16],
#     2: [1, 3],
#     ...
#     16: [15, 1]
# }
#
# You can place this mapping in shared_states.py or generate programmatically.


class TrialController:
    """
    Controls the trial flow based on an already-loaded protocol.
    The controller is intentionally independent of the GUI loop (runs its own thread).
    """

    def __init__(self):
        self.protocol: Dict[str, Any] = {}
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()  # reserved if you want pause/resume
        self.session_running = False

        # runtime variables
        self.current_trial_index = 0
        self.collected_rewards = set()
        self.trial_count_target: Optional[int] = None
        self.session_duration_target: Optional[float] = None  # seconds
        self.session_start_time: Optional[float] = None

        # parsed config (defaults)
        self.phase_length_mode = "time"  # or "position"
        self.trial_phase_length = 10.0
        self.intertrial_phase_length = 5.0
        self.num_rewards = 0
        self.remembered_relays = shared_states.remembered_relays  # live reference
        self.led_mode = "single"  # 'single' or 'neighbour'
        self.neighbour_leds_map = getattr(shared_states, "neighbour_leds_map", {})  # optional
        self.experiment_type = "Open-Field Experiment"
        self.ymaze_settings = {}
        self.light_sphere_cfg = {}
        self.trial_mode = "fixed_trials"  # 'fixed_trials' or 'fixed_time'
        self.mock_dlc_mode = "static"  # 'static' or 'random_walk' (for the mock)
        self.mock_mouse_pos = (0.5, 0.5)  # normalized arena coordinates [0..1]
        self.light_sphere_state = None  # (x, y, size)
        self.event_log_file = None
        self.event_log_writer = None
        self.event_log_path = None

    # ---- Protocol parsing and setup ----
    def load_protocol(self, protocol: Dict[str, Any]):
        """
        Provide a protocol dictionary (the same format you already use).
        This function extracts the fields relevant to trial control.
        """
        self.protocol = protocol or {}
        # experiment type
        self.experiment_type = self.protocol.get("experiment_type", self.experiment_type)

        # light sphere settings (Open-Field)
        self.light_sphere_cfg = self.protocol.get("light_sphere", {})

        # LED config
        self.led_mode = (self.protocol.get("led_configuration", {}).get("mode") or self.led_mode)

        # trial settings
        trial_settings = self.protocol.get("trial_settings", {})
        if trial_settings.get("mode") == "fixed_trials":
            self.trial_mode = "fixed_trials"
            self.trial_count_target = trial_settings.get("trial_count")
            self.session_duration_target = None
        else:
            self.trial_mode = "fixed_time"
            self.trial_count_target = None
            self.session_duration_target = trial_settings.get("session_duration")

        # phase length settings
        phase_length = self.protocol.get("phase_length_settings", {})
        self.phase_length_mode = phase_length.get("phase_length_mode", self.phase_length_mode)
        self.trial_phase_length = float(phase_length.get("trial_phase_length", self.trial_phase_length))
        self.intertrial_phase_length = float(phase_length.get("intertrial_phase_length", self.intertrial_phase_length))

        # rewards
        self.num_rewards = int(self.protocol.get("num_rewards", self.num_rewards))

        # y-maze
        self.ymaze_settings = self.protocol.get("ymaze_settings", {})

        # neighbour map fallback (create ring if not set)
        if not self.neighbour_leds_map:
            self.neighbour_leds_map = self._default_neighbour_map(16)

        print("[TRIAL] Protocol loaded into TrialController.")
        print(f"       Experiment type: {self.experiment_type}")
        print(f"       LED mode: {self.led_mode}, Phase length mode: {self.phase_length_mode}")
        if self.trial_mode == "fixed_trials":
            print(f"       Trial count target: {self.trial_count_target}")
        else:
            print(f"       Session duration target: {self.session_duration_target}s")

    @staticmethod
    def _default_neighbour_map(n_relays: int) -> Dict[int, List[int]]:
        """Generates a circular neighbour map for 1..n_relays."""
        m = {}
        for i in range(1, n_relays + 1):
            left = i - 1 if i > 1 else n_relays
            right = i + 1 if i < n_relays else 1
            m[i] = [left, right]
        return m

    # ---- Session control ----
    def start_session(self):
        if self.session_running:
            print("[TRIAL] Session already running.")
            return
        self.stop_event.clear()
        self.session_running = True
        self.session_start_time = time.time()
        self.current_trial_index = 0
        self.collected_rewards = set()

        try:
            session_path = shared_states.current_session_path
            if session_path and os.path.isdir(session_path):
                self.event_log_path = os.path.join(session_path, "trial_events.csv")
                self.event_log_file = open(self.event_log_path, mode='w', newline='')
                self.event_log_writer = csv.writer(self.event_log_file)
                self.event_log_writer.writerow(["timestamp", "event_type", "details"])
                print(f"[TRIAL] Event log created: {self.event_log_path}")
            else:
                print("[TRIAL] No valid current_session_path found, event logging disabled.")
        except Exception as e:
            print(f"[TRIAL] Could not create event log: {e}")

        # start thread
        self.thread = threading.Thread(target=self._trial_loop, daemon=True)
        self.thread.start()
        self._trigger_output("session_start")
        print("[TRIAL] Session started.")

    def stop_session(self):
        if not self.session_running:
            print("[TRIAL] Session is not running.")
            return
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        self.session_running = False
        self._cleanup_after_session()
        self._trigger_output("session_stop")
        print("[TRIAL] Session stopped by user or end condition.")
        if self.event_log_file:
            try:
                self.event_log_file.close()
                print(f"[TRIAL] Event log saved to {self.event_log_path}")
            except Exception as e:
                print(f"[TRIAL] Error closing event log: {e}")
            self.event_log_file = None
            self.event_log_writer = None

    def _cleanup_after_session(self):
        # Turn off all LEDs and light sphere placeholder
        print("[TRIAL] Cleaning up: turning off LEDs and light sphere.")
        # Turn off all 16 LEDs
        for led in range(1, 17):
            try:
                set_led(None, led, on=False)
            except Exception:
                pass
        self.light_sphere_state = None

    # ---- Trial loop and phases ----
    def _trial_loop(self):
        """
        Main loop that runs trials until stop_event or session end condition.
        Each trial: Reward Phase -> Intertrial Phase -> increment trial counter.
        """
        # If session duration is time-based, store stop time
        session_deadline = None
        if self.session_duration_target is not None:
            session_deadline = self.session_start_time + float(self.session_duration_target)

        while not self.stop_event.is_set():
            # check session end (time)
            if session_deadline and time.time() >= session_deadline:
                print("[TRIAL] Session duration reached.")
                break

            # If trial_count target reached
            if (self.trial_count_target is not None) and (self.current_trial_index >= self.trial_count_target):
                print("[TRIAL] Target trial count reached.")
                break

            # Run Reward Phase
            self.current_trial_index += 1
            print(f"[TRIAL] Starting Trial #{self.current_trial_index}")
            self._trigger_output("trial_start")
            self._run_reward_phase()
            if self.stop_event.is_set():
                break

            # Run Intertrial Phase
            self._run_intertrial_phase()
            if self.stop_event.is_set():
                break

        # End of session
        self.session_running = False
        # call cleanup and ensure recording/GUI stop is called elsewhere
        self._cleanup_after_session()
        print("[TRIAL] Trial loop finished.")

    def _run_reward_phase(self):
        """
        Reward Phase:
        - Activate reward relays / LEDs per remembered_relays
        - If mode=time: wait fixed length
        - If mode=position: wait until all rewards collected (mock DLC to detect licks)
        - Always send output stub for reward_phase
        """
        print("[TRIAL] Entering Reward Phase.")
        self._trigger_output("reward_phase")

        # Activate relays/LEDs according to remembered_relays and led_mode
        self._activate_reward_leds()

        # If Y-Maze -> display patterns and possibly flip depending on cue switch prob
        if self.experiment_type == "Y-Maze":
            self._display_ymaze_cues_for_trial()

        # Reset "collected" for this trial
        self.collected_rewards = set()

        if self.phase_length_mode == "time":
            # wait for trial_phase_length (but allow stop)
            t_end = time.time() + self.trial_phase_length
            while time.time() < t_end and not self.stop_event.is_set():
                # In a real system you'd monitor licks here via sensors/DLC.
                # We mock occasional licks: random chance to collect rewards
                self._mock_maybe_collect_reward()
                time.sleep(0.1)
        else:
            # Wait until all rewards collected (position-based or event-based)
            # We mock by requiring N unique 'collections' (num_rewards)
            attempts = 0
            while not self.stop_event.is_set():
                self._mock_maybe_collect_reward()
                if self.num_rewards > 0 and len(self.collected_rewards) >= self.num_rewards:
                    print("[TRIAL] All rewards collected for this trial.")
                    break
                # Safety: prevent infinite loops if num_rewards is 0
                attempts += 1
                if attempts > 10000:
                    print("[TRIAL] Reward phase stuck; breaking for safety.")
                    break
                time.sleep(0.05)

        # After finishing reward phase, turn off reward LEDs (optional visual)
        self._deactivate_all_reward_leds()
        self._trigger_output("reward_phase_end")
        print("[TRIAL] Reward Phase ended.")

    def _run_intertrial_phase(self):
        """
        Intertrial Phase:
        - Project light sphere (mock)
        - If mode=time: wait fixed time
        - If mode=position: wait until mouse dwells in sphere for dwell_time_threshold
        """
        print("[TRIAL] Entering Intertrial Phase.")
        self._trigger_output("intertrial_phase")

        # Choose location for light sphere: either random or fixed per protocol
        location_mode = self.light_sphere_cfg.get("location_mode", "random")
        size = float(self.light_sphere_cfg.get("size", 40.0))
        dwell_threshold = float(self.light_sphere_cfg.get("dwell_time_threshold", 1.0))

        if location_mode == "fixed":
            # in a real app, you'd set this; here we use center
            sphere_pos = (0.5, 0.5)
        else:
            sphere_pos = (random.uniform(0.2, 0.8), random.uniform(0.2, 0.8))

        self.light_sphere_state = (sphere_pos[0], sphere_pos[1], size)
        self._project_light_sphere(sphere_pos, size)

        if self.phase_length_mode == "time":
            t_end = time.time() + self.intertrial_phase_length
            while time.time() < t_end and not self.stop_event.is_set():
                time.sleep(0.05)
        else:
            # Wait until dwell time threshold in sphere is reached
            dwell_accum = 0.0
            check_interval = 0.05
            while not self.stop_event.is_set():
                mouse_pos = self._get_mouse_position()
                if self._is_point_in_sphere(mouse_pos, sphere_pos, size):
                    dwell_accum += check_interval
                    if dwell_accum >= dwell_threshold:
                        print(f"[TRIAL] Dwell threshold reached: {dwell_accum}s >= {dwell_threshold}s.")
                        self._trigger_output("light_sphere_dwell")
                        break
                else:
                    # reset dwell counter when leaving sphere
                    dwell_accum = 0.0
                time.sleep(check_interval)

        # Clear sphere projection
        self.light_sphere_state = None
        print("[TRIAL] Intertrial Phase ended.")
        self._trigger_output("intertrial_phase_end")

    # ---- Hardware / LED helpers ----
    def _activate_reward_leds(self):
        """
        Activate the LED(s) associated with the remembered_relays. If led_mode == 'neighbour',
        also turn on neighbouring LEDs from neighbour_leds_map.
        remembered_relays is expected to be a dict with keys '1' and '2' mapping to tags like 'button1_3'
        """
        relays = []
        try:
            # remembered_relays in shared_states stores tags like "button1_3" or None
            rr = self.remembered_relays
            for port_str, tag in rr.items():
                if not tag:
                    continue
                # extract the numeric relay index from the tag: "button{port}_{num}"
                try:
                    parts = tag.split("_")
                    relay_num = int(parts[1])
                except Exception:
                    continue
                relays.append(relay_num)

            # Turn on LEDs/relays
            to_activate = set()
            for r in relays:
                to_activate.add(r)
                if self.led_mode == "neighbour":
                    neigh = self.neighbour_leds_map.get(r, [])
                    for n in neigh:
                        to_activate.add(n)

            for led in sorted(to_activate):
                try:
                    set_led(None, int(led), on=True)
                    print(f"[TRIAL] LED {led} ON (activated for reward).")
                    # Highlight GUI lickport button
                    self._highlight_lickport_button(led, True)
                except Exception:
                    print(f"[TRIAL] Failed to activate LED {led} (mock).")
        except Exception as e:
            print(f"[TRIAL] Error activating reward LEDs: {e}")


    def _deactivate_all_reward_leds(self):
        for led in range(1, 17):
            try:
                set_led(None, led, on=False)
                self._highlight_lickport_button(led, False)
            except Exception:
                pass

    # ---- Mock DLC & reward sensing ----
    def _get_mouse_position(self) -> Tuple[float, float]:
        """
        Returns a mock mouse position in normalized [0..1] arena coordinates.
        If you later plug real DLC, replace this method to return actual (x,y).
        """
        if self.mock_dlc_mode == "static":
            return self.mock_mouse_pos
        # random walk mode
        x, y = self.mock_mouse_pos
        x += random.uniform(-0.01, 0.01)
        y += random.uniform(-0.01, 0.01)
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        self.mock_mouse_pos = (x, y)
        return (x, y)

    def _mock_maybe_collect_reward(self):
        """
        Mock behavior that occasionally 'collects' a reward.
        In the real system, you'd check lick sensors / DLC events.
        Here we simulate a chance per call.
        """
        if self.num_rewards <= 0:
            return
        # 1% chance per call to collect one reward
        if random.random() < 0.01:
            # collect a random reward index between 1..num_rewards
            reward_id = random.randint(1, max(1, self.num_rewards))
            self.collected_rewards.add(reward_id)
            print(f"[TRIAL] Mock: reward {reward_id} collected (collected {len(self.collected_rewards)}/{self.num_rewards}).")
            self._trigger_output("reward_port_licks")

    # ---- Light sphere helpers ----
    def _project_light_sphere(self, pos: Tuple[float, float], size: float):
        """Mock: 'project' a light sphere to position pos with size. Replace with serial GUI calls later."""
        x, y = pos
        print(f"[LIGHT] Projecting light sphere at ({x:.2f}, {y:.2f}) size={size} (mock).")

    @staticmethod
    def _is_point_in_sphere(point: Tuple[float, float], sphere_pos: Tuple[float, float], sphere_size: float) -> bool:
        """
        Check if normalized point is within sphere. sphere_size is in arbitrary units;
        assume sphere_size corresponds to a normalized radius factor (for mock we
        map size (e.g., 40) to a radius fraction).
        """
        px, py = point
        sx, sy = sphere_pos
        # convert size to normalized radius (this mapping is arbitrary + mock)
        radius = max(0.01, min(0.4, sphere_size / 200.0))
        dist = math.hypot(px - sx, py - sy)
        return dist <= radius

    # ---- Y-Maze placeholder ----
    def _display_ymaze_cues_for_trial(self):
        """
        Mock Y-Maze pattern display. In the full implementation you might use DearPyGUI
        to draw patterns or swap textures on two windows/screens.
        We include a cue switching toggle based on cue_switch_probability in ymaze_settings.
        """
        ymaze = self.ymaze_settings or {}
        cue_switch_prob = float(ymaze.get("cue_switch_probability", 0.5))
        # Decide whether to swap this trial
        swap = random.random() < cue_switch_prob
        # Placeholder prints — replace with DPG texture swaps or screen updates
        if swap:
            print("[YMAZE] Displaying Pattern A -> Right, Pattern B -> Left (swap).")
        else:
            print("[YMAZE] Displaying Pattern A -> Left, Pattern B -> Right (no swap).")

    # ---- Output hooks (digital/analog mock) ----
    def _trigger_output(self, event_type: str, details: str = ""):
        """
        Mock hook that would drive analog/digital outputs.
        Now also logs the event to trial_events.csv.
        """
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[OUTPUT] ({ts_str}) Would trigger outputs for event '{event_type}'. {details}")
        # Log event
        if self.event_log_writer:
            try:
                self.event_log_writer.writerow([ts_str, event_type, details])
                self.event_log_file.flush()
            except Exception as e:
                print(f"[TRIAL] Failed to log event '{event_type}': {e}")
    
    def _highlight_lickport_button(self, relay_number: int, on: bool):
        """
        Relay numbers 1–8 correspond to port 1 (buttons_lickports1),
        Relay numbers 9–16 correspond to port 2 (buttons_lickports2).
        """
        if relay_number <= 8:
            port = "1"
            button_dict = buttons_lickports1
        else:
            port = "2"
            button_dict = buttons_lickports2
        tag = f"button{port}_{relay_number}"
        if tag in button_dict:
            dpg.set_value(tag, on)
            button_dict[tag]["checked"] = on
            dpg.bind_item_theme(tag, active_theme if on else None)
            

