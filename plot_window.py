# plot_window.py
import sys
import cv2
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import shared_states as S

class PlotWindow(QtWidgets.QMainWindow):
    def __init__(self, update_hz=30):
        super().__init__()
        self.setWindowTitle("Live Data & Camera Dashboard")
        screen = QtWidgets.QApplication.primaryScreen()
        rect = screen.availableGeometry()  # usable area without taskbar
        screen_width = rect.width()
        screen_height = rect.height()

        # Move the window to the right half of the screen
        self.move(rect.x() + screen_width // 2, rect.y())  # top-right corner
        self.resize(screen_width // 2, screen_height)     # half width, full height
        self._closing = False
        self.update_interval_ms = int(1000.0 / float(update_hz))

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)

        # Camera view (ImageView)
        self.camera_view = pg.ImageView(view=pg.PlotItem())
        layout.addWidget(self.camera_view, stretch=2)

        # Sensor plots grid (GraphicsLayoutWidget)
        self.plots_layout = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plots_layout, stretch=3)

        self.sensor_curves = []
        # Build a 4x4 grid of plots
        for row in range(4):
            for col in range(4):
                idx = row * 4 + col
                p = self.plots_layout.addPlot(row=row, col=col, title=f"Sensor {idx+1}")
                p.showGrid(x=True, y=True)
                p.setLabel('left', "Value")
                p.setLabel('bottom', "Time (s)")
                # assign a visible colored pen
                color = (idx * 15 % 255, 100, 255)
                curve = p.plot([], [], pen=pg.mkPen(color=color, width=1))
                self.sensor_curves.append(curve)

        # Timer for updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(self.update_interval_ms)

    def _on_timer(self):
        # Stop if requested
        if getattr(S, "plot_stop_event", None) and S.plot_stop_event.is_set():
            self.timer.stop()
            self.close()
            return

        # Update camera image
        try:
            with S.camera_lock:
                frame = None if S.last_camera_frame is None else S.last_camera_frame.copy()
        except Exception:
            frame = None

        if frame is not None:
            try:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.camera_view.setImage(np.flipud(frame_rgb), autoLevels=False)
            except Exception as e:
                print(f"[PlotWindow] camera update error: {e}")

        # Update sensor curves
        for sid in range(16):
            try:
                times = list(S.gui_time_buffers[sid])
                vals = list(S.gui_plot_buffers[sid])
            except IndexError:
                times = []
                vals = []

            if times and vals and len(times) == len(vals):
                t0 = times[0]
                rel_times = [t - t0 for t in times]
                self.sensor_curves[sid].setData(rel_times, vals)
            else:
                self.sensor_curves[sid].setData([], [])

    def closeEvent(self, event):
        try:
            self.timer.stop()
        except Exception:
            pass
        self._closing = True
        event.accept()

def start_plot_window(update_hz=30):
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    S.plot_qt_app = app

    win = PlotWindow(update_hz=update_hz)
    S.plot_window_ref = win
    win.show()

    try:
        app.exec_()
    finally:
        S.plot_window_ref = None
        S.plot_qt_app = None
        try:
            if getattr(S, "plot_stop_event", None):
                S.plot_stop_event.clear()
        except Exception:
            pass

if __name__ == "__main__":
    start_plot_window()
