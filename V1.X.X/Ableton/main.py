import motiontask
import GetMediaPipe
from pythonosc import udp_client
import threading
import time
import ParticleEffects

class CoordinateSmoother:
    def __init__(self, alpha=0.3, min_change_threshold=0.01):
        self.alpha = alpha
        self.min_change_threshold = min_change_threshold
        self.smoothed_x = None
        self.smoothed_y = None
        self.smoothed_z = None
        self.initialized = False
    
    def smooth(self, x, y, z):
        """
        Apply exponential moving average smoothing to coordinates.
        
        Returns smoothed (x, y, z) tuple.
        """
        if not self.initialized:
            # Initialize with first values
            self.smoothed_x = x
            self.smoothed_y = y
            self.smoothed_z = z
            self.initialized = True
            return (x, y, z)
        
        # Calculate change magnitude
        dx = abs(x - self.smoothed_x)
        dy = abs(y - self.smoothed_y)
        dz = abs(z - self.smoothed_z)
        change_magnitude = (dx**2 + dy**2 + dz**2)**0.5
        
        # Only update if change is significant enough
        if change_magnitude < self.min_change_threshold:
            return (self.smoothed_x, self.smoothed_y, self.smoothed_z)
        
        # Apply exponential moving average
        self.smoothed_x = self.alpha * x + (1 - self.alpha) * self.smoothed_x
        self.smoothed_y = self.alpha * y + (1 - self.alpha) * self.smoothed_y
        self.smoothed_z = self.alpha * z + (1 - self.alpha) * self.smoothed_z
        
        return (self.smoothed_x, self.smoothed_y, self.smoothed_z)

# Create a global smoother instance for person tracking
person_coord_smoother = CoordinateSmoother(alpha=0.25, min_change_threshold=0.02)

'''
|  ID |       Action            |   Motion Task Action  |
| --- | ----------------------- | --------------------- |
|  0  | Select right track      | Right Hand to left    |
|  1  | Select left track       | Left Hand to right    |
|  2  | Select up scene         | Left Hand Thumb Up    |
|  3  | Select down scene       | Left Hand Thumb Down  |
|  4  | Fire/Stop Clip Slot     | Victory gesture       |
|  5  | Fire/Stop Scene         | Point-Up gesture      |
|  6  | Choose MasterTrack      | Two Hand Holding      |
'''
client = udp_client.SimpleUDPClient("127.0.0.1", 7400)
spatial_client = udp_client.SimpleUDPClient("127.0.0.1", 9400)

def send_action(action, hand_id):
    if action == "right_track":
        client.send_message("/track/right", 0)
    elif action == "left_track":
        client.send_message("/track/left", 1)
    elif action == "up_scene":
        client.send_message("/scene/up", 2)
    elif action == "down_scene":
        client.send_message("/scene/down", 3)
    elif action == "fire_clip":
        client.send_message("/clip/fire", 4)
    elif action == "fire_scene":
        client.send_message("/scene/fire", 5)
    elif action == "master_track":
        client.send_message("/track/master", 6)

def send_xy_location(x, y, z):
    # Apply smoothing to prevent coordinate jitter and panning bounce
    smoothed_x, smoothed_y, smoothed_z = person_coord_smoother.smooth(x, y, z)
    
    # Send three values in a single OSC message for Max/MSP unpack f f f
    # The patch expects: udpreceive 9400 -> unpack f f f
    spatial_client.send_message("/spatial/xyz", [float(smoothed_x), float(smoothed_y), float(smoothed_z)])

motiontask.set_osc_callback(send_action)

particle_hand_data_list = []
particle_hand_data_lock = threading.Lock()
hand_data_timestamps = {} 

def collect_hand_data_for_particles(data):
    global particle_hand_data_list, hand_data_timestamps
    
    hand_id = data.get('hand_id', 0)
    coordinates = data.get('coordinates', {})
    current_time = time.time()
    
    hand_info = {
        'hand_id': hand_id,
        'openness': coordinates.get('openness', 0.5),
        'pinch': coordinates.get('pinch', 0.0),
        'palm_x': coordinates.get('palm_x', 0.5),
        'palm_y': coordinates.get('palm_y', 0.5),
        'palm_z': coordinates.get('palm_z', 0.0)
    }
    
    with particle_hand_data_lock:
        found = False
        for i, existing in enumerate(particle_hand_data_list):
            if existing['hand_id'] == hand_id:
                particle_hand_data_list[i] = hand_info
                found = True
                break
        if not found:
            particle_hand_data_list.append(hand_info)
        
        hand_data_timestamps[hand_id] = current_time
        
        timeout = 1.0
        particle_hand_data_list[:] = [
            h for h in particle_hand_data_list
            if current_time - hand_data_timestamps.get(h['hand_id'], 0) < timeout
        ]
        
        ParticleEffects.update_particle_hand_data(particle_hand_data_list.copy())

def run_depth_streamer(oak_device_info=None):
    """
    Run OAK depth streamer for OBS (port 8082) and OSC data (XYZ coordinates).
    """
    try:
        import MaxShowDepth
        import XYlocationGet
        from DepthViewGet import OAKDepthViewer
        
        # Create shared OAK calculator with OSC callback
        shared_calculator = XYlocationGet.OAKSpatialCalculator(callback=send_xy_location)
        
        # Create depth viewer with the shared calculator and device info
        viewer = OAKDepthViewer(calculator=shared_calculator, device_info=oak_device_info)
        
        # Create depth streamer with the viewer that uses shared calculator
        streamer = MaxShowDepth.OAKDepthStreamer(port=8082, tcp_port=8083, use_virtual_cam=False, viewer=viewer)
        
        print("Starting OAK Depth Streamer on port 8082 for OBS...")
        print("OAK Spatial Calculator running - sending XYZ coordinates via OSC to port 9400")
        streamer.run()
    except Exception as e:
        print(f"OAK Depth Streamer error: {e}")
        print("Continuing without depth stream")

def combined_hand_data_callback(data):
    motiontask.process_hand_data(data)
    
    collect_hand_data_for_particles(data)

if __name__ == "__main__":
    # Start 3D Particle System Server
    print("\n[0/3] Starting 3D Particle System Server...")
    particle_server = ParticleEffects.start_particle_system()
    time.sleep(0.5)  # Give it a moment to initialize
    
    # OAK Device Configuration
    OAK_DEVICE_IP = "169.254.1.222"  
    print("\n[1/3] Starting OAK Depth Streamer for OBS (port 8082) and OSC data...")
    if OAK_DEVICE_IP:
        print(f"Connecting to OAK device at IP: {OAK_DEVICE_IP}")
    else:
        print("Auto-detecting OAK device (USB or POE)...")
    depth_streamer_thread = threading.Thread(target=run_depth_streamer, args=(OAK_DEVICE_IP,), daemon=True)
    depth_streamer_thread.start()
    time.sleep(1.0)
    
    # Start MediaPipe with motion streamer for OBS (port 8080)
    # GetMediaPipe.main() will create its own StreamingServer on port 8080
    print("\n[2/3] Starting MediaPipe Motion Streamer for OBS (port 8080)...")
    print("\n" + "=" * 70)
    print("Stream URLs for OBS:")
    print("  - MediaPipe Motion: http://localhost:8080/stream (640x480)")
    print("  - OAK Depth View:   http://localhost:8082/stream (640x480)")
    print("\n3D Particle System:")
    print("  - Web Interface:    http://localhost:8766/particle_system.html")
    print("  - WebSocket Server: ws://localhost:8765")
    print("\nOSC Data:")
    print("  - Person XYZ Coordinates:  Port 9400 (/spatial/x, /spatial/y, /spatial/z)")
    print("    (Sends closest person's position for Panning control)")
    print("  - Gesture Actions:  Port 7400 (/track/*, /scene/*, /clip/*)")
    print("=" * 70 + "\n")
    GetMediaPipe.main(data_callback=combined_hand_data_callback)

