import sys
import json
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QPainter


class FFmpegThread(QThread):
    frame_ready = pyqtSignal(QImage)
    stream_ready = pyqtSignal()
    stream_error = pyqtSignal()

    def __init__(self, url, width, height):
        super().__init__()
        self.url = url
        self.width = width
        self.height = height
        self.process = None
        self.running = True

    def run(self):
        frame_size = self.width * self.height * 3
        try:
            self.process = subprocess.Popen(
                ["ffmpeg", "-rtsp_transport", "tcp", "-loglevel", "error", "-i", self.url, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            first_frame = True
            while self.running:
                data = self.read_exactly(frame_size)
                if not data:
                    break
                image = QImage(data, self.width, self.height, self.width * 3, QImage.Format.Format_RGB888).copy()
                if first_frame:
                    self.stream_ready.emit()
                    first_frame = False
                self.frame_ready.emit(image)
        except Exception:
            self.stream_error.emit()

    def read_exactly(self, size):
        data = bytearray()
        while len(data) < size and self.running:
            chunk = self.process.stdout.read(size - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data) if len(data) == size else None

    def stop(self):
        self.running = False
        if self.process:
            try:
                self.process.stdout.close()
            except Exception:
                pass
            try:
                self.process.kill()
            except Exception:
                pass
            self.process = None


class VideoFrame(QWidget):
    def __init__(self, parent_camera):
        super().__init__()
        self.parent_camera = parent_camera
        self.image = None
        self.setStyleSheet("background-color: black;")

    def set_image(self, image):
        self.image = image
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if self.image is None:
            return
        pixmap = QPixmap.fromImage(self.image)
        pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        x = (self.width() - pixmap.width()) // 2
        y = (self.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_camera.handle_double_click()


class CameraWidget(QWidget):
    def __init__(self, slot_index, initial_channel, parent_grid, config):
        super().__init__()
        self.slot_index = slot_index
        self.current_channel = initial_channel
        self.parent_grid = parent_grid
        self.config = config
        self.ffmpeg_thread = None
        self.is_muted = True
        self.init_ui()
        if self.current_channel != "Vacío":
            self.play_stream("2")

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        self.video_frame = VideoFrame(self)
        layout.addWidget(self.video_frame)
        controls_layout = QHBoxLayout()
        self.cam_selector = QComboBox()
        self.cam_selector.addItem("Vacío")
        for ch in range(1, self.config["TOTAL_CHANNELS"] + 1):
            self.cam_selector.addItem(f"Cam {ch}", str(ch))
        if self.current_channel == "Vacío":
            self.cam_selector.setCurrentIndex(0)
        else:
            index = self.cam_selector.findData(self.current_channel)
            if index != -1:
                self.cam_selector.setCurrentIndex(index)
        self.cam_selector.currentIndexChanged.connect(self.handle_channel_changed)
        controls_layout.addWidget(self.cam_selector)
        self.audio_btn = QPushButton("🔇")
        self.audio_btn.setFixedWidth(40)
        self.audio_btn.setEnabled(False)
        self.audio_btn.setToolTip("Audio pendiente de implementación")
        controls_layout.addWidget(self.audio_btn)
        self.status_label = QLabel("Desconectado")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        controls_layout.addWidget(self.status_label)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        self.setLayout(layout)

    def play_stream(self, stream_type):
        if self.current_channel == "Vacío":
            return
        self.stop_stream()
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.status_label.setText("Conectando...")
        channel_code = f"{self.current_channel}0{stream_type}"
        url = f"rtsp://{self.config['NVR_USER']}:{self.config['NVR_PASS']}@{self.config['NVR_IP']}:{self.config['NVR_PORT']}/Streaming/channels/{channel_code}"
        if stream_type == "1":
            width, height = 2560, 1440
        else:
            width, height = 640, 360
        self.ffmpeg_thread = FFmpegThread(url, width, height)
        self.ffmpeg_thread.frame_ready.connect(self.handle_frame)
        self.ffmpeg_thread.stream_ready.connect(self.handle_stream_ready)
        self.ffmpeg_thread.stream_error.connect(self.handle_stream_error)
        self.ffmpeg_thread.start()

    def stop_stream(self):
        if self.ffmpeg_thread:
            self.ffmpeg_thread.stop()
            self.ffmpeg_thread.wait(1000)
            self.ffmpeg_thread = None
        self.video_frame.image = None
        self.video_frame.update()

    def handle_frame(self, image):
        if self.sender() != self.ffmpeg_thread:
            return
        self.video_frame.set_image(image)

    def handle_stream_ready(self):
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.status_label.setText("OK")

    def handle_stream_error(self):
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_label.setText("SIN SEÑAL")

    def handle_channel_changed(self):
        selected_data = self.cam_selector.currentData()
        new_channel = selected_data if selected_data else "Vacío"
        if new_channel != self.current_channel:
            self.current_channel = new_channel
            self.stop_stream()
            if self.current_channel != "Vacío":
                self.play_stream("2")
            else:
                self.status_label.setText("")
            self.parent_grid.save_current_mapping()

    def toggle_audio(self):
        pass

    def handle_double_click(self):
        if self.current_channel != "Vacío":
            self.parent_grid.handle_camera_double_click(self)

    def close_and_release(self):
        self.stop_stream()
        self.setParent(None)
        self.deleteLater()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor NVR Hikvision 1.0.0")
        self.resize(1280, 720)
        self.load_config()
        self.cameras = []
        self.maximized_cam = None
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.top_bar = QHBoxLayout()
        self.grid_selector = QComboBox()
        self.grid_selector.addItems(["Grilla 2x2", "Grilla 3x3", "Grilla 4x4"])
        initial_index = self.config.get("LAST_GRID_SIZE", 3) - 2
        self.grid_selector.setCurrentIndex(max(0, min(initial_index, 2)))
        self.grid_selector.currentIndexChanged.connect(self.change_grid_size)
        self.top_bar.addWidget(self.grid_selector)
        self.top_bar.addStretch()
        self.main_layout.addLayout(self.top_bar)
        self.grid_layout = QGridLayout()
        self.main_layout.addLayout(self.grid_layout)
        self.build_grid(self.config.get("LAST_GRID_SIZE", 3))

    def load_config(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "config.json")
        if not os.path.exists(config_path):
            print("Error: No se encontró config.json")
            sys.exit(1)
        with open(config_path, "r") as f:
            self.config = json.load(f)

    def save_current_mapping(self):
        current_size = self.grid_selector.currentText()
        size_num = 3
        if "2x2" in current_size:
            size_num = 2
        elif "4x4" in current_size:
            size_num = 4
        mapping = [cam.current_channel for cam in self.cameras]
        self.config["LAST_GRID_SIZE"] = size_num
        self.config["GRID_MAPPING"] = mapping
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def build_grid(self, size):
        for cam in self.cameras:
            cam.close_and_release()
        self.cameras.clear()
        saved_mapping = self.config.get("GRID_MAPPING", [])
        total_slots = size * size
        for i in range(total_slots):
            if i < len(saved_mapping):
                initial_channel = saved_mapping[i]
            else:
                initial_channel = str(i + 1) if (i + 1) <= self.config["TOTAL_CHANNELS"] else "Vacío"
            cam_widget = CameraWidget(i, initial_channel, self, self.config)
            row = i // size
            col = i % size
            self.grid_layout.addWidget(cam_widget, row, col)
            self.cameras.append(cam_widget)
        self.save_current_mapping()

    def change_grid_size(self):
        text = self.grid_selector.currentText()
        if "2x2" in text:
            self.build_grid(2)
        elif "3x3" in text:
            self.build_grid(3)
        elif "4x4" in text:
            self.build_grid(4)

    def handle_camera_double_click(self, clicked_cam):
        if self.maximized_cam is None:
            self.maximized_cam = clicked_cam
            for cam in self.cameras:
                if cam != clicked_cam:
                    cam.setVisible(False)
            clicked_cam.play_stream("1")
        else:
            for cam in self.cameras:
                cam.setVisible(True)
            self.maximized_cam.play_stream("2")
            self.maximized_cam = None

    def closeEvent(self, event):
        for cam in self.cameras:
            cam.stop_stream()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
