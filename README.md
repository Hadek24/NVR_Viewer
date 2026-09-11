# NVR Viewer

A lightweight Linux GUI application for viewing Hikvision NVR camera streams using RTSP.

The project was created as a personal lab project to replace a heavier video surveillance client with a simpler application focused on the features actually needed for everyday monitoring.

## Features

Current version — v1.0.0

* PyQt6 graphical interface
* VLC-based video playback
* RTSP streams from Hikvision NVR
* Configurable number of camera channels
* 2x2, 3x3 and 4x4 grid layouts
* Individual camera/channel selection
* Audio mute/unmute per camera
* Substream for multi-camera view
* Mainstream when maximizing a camera
* Persistent grid configuration using JSON
* Double-click to maximize/restore a camera

## Requirements

* Linux
* Python 3
* PyQt6
* VLC
* python-vlc
* A Hikvision-compatible NVR/camera system providing RTSP streams

## Installation

Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

Install the required system packages:
```bash
sudo apt update
sudo apt install vlc python3-pyqt6 python3-vlc
```

## Configuration

The application uses a local `config.json` file for the NVR connection and application settings.

Create it from the example configuration:
```bash
cp config.example.json config.json
```

Example (`config.json`):
```json
{
    "NVR_USER": "admin",
    "NVR_PASS": "your_password",
    "NVR_IP": "192.168.1.100",
    "NVR_PORT": "554",
    "TOTAL_CHANNELS": 16,
    "LAST_GRID_SIZE": 3,
    "GRID_MAPPING": [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9"
    ]
}
```

> ⚠️ **Important:** `config.json` contains credentials and is intentionally excluded from the Git repository. Do not commit real passwords or other sensitive information.

## Running

Start the application with:
```bash
python3 nvr_viewer.py
```

The application connects directly to the NVR using RTSP.

## RTSP

The application uses Hikvision RTSP channel URLs following the standard channel/stream structure:
```text
rtsp://USER:PASSWORD@NVR_IP:PORT/Streaming/Channels/CHANNEL0STREAM
```

For example:
* **Channel 1 + substream:** `.../Streaming/Channels/102`
* **Channel 1 + mainstream:** `.../Streaming/Channels/101`

The multi-camera grid uses the substream to reduce resource usage, while the maximized camera uses the mainstream.

## Project Structure

```text
nvr-viewer/
├── nvr_viewer.py
├── config.example.json
├── config.json          # Local only - not tracked by Git
├── .gitignore
└── README.md
```

## Project Status

This is an actively developed personal project.
The current priority is stability and reliability before adding additional features.

## License

This project is provided for educational and personal use.
