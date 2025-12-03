# PANGU - Ableton Live Version 1.0.0
> Last Update: Nov/28/2025

![GitHub Created At](https://img.shields.io/badge/Created_At-2025-orange) [![GITHUB](https://img.shields.io/badge/github-repo-blue?logo=github)](https://github.com/CharlieSL1/PanGu-Spatial-Audio-Performance-Control-System) [![Ableton](https://img.shields.io/badge/Ableton-12.2+-orange?logo=ableton-live)](https://www.ableton.com/)

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Hardware Setup](#hardware-setup)
- [Ableton Live Setup](#ableton-live-setup)
- [Usage](#usage)
- [Gesture Controls](#gesture-controls)
- [OSC Data](#osc-data)
- [Troubleshooting](#troubleshooting)
- [Files Overview](#files-overview)

## Overview

This is the Ableton Live integration version of PanGu. It enables real-time control of Ableton Live through hand gestures and 3D spatial positioning. The system uses MediaPipe for hand tracking and an OAK depth camera for 3D spatial audio positioning, allowing performers to control tracks, scenes, clips, and spatial panning through intuitive gestures.

**Key Features:**
- **Hand Gesture Recognition**: Control Ableton tracks, scenes, and clips with predefined gestures
- **3D Spatial Positioning**: Use depth camera to map physical position to spatial panning in Ableton
- **Visual Feedback**: 3D particle system and live video streams for OBS Studio
- **OSC Integration**: Seamless communication between Python scripts and Max/MSP patches in Ableton

## System Requirements

- **Ableton Live**: Version 12.2 or later
- **Max for Live**: Included with Ableton Live Suite, or Max 8 standalone
- **Python**: Version 3.12 recommended
- **Operating System**: macOS Sequoia 15.6.1+ or Windows 11 (25H2+)
- **Hardware**:
  - Standard webcam or camera for hand tracking (MediaPipe)
  - OAK depth camera (optional, for 3D spatial positioning)
  - OBS Studio (optional, for video streaming)

## Installation

### Step 1: Clone and Setup Python Environment

```bash
# Navigate to the Ableton version directory
cd PanGu-Spatial-Audio-Performance-Control-System/V1.X.X/Ableton

# Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r ../../requirements.txt
```

### Step 2: Install Max for Live Device

1. Copy `PANGU.amxd` to your Ableton Live User Library:
   - **macOS**: `/Users/[YourName]/Music/Ableton/User Library/Presets/Audio Effects/Max Audio Effect/`
   - **Windows**: `C:\Users\[YourName]\Documents\Ableton\User Library\Presets\Audio Effects\Max Audio Effect\`

2. Alternatively, use the project file:
   - Open `GANGU_PerformRef Project/GANGU_PerformRef.als` in Ableton Live
   - The PANGU Max for Live device is already included in the project

### Step 3: Configure OAK Camera (Optional)

If you're using an OAK depth camera:

1. Connect the OAK camera via USB or PoE
2. If using PoE, update the IP address in `main.py`:
   ```python
   OAK_DEVICE_IP = "169.254.1.222"  # Change to your OAK camera IP
   ```
3. If using USB, set `OAK_DEVICE_IP = None` for auto-detection

## Hardware Setup

### Camera Configuration

1. **Hand Tracking Camera (MediaPipe)**:
   - Position camera to capture hand gestures clearly
   - Ensure good lighting for optimal hand detection
   - Camera should be placed horizontally at performer level

2. **OAK Depth Camera (Optional - for 3D spatial positioning)**:
   - Mount vertically to capture depth information
   - Position to cover the performance area
   - Ensure stable connection (USB recommended for low latency)

### OBS Studio Setup (Optional)

If you want to stream/record with OBS Studio:

1. Install [OBS Studio](https://obsproject.com/)
2. Add Browser Sources with these URLs:
   - **MediaPipe Motion Stream**: `http://localhost:8080/stream`
   - **OAK Depth View**: `http://localhost:8082/stream`
3. Resolution: 640x480 for both streams

## Ableton Live Setup

### 1. Load the Max for Live Device

1. In Ableton Live, create a new Audio Track
2. Load the **PANGU** Max Audio Effect from your User Library
3. The device will listen on OSC ports:
   - **Port 7400**: Gesture actions (tracks, scenes, clips)
   - **Port 9400**: Spatial XYZ coordinates

### 2. Configure Track/Scene Mapping

The PANGU device responds to these OSC messages:

**Gesture Controls (Port 7400):**
- `/track/right` - Navigate to right track
- `/track/left` - Navigate to left track  
- `/scene/up` - Navigate to scene above
- `/scene/down` - Navigate to scene below
- `/clip/fire` - Fire/Stop the selected clip slot
- `/scene/fire` - Fire/Stop the selected scene
- `/track/master` - Select master track

**Spatial Controls (Port 9400):**
- `/spatial/xyz` - Receives `[x, y, z]` floats for spatial panning

### 3. Project Template

Use the included Ableton project as a template:
- Open `GANGU_PerformRef Project/GANGU_PerformRef.als`
- This project includes the PANGU device and example routing

## Usage

### Starting PanGu

1. **Activate your Python virtual environment**:
   ```bash
   cd V1.X.X/Ableton
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Run the main script**:
   ```bash
   python main.py
   ```

3. **Expected output**:
   ```
   [0/3] Starting 3D Particle System Server...
   [1/3] Starting OAK Depth Streamer for OBS (port 8082) and OSC data...
   [2/3] Starting MediaPipe Motion Streamer for OBS (port 8080)...
   
   Stream URLs for OBS:
     - MediaPipe Motion: http://localhost:8080/stream (640x480)
     - OAK Depth View:   http://localhost:8082/stream (640x480)
   
   3D Particle System:
     - Web Interface:    http://localhost:8766/particle_system.html
     - WebSocket Server: ws://localhost:8765
   
   OSC Data:
     - Person XYZ Coordinates:  Port 9400 (/spatial/x, /spatial/y, /spatial/z)
     - Gesture Actions:  Port 7400 (/track/*, /scene/*, /clip/*)
   ```

4. **Open Ableton Live** and ensure the PANGU device is loaded and active

5. **Open 3D Particle Visualizer** (optional):
   - Navigate to `http://localhost:8766/particle_system.html` in your browser
   - This shows real-time visualization of hand movements

## Gesture Controls

The system recognizes the following gestures for Ableton Live control:

| Gesture | Action | OSC Message | Description |
|---------|--------|-------------|-------------|
| Right Hand to Left | Select Right Track | `/track/right` | Navigate to the track on the right |
| Left Hand to Right | Select Left Track | `/track/left` | Navigate to the track on the left |
| Left Hand Thumb Up | Select Up Scene | `/scene/up` | Navigate to scene above |
| Left Hand Thumb Down | Select Down Scene | `/scene/down` | Navigate to scene below |
| Victory Gesture | Fire/Stop Clip | `/clip/fire` | Fire or stop the selected clip slot |
| Point-Up Gesture | Fire/Stop Scene | `/scene/fire` | Fire or stop the selected scene |
| Two Hand Holding | Select Master Track | `/track/master` | Navigate to master track |

**Note**: Gesture recognition is optimized to prevent hypersensitivity. Small movements are filtered out to ensure stable control.

## OSC Data

### Spatial Positioning (Port 9400)

The system continuously sends the position of the closest detected person:

- **OSC Address**: `/spatial/xyz`
- **Format**: `[float x, float y, float z]`
- **Coordinate Range**: Normalized 0.0 - 1.0 (typically)
- **Smoothing**: Applied to prevent jitter and panning bounce
- **Update Rate**: Real-time (30-60 FPS depending on camera)

Use these coordinates in Max/MSP to control:
- Spatial panning in multichannel setups
- 3D reverb parameters
- Distance-based effects
- Volume automation based on position

### Gesture Actions (Port 7400)

Commands are sent as integer values:
- `/track/right` → `0`
- `/track/left` → `1`
- `/scene/up` → `2`
- `/scene/down` → `3`
- `/clip/fire` → `4`
- `/scene/fire` → `5`
- `/track/master` → `6`

## Troubleshooting

### OSC Messages Not Received in Ableton

1. **Check Port Numbers**: Ensure PANGU device is listening on ports 7400 and 9400
2. **Firewall**: Check if firewall is blocking UDP ports 7400 and 9400
3. **Max Console**: Open Max Console to see OSC messages (View → Max Window)
4. **Device Active**: Ensure the PANGU device is active (not bypassed) in Ableton

### Camera Not Detected

1. **MediaPipe Camera**: Check camera permissions in system settings
2. **OAK Camera**: 
   - Verify USB connection
   - For PoE, check network configuration and IP address
   - Run `python -c "import depthai; depthai.Device()"` to test detection

### Poor Gesture Recognition

1. **Lighting**: Ensure adequate lighting for hand detection
2. **Background**: Use a contrasting background
3. **Distance**: Keep hands within camera frame
4. **Update MediaPipe**: Ensure latest version: `pip install --upgrade mediapipe`

### Performance Issues

1. **Reduce Resolution**: Modify camera resolution in `GetMediaPipe.py`
2. **Close Unused Applications**: Free up CPU for computer vision processing
3. **Virtual Environment**: Ensure you're using the virtual environment with correct dependencies

## Files Overview

| File | Purpose |
|------|---------|
| `main.py` | Main entry point, coordinates all subsystems |
| `GetMediaPipe.py` | Hand tracking with MediaPipe, streams to OBS |
| `motiontask.py` | Gesture recognition and motion task processing |
| `XYlocationGet.py` | OAK depth camera integration for 3D coordinates |
| `DepthViewGet.py` | Depth visualization and OAK camera viewer |
| `MaxShowDepth.py` | HTTP streaming server for OAK depth view (OBS) |
| `MaxShowmotion.py` | HTTP streaming server for MediaPipe view (OBS) |
| `ParticleEffects.py` | 3D particle system visualization server |
| `particle_system.html` | Web interface for 3D particle visualization |
| `PANGU.amxd` | Max for Live device for Ableton integration |
| `PANGUCameraOBS.json` | OBS Studio scene configuration (optional) |
| `gesture_recognizer.task` | MediaPipe gesture recognition model |

## Next Steps

- Customize gesture mappings in `main.py` `send_action()` function
- Adjust spatial smoothing parameters in `CoordinateSmoother` class
- Integrate with your own Max/MSP patches using the OSC data
- Experiment with multichannel spatial audio routing in Ableton

## Contributing

See the main [README.md](../../../README.md) for contribution guidelines and credits.

## License

[MIT](../../../LICENSE) © lishi
