# engine.py
import threading, time, os, queue, cv2
from collections import deque
import shared_states as S
from shared_states import camera_lock, last_camera_frame
from utils import clean_serial_line, parse_sensor_line, get_camera_frame

class Engine:
    def __init__(self, target_hz=30):
        self.frame_period = 1.0 / float(target_hz)
        self.running = threading.Event()
        self.acq_q = queue.Queue(maxsize=256)      # (t, frame, ser_vals1, ser_vals2)
        self.writer_q = queue.Queue(maxsize=1024)  # rows / frames to persist
        self.threads = []

    # ---------- Public API ----------
    def start(self):
        if self.running.is_set():
            return
        self.running.set()
        self._start_threads()

    def stop(self):
        self.running.clear()
        for t in self.threads:
            t.join(timeout=2.0)
        self.threads.clear()

    # ---------- Threads ----------
    def _start_threads(self):
        t1 = threading.Thread(target=self._acquisition_loop, name="AcqThread", daemon=True)
        t2 = threading.Thread(target=self._processing_loop, name="ProcThread", daemon=True)
        t3 = threading.Thread(target=self._writer_loop, name="WriterThread", daemon=True)
        self.threads.extend([t1, t2, t3])
        for t in self.threads: t.start()

    def _acquisition_loop(self):
        next_tick = time.perf_counter()
        while self.running.is_set():
            now = time.perf_counter()
            if now < next_tick:
                time.sleep(next_tick - now)
                continue
            next_tick += self.frame_period

            # --- Camera (non-blocking) ---
            frame = get_camera_frame()

            # Store latest camera frame in shared state
            if frame is not None:
                with camera_lock:
                    S.last_camera_frame = frame.copy()
            
            # --- Sensor data request ---
            if S.ser1: S.ser1.write(b's')
            if S.ser2: S.ser2.write(b's')

            line1 = clean_serial_line(S.ser1.readline().decode('utf-8')) if S.ser1 else ""
            line2 = clean_serial_line(S.ser2.readline().decode('utf-8')) if S.ser2 else ""
            ts1, vals1 = parse_sensor_line(line1)
            ts2, vals2 = parse_sensor_line(line2)

            tstamp = time.perf_counter()
            item = (tstamp, frame, (ts1, vals1), (ts2, vals2))
            try:
                self.acq_q.put_nowait(item)
            except queue.Full:
                pass

    def _processing_loop(self):
        """
        Convert acquisition packets into:
          - sensor ring buffers
          - downsampled GUI buffers
          - disk batches (writer_q)
        """
        # local helpers for GUI-thin buffers
        # deques for last ~2s at 10Hz: 20 pts
        gui_len = 200  # points per sensor for GUI (tune)
        if not hasattr(S, "gui_plot_buffers"):
            S.gui_plot_buffers = [deque(maxlen=gui_len) for _ in range(16)]
            S.gui_time_buffers = [deque(maxlen=gui_len) for _ in range(16)]

        # downsample accumulation
        last_gui_push = 0.0
        gui_push_period = 0.1  # 10 Hz to GUI

        while self.running.is_set():
            try:
                tstamp, frame, s1, s2 = self.acq_q.get(timeout=0.1)
            except queue.Empty:
                continue

            (ts1, vals1) = s1
            (ts2, vals2) = s2

            # --- Update ring buffers for full-resolution data (acq rate) ---
            # Use your mapping; keep existing MAX_POINTS
            if ts1 and vals1:
                for i, val in enumerate(vals1):
                    sensor_id = S.sensor_mapping["ser1"][i] - 1
                    # initialize buffers if missing
                    if sensor_id not in S.timestamps:
                        S.timestamps[sensor_id] = deque(maxlen=S.MAX_POINTS)
                        S.data_buffers[sensor_id] = deque(maxlen=S.MAX_POINTS)
                        S.gui_time_buffers[sensor_id] = deque(maxlen=200)
                        S.gui_plot_buffers[sensor_id] = deque(maxlen=200)
                    
                    S.timestamps[sensor_id].append(tstamp)
                    S.data_buffers[sensor_id].append(val)
            if ts2 and vals2:
                for i, val in enumerate(vals2):
                    sensor_id = S.sensor_mapping["ser2"][i] - 1
                    # initialize buffers if missing
                    if sensor_id not in S.timestamps:
                        S.timestamps[sensor_id] = deque(maxlen=S.MAX_POINTS)
                        S.data_buffers[sensor_id] = deque(maxlen=S.MAX_POINTS)
                        S.gui_time_buffers[sensor_id] = deque(maxlen=200)
                        S.gui_plot_buffers[sensor_id] = deque(maxlen=200)
                    
                    S.timestamps[sensor_id].append(tstamp)
                    S.data_buffers[sensor_id].append(val)

            # --- Prepare disk rows if recording ---
            if S.is_recording:
                # combine 16 values (fill zeros if missing)
                combined = [0]*16
                if vals1:
                    for i, v in enumerate(vals1):
                        if i < 8: combined[i] = v
                if vals2:
                    for i, v in enumerate(vals2):
                        idx = i + 8
                        if idx < 16: combined[idx] = v
                self._enqueue_csv_row((tstamp, combined))

                if S.current_session_path and frame is not None:
                    self._enqueue_frame((tstamp, frame))
            # --- Build thin GUI buffers at ~10 Hz ---
            now = time.perf_counter()
            if now - last_gui_push >= gui_push_period:
                last_gui_push = now
                for sensor_id in S.timestamps.keys():
                    if S.timestamps[sensor_id]:
                        S.gui_time_buffers[sensor_id].append(S.timestamps[sensor_id][-1])
                        S.gui_plot_buffers[sensor_id].append(S.data_buffers[sensor_id][-1])

            # TODO: DLC live processing + trial controller could go here,
            # using the same tstamp for synchronization.

    def _enqueue_csv_row(self, row):
        try:
            self.writer_q.put_nowait(("csv", row))
        except queue.Full:
            pass

    def _enqueue_frame(self, frame_tuple):
        try:
            self.writer_q.put_nowait(("frame", frame_tuple))
        except queue.Full:
            pass

    def _writer_loop(self):
        # flush in batches
        batch_rows = []
        last_flush = time.perf_counter()
        FLUSH_PERIOD = 1.0

        while self.running.is_set() or not self.writer_q.empty():
            try:
                kind, payload = self.writer_q.get(timeout=0.1)
            except queue.Empty:
                # periodic flush
                if batch_rows and (time.perf_counter() - last_flush) > FLUSH_PERIOD:
                    self._flush_csv(batch_rows)
                    batch_rows.clear()
                    last_flush = time.perf_counter()
                continue

            if kind == "csv":
                batch_rows.append(payload)
                if len(batch_rows) >= S.CSV_FLUSH_EVERY_N:
                    self._flush_csv(batch_rows)
                    batch_rows.clear()
                    last_flush = time.perf_counter()

            elif kind == "frame":
                tstamp, frame = payload
                # write JPEG
                if S.current_session_path:
                    path = os.path.join(S.current_session_path, "frames", f"frame_{int(tstamp*1000)}.jpg")
                    try: cv2.imwrite(path, frame)
                    except Exception as e: print(f"[WRITER] frame save error: {e}")

        # final flush
        if batch_rows:
            self._flush_csv(batch_rows)

    def _flush_csv(self, rows):
        if not S.csv_writer or not rows: return
        try:
            # rows: list of (tstamp, [v1..v16])
            S.csv_writer.writerows([[rt, *vals] for (rt, vals) in rows])
            S.csv_file.flush()
        except Exception as e:
            print(f"[WRITER] csv flush error: {e}")
