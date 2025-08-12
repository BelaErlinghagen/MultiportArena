# trial_functionality.py
import threading
import time
import random
import math
import csv
import os
from typing import Dict, Any, Optional, Tuple, List

import dearpygui.dearpygui as dpg

import shared_states
from utils import set_led, toggle_lickport_button, toggle_trial_button

# NOTE: do NOT import active_theme, ser1, ser2 at module import time.
# We'll reference them via shared_states.* at execution time so we always
# use the up-to-date objects created in build_gui().

class TrialController:
    def __init__(self):
        self.protocol: Dict[str, Any] = {}
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.session_running = False

        # runtime variables
        self.current_trial_index = 0
        self.collected_rewards = set()
        self.trial_count_target: Optional[int] = None
        self.session_duration_target: Optional[float] = None
        self.session_start_time: Optional[float] = None

        # parsed config (defaults)
        self.phase_length_mode = "time"
        self.trial_phase_length = 10.0
        self.intertrial_phase_length = 5.0
        self.num_rewards = 0
        self.remembered_relays = shared_states.remembered_relays  # live reference (strings like 'button1_1')
        self.led_mode = "single"  # 'single' / 'neighbour' / 'all' (you said you'll add 'all' later)
        self.neighbour_leds_map = getattr(shared_states, "neighbour_leds_map", {})
        self.experiment_type = "Open-Field Experiment"
        self.ymaze_settings = {}
        self.light_sphere_cfg = {}
        self.trial_mode = "fixed_trials"
        self.mock_dlc_mode = "static"
        self.mock_mouse_pos = (0.5, 0.5)
        self.light_sphere_state = None
        self.event_log_file = None
        self.event_log_writer = None
        self.event_log_path = None

    # ---- Protocol parsing and setup ----
    def load_protocol(self, protocol: Dict[str, Any]):
        self.protocol = protocol or {}
        self.experiment_type = self.protocol.get("experiment_type", self.experiment_type)
        self.light_sphere_cfg = self.protocol.get("light_sphere", {})
        self.led_mode = (self.protocol.get("led_configuration", {}).get("mode") or self.led_mode)

        trial_settings = self.protocol.get("trial_settings", {})
        if trial_settings.get("mode") == "fixed_trials":
            self.trial_mode = "fixed_trials"
            self.trial_count_target = trial_settings.get("trial_count")
            self.session_duration_target = None
        else:
            self.trial_mode = "fixed_time"
            self.trial_count_target = None
            self.session_duration_target = trial_settings.get("session_duration")

        phase_length = self.protocol.get("phase_length_settings", {})
        self.phase_length_mode = phase_length.get("phase_length_mode", self.phase_length_mode)
        self.trial_phase_length = float(phase_length.get("trial_phase_length", self.trial_phase_length))
        self.intertrial_phase_length = float(phase_length.get("intertrial_phase_length", self.intertrial_phase_length))
        self.num_rewards = int(self.protocol.get("num_rewards", self.num_rewards))
        self.ymaze_settings = self.protocol.get("ymaze_settings", {})

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
                self.event_log_writer.writerow(["pc_timestamp", "arduino_timestamp", "event_type", "details"])
                print(f"[TRIAL] Event log created: {self.event_log_path}")
            else:
                print("[TRIAL] No valid current_session_path found, event logging disabled.")
        except Exception as e:
            print(f"[TRIAL] Could not create event log: {e}")

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
        print("[TRIAL] Cleaning up: turning off LEDs and light sphere.")
        for led in range(1, 17):
            try:
                set_led(None, led, on=False)
            except Exception:
                pass
        self.light_sphere_state = None

    # ---- Trial loop and phases ----
    def _trial_loop(self):
        session_deadline = None
        if self.session_duration_target is not None:
            session_deadline = self.session_start_time + float(self.session_duration_target)

        while not self.stop_event.is_set():
            if session_deadline and time.time() >= session_deadline:
                print("[TRIAL] Session duration reached.")
                break

            if (self.trial_count_target is not None) and (self.current_trial_index >= self.trial_count_target):
                print("[TRIAL] Target trial count reached.")
                break

            self.current_trial_index += 1
            print(f"[TRIAL] Starting Trial #{self.current_trial_index}")
            self._trigger_output("trial_start")
            self._run_reward_phase()
            if self.stop_event.is_set():
                break
            self._run_intertrial_phase()
            if self.stop_event.is_set():
                break

        self.session_running = False
        self._cleanup_after_session()
        print("[TRIAL] Trial loop finished.")

    def _run_reward_phase(self):
        # queue the trial-phase button toggle on the main GUI thread (capture tag)
        for tag_key in shared_states.buttons_trials.keys():
            try:
                if dpg.get_item_label(tag_key) == "Reward-Phase":
                    shared_states.gui_actions.append(
                        lambda t=tag_key: toggle_trial_button(
                            t, shared_states.buttons_trials, shared_states.active_theme, shared_states.ser1, shared_states.ser2
                        )
                    )
            except Exception:
                # Ignore items that are not GUI buttons (defensive)
                pass

        self._trigger_output("reward_phase")
        self._activate_rewards()
        self._activate_reward_leds()

        if self.experiment_type == "Y-Maze":
            self._display_ymaze_cues_for_trial()

        self.collected_rewards = set()
        if self.phase_length_mode == "time":
            t_end = time.time() + self.trial_phase_length
            while time.time() < t_end and not self.stop_event.is_set():
                self._mock_maybe_collect_reward()
                time.sleep(0.1)
        else:
            attempts = 0
            while not self.stop_event.is_set():
                self._mock_maybe_collect_reward()
                if self.num_rewards > 0 and len(self.collected_rewards) >= self.num_rewards:
                    print("[TRIAL] All rewards collected for this trial.")
                    break
                attempts += 1
                if attempts > 10000:
                    print("[TRIAL] Reward phase stuck; breaking for safety.")
                    break
                time.sleep(0.05)

        self._trigger_output("reward_phase_end")
        print("[TRIAL] Reward Phase ended.")

    def _run_intertrial_phase(self):
        for tag_key in shared_states.buttons_trials.keys():
            try:
                if dpg.get_item_label(tag_key) == "Intertrial-Phase":
                    shared_states.gui_actions.append(
                        lambda t=tag_key: toggle_trial_button(
                            t, shared_states.buttons_trials, shared_states.active_theme, shared_states.ser1, shared_states.ser2
                        )
                    )
            except Exception:
                pass

        print("[TRIAL] Entering Intertrial Phase.")
        self._trigger_output("intertrial_phase")

        location_mode = self.light_sphere_cfg.get("location_mode", "random")
        size = float(self.light_sphere_cfg.get("size", 40.0))
        dwell_threshold = float(self.light_sphere_cfg.get("dwell_time_threshold", 1.0))

        if location_mode == "fixed":
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
                    dwell_accum = 0.0
                time.sleep(check_interval)

        self.light_sphere_state = None
        print("[TRIAL] Intertrial Phase ended.")
        self._trigger_output("intertrial_phase_end")
    
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
            if self.led_mode == "all":
                for led in range(1, 17):
                    try:
                        set_led(None, led, on=True)
                    except Exception:
                        pass
            else:
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
                    except Exception:
                        print(f"[TRIAL] Failed to activate LED {led} (mock).")
        except Exception as e:
            print(f"[TRIAL] Error activating reward LEDs: {e}")


    def _deactivate_all_reward_leds(self):
        for led in range(1, 17):
            try:
                set_led(None, led, on=False)
            except Exception:
                pass

    def _activate_rewards(self):
        # Use remembered_relays dict which stores tags like 'button1_1' and 'button2_2'
        rr = self.remembered_relays or {}
        for port_str, tag_key in rr.items():
            if not tag_key:
                continue
            # queue a GUI toggle using live shared_states.active_theme and live button dicts
            if port_str == "1":
                shared_states.gui_actions.append(
                    lambda t=tag_key: toggle_lickport_button(
                        t, shared_states.buttons_lickports1, "1", shared_states.active_theme
                    )
                )
                print(shared_states.buttons_lickports1)
            elif port_str == "2":
                shared_states.gui_actions.append(
                    lambda t=tag_key: toggle_lickport_button(
                        t, shared_states.buttons_lickports2, "2", shared_states.active_theme
                    )
                )
                print(shared_states.buttons_lickports2)

    # ---- Mock DLC & reward sensing ----
    def _get_mouse_position(self) -> Tuple[float, float]:
        if self.mock_dlc_mode == "static":
            return self.mock_mouse_pos
        x, y = self.mock_mouse_pos
        x += random.uniform(-0.01, 0.01)
        y += random.uniform(-0.01, 0.01)
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        self.mock_mouse_pos = (x, y)
        return (x, y)

    def _mock_maybe_collect_reward(self):
        if self.num_rewards <= 0:
            return
        if random.random() < 0.01:
            reward_id = random.randint(1, max(1, self.num_rewards))
            self.collected_rewards.add(reward_id)
            print(f"[TRIAL] Mock: reward {reward_id} collected ({len(self.collected_rewards)}/{self.num_rewards}).")
            self._trigger_output("reward_port_licks")

    def _project_light_sphere(self, pos: Tuple[float, float], size: float):
        x, y = pos
        print(f"[LIGHT] Projecting light sphere at ({x:.2f}, {y:.2f}) size={size} (mock).")

    @staticmethod
    def _is_point_in_sphere(point: Tuple[float, float], sphere_pos: Tuple[float, float], sphere_size: float) -> bool:
        px, py = point
        sx, sy = sphere_pos
        radius = max(0.01, min(0.4, sphere_size / 200.0))
        dist = math.hypot(px - sx, py - sy)
        return dist <= radius

    def _display_ymaze_cues_for_trial(self):
        ymaze = self.ymaze_settings or {}
        cue_switch_prob = float(ymaze.get("cue_switch_probability", 0.5))
        swap = random.random() < cue_switch_prob
        if swap:
            print("[YMAZE] Displaying Pattern A -> Right, Pattern B -> Left (swap).")
        else:
            print("[YMAZE] Displaying Pattern A -> Left, Pattern B -> Right (no swap).")

    def _trigger_output(self, event_type: str, details: str = ""):
        ts_pc_str = time.strftime("%Y-%m-%d %H:%M:%S")
        arduino_ts = None
        try:
            if shared_states.timestamps and shared_states.timestamps[0]:
                arduino_ts = shared_states.timestamps[0][-1]
        except Exception:
            pass

        print(f"[OUTPUT] ({ts_pc_str}) Would trigger outputs for event '{event_type}'.  [Arduino TS: {arduino_ts}]")

        if self.event_log_writer:
            try:
                self.event_log_writer.writerow([ts_pc_str, arduino_ts, event_type, details])
                self.event_log_file.flush()
            except Exception as e:
                print(f"[TRIAL] Failed to log event '{event_type}': {e}")
