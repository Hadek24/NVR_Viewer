import sys
import json
import os
import vlc
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, 
                             QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel)
from PyQt6.QtCore import Qt

class VideoFrame(QWidget):
    """Widget de video personalizado para capturar el doble clic"""
    def __init__(self, parent_camera):
        super().__init__()
        self.parent_camera = parent_camera
        self.setStyleSheet("background-color: black;")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_camera.handle_double_click()


class CameraWidget(QWidget):
    """Componente de cámara individual con selector de canal dinámico"""
    def __init__(self, slot_index, initial_channel, vlc_instance, parent_grid, config):
        super().__init__()
        self.slot_index = slot_index  # Posición del cuadro en la grilla (0, 1, 2...)
        self.current_channel = initial_channel  # Puede ser "1", "2" o "Vacío"
        self.vlc_instance = vlc_instance
        self.parent_grid = parent_grid
        self.config = config
        self.is_muted = True 

        self.media_player = self.vlc_instance.media_player_new()
        self.media_player.audio_set_mute(True)

        self.event_manager = self.media_player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.handle_vlc_error)

        self.init_ui()
        
        # Solo reproducir si el cuadro no está configurado como "Vacío"
        if self.current_channel != "Vacío":
            self.play_stream("2")

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)

        self.video_frame = VideoFrame(self)
        layout.addWidget(self.video_frame)

        # Controles inferiores
        controls_layout = QHBoxLayout()
        
        # Desplegable para seleccionar qué cámara va en este cuadro
        self.cam_selector = QComboBox()
        self.cam_selector.addItem("Vacío")
        for ch in range(1, self.config["TOTAL_CHANNELS"] + 1):
            self.cam_selector.addItem(f"Cam {ch}", str(ch))
        
        # Setear el valor inicial guardado
        if self.current_channel == "Vacío":
            self.cam_selector.setCurrentIndex(0)
        else:
            index = self.cam_selector.findData(self.current_channel)
            if index != -1: self.cam_selector.setCurrentIndex(index)
            
        self.cam_selector.currentIndexChanged.connect(self.handle_channel_changed)
        controls_layout.addWidget(self.cam_selector)

        # Botón de audio individual
        self.audio_btn = QPushButton("🔇")
        self.audio_btn.setFixedWidth(40)
        self.audio_btn.clicked.connect(self.toggle_audio)
        controls_layout.addWidget(self.audio_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        controls_layout.addWidget(self.status_label)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        self.setLayout(layout)

        self.media_player.set_xwindow(int(self.video_frame.winId()))

    def play_stream(self, stream_type):
        if self.current_channel == "Vacío":
            return
            
        self.status_label.setText("")
        channel_code = f"{self.current_channel}0{stream_type}"
        url = f"rtsp://{self.config['NVR_USER']}:{self.config['NVR_PASS']}@{self.config['NVR_IP']}:{self.config['NVR_PORT']}/Streaming/Channels/{channel_code}"
        
        try:
            media = self.vlc_instance.media_new(url)
            self.media_player.set_media(media)
            self.media_player.play()
            self.media_player.audio_set_mute(self.is_muted)
        except Exception as e:
            self.status_label.setText("⚠️ ERROR")
            print(f"Error en cuadro {self.slot_index}: {e}")

    def handle_channel_changed(self):
        """Se dispara cuando el usuario elige otra cámara en el desplegable"""
        selected_data = self.cam_selector.currentData()
        new_channel = selected_data if selected_data else "Vacío"
        
        if new_channel != self.current_channel:
            self.current_channel = new_channel
            self.media_player.stop()
            
            if self.current_channel != "Vacío":
                self.play_stream("2")
            else:
                self.status_label.setText("")
            
            # Avisar a la ventana principal para guardar los cambios en el JSON
            self.parent_grid.save_current_mapping()

    def handle_vlc_error(self, event):
        self.status_label.setText("⚠️ SIN SEÑAL")

    def toggle_audio(self):
        if self.current_channel == "Vacío": return
        self.is_muted = not self.is_muted
        self.media_player.audio_set_mute(self.is_muted)
        self.audio_btn.setText("🔇" if self.is_muted else "🔊")

    def handle_double_click(self):
        if self.current_channel != "Vacío":
            self.parent_grid.handle_camera_double_click(self)

    def close_and_release(self):
        self.media_player.stop()
        self.media_player.release()
        self.setParent(None)
        self.deleteLater()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor NVR Hikvision 1.0.0")
        self.resize(1280, 720)

        self.load_config()
        self.vlc_instance = vlc.Instance("--no-xlib --quiet") 

        self.cameras = []
        self.maximized_cam = None

        # UI Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self.top_bar = QHBoxLayout()
        self.grid_selector = QComboBox()
        self.grid_selector.addItems(["Grilla 2x2", "Grilla 3x3", "Grilla 4x4"])
        
        # Mapear el tamaño guardado al índice del combo (2x2=0, 3x3=1, 4x4=2)
        initial_index = self.config.get("LAST_GRID_SIZE", 3) - 2
        self.grid_selector.setCurrentIndex(max(0, min(initial_index, 2)))
        
        self.grid_selector.currentIndexChanged.connect(self.change_grid_size)
        self.top_bar.addWidget(self.grid_selector)
        self.top_bar.addStretch()
        self.main_layout.addLayout(self.top_bar)

        self.grid_layout = QGridLayout()
        self.main_layout.addLayout(self.grid_layout)

        # Construir la grilla con el tamaño que recuperamos del JSON
        self.build_grid(self.config.get("LAST_GRID_SIZE", 3))

    def load_config(self):
        if not os.path.exists("config.json"):
            print("Error: No se encontró config.json")
            sys.exit(1)
        with open("config.json", "r") as f:
            self.config = json.load(f)

    def save_current_mapping(self):
        """Serializa la configuración actual de la pantalla y la guarda en el JSON"""
        current_size = self.grid_selector.currentText()
        size_num = 3
        if "2x2" in current_size: size_num = 2
        elif "4x4" in current_size: size_num = 4

        # Reconstruir la lista de canales según lo que tiene seleccionado cada cuadro
        mapping = [cam.current_channel for cam in self.cameras]

        self.config["LAST_GRID_SIZE"] = size_num
        self.config["GRID_MAPPING"] = mapping

        with open("config.json", "w") as f:
            json.dump(self.config, f, indent=4)

    def build_grid(self, size):
        for cam in self.cameras:
            cam.close_and_release()
        self.cameras.clear()

        saved_mapping = self.config.get("GRID_MAPPING", [])
        total_slots = size * size

        for i in range(total_slots):
            # Intentar recuperar el canal guardado para esta posición. 
            # Si no hay (ej: pasaste de 3x3 a 4x4), asignamos secuencial o "Vacío"
            if i < len(saved_mapping):
                initial_channel = saved_mapping[i]
            else:
                initial_channel = str(i + 1) if (i + 1) <= self.config["TOTAL_CHANNELS"] else "Vacío"

            cam_widget = CameraWidget(i, initial_channel, self.vlc_instance, self, self.config)
            
            row = i // size
            col = i % size
            self.grid_layout.addWidget(cam_widget, row, col)
            self.cameras.append(cam_widget)

        # Guardar el estado por si la grilla cambió de tamaño y generó nuevos cuadros por defecto
        self.save_current_mapping()

    def change_grid_size(self):
        text = self.grid_selector.currentText()
        if "2x2" in text: self.build_grid(2)
        elif "3x3" in text: self.build_grid(3)
        elif "4x4" in text: self.build_grid(4)

    def handle_camera_double_click(self, clicked_cam):
        if self.maximized_cam is None:
            self.maximized_cam = clicked_cam
            for cam in self.cameras:
                if cam != clicked_cam: cam.setVisible(False)
            clicked_cam.play_stream("1")
        else:
            for cam in self.cameras: cam.setVisible(True)
            self.maximized_cam.play_stream("2")
            self.maximized_cam = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
