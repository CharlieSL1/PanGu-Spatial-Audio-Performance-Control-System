import cv2
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import socket
import struct
from DepthViewGet import OAKDepthViewer

class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            while True:
                if hasattr(self.server, 'frame_bytes'):
                    try:
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(self.server.frame_bytes))
                        self.end_headers()
                        self.wfile.write(self.server.frame_bytes)
                        self.wfile.write(b'\r\n')
                    except:
                        break
        elif self.path == '/frame.jpg':
            if hasattr(self.server, 'frame_bytes'):
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(self.server.frame_bytes))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(self.server.frame_bytes)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

class StreamingServer:
    def __init__(self, port=8082, tcp_port=8083, max_width=640, max_height=480, local_file_path=None, use_virtual_cam=False):
        self.port = port
        self.tcp_port = tcp_port
        self.server = None
        self.thread = None
        self.tcp_socket = None
        self.tcp_client = None
        self.tcp_thread = None
        self.max_width = max_width
        self.max_height = max_height
        self.frame_count = 0
        self.latest_frame_data = None
        self.use_virtual_cam = use_virtual_cam
        self.virtual_cam = None
        if local_file_path is None:
            import os
            self.local_file_path = os.path.expanduser('~/max_depth_frame.jpg')
        else:
            self.local_file_path = local_file_path
    
    def start(self):
        self.server = HTTPServer(('localhost', self.port), StreamingHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"Depth stream available at: http://localhost:{self.port}/stream")
        print(f"Single frame available at: http://localhost:{self.port}/frame.jpg")
        print(f"Local file updated at: {self.local_file_path}")
        print(f"OBS: Add 'Browser Source' with URL: http://localhost:{self.port}/stream")
        print(f"OBS: Or use 'Image Source' pointing to: {self.local_file_path}")
        
        if self.use_virtual_cam:
            try:
                import pyvirtualcam
                self.virtual_cam = pyvirtualcam.Camera(width=self.max_width, height=self.max_height, fps=30)
                print(f"Virtual camera created: {self.virtual_cam.device}")
                print(f"OBS: Use 'Video Capture Device' and select '{self.virtual_cam.device}'")
            except ImportError:
                print("pyvirtualcam not installed. Install with: pip install pyvirtualcam")
                print("Note: On macOS, you may need OBS Virtual Camera. See: https://obsproject.com/")
                self.use_virtual_cam = False
            except Exception as e:
                print(f"Failed to create virtual camera: {e}")
                print("Note: On macOS, you may need OBS Virtual Camera. See: https://obsproject.com/")
                self.use_virtual_cam = False
        
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_socket.bind(('127.0.0.1', self.tcp_port))
            self.tcp_socket.listen(1)
            self.tcp_socket.settimeout(1.0)
            print(f"TCP server listening on port {self.tcp_port} for jit.net.recv")
            self.tcp_thread = Thread(target=self._tcp_accept_loop, daemon=True)
            self.tcp_thread.start()
        except Exception as e:
            print(f"TCP socket creation failed: {e}")
            self.tcp_socket = None
    
    def _tcp_accept_loop(self):
        while self.tcp_socket:
            try:
                client, addr = self.tcp_socket.accept()
                print(f"Max jit.net.recv connected from {addr}")
                self.tcp_client = client
                self.tcp_client.settimeout(None)
                while self.tcp_client:
                    if self.latest_frame_data:
                        try:
                            self.tcp_client.sendall(self.latest_frame_data)
                        except:
                            break
                    time.sleep(0.033)
            except socket.timeout:
                continue
            except Exception as e:
                if self.tcp_socket:
                    print(f"TCP accept error: {e}")
                break
    
    def update_frame(self, frame):
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        frame_data = buffer.tobytes()
        
        if self.server:
            self.server.frame_bytes = frame_data
        
        try:
            success = cv2.imwrite(self.local_file_path, frame)
            if success and self.frame_count == 0:
                print(f"Local file saved successfully: {self.local_file_path}")
        except Exception as e:
            if self.frame_count == 0:
                print(f"Failed to save local file: {e}")
        
        if self.use_virtual_cam and self.virtual_cam:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width = rgb_frame.shape[:2]
                
                if width != self.max_width or height != self.max_height:
                    rgb_frame = cv2.resize(rgb_frame, (self.max_width, self.max_height))
                
                self.virtual_cam.send(rgb_frame)
                self.virtual_cam.sleep_until_next_frame()
            except Exception as e:
                if self.frame_count == 0:
                    print(f"Failed to send frame to virtual camera: {e}")
        
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width = rgb_frame.shape[:2]
            
            if width > self.max_width or height > self.max_height:
                scale = min(self.max_width / width, self.max_height / height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                rgb_frame = cv2.resize(rgb_frame, (new_width, new_height))
                height, width = rgb_frame.shape[:2]
            
            planes = 3
            matrix_data = rgb_frame.tobytes()
            
            matrix_name = b''
            name_len = len(matrix_name)
            
            dimcount = 2
            dims = struct.pack('<ii', width, height)
            type_code = struct.pack('<i', 1)
            planecount = struct.pack('<i', planes)
            
            packet = struct.pack('<i', name_len) + matrix_name + struct.pack('<i', dimcount) + dims + type_code + planecount + matrix_data
            
            self.latest_frame_data = packet
            self.frame_count += 1
            if self.frame_count == 1:
                print(f"First frame prepared: {width}x{height}, packet size: {len(packet)} bytes")
            if self.frame_count % 30 == 0:
                print(f"Prepared {self.frame_count} frames for TCP stream ({width}x{height}, {len(packet)} bytes)")
        except Exception as e:
            print(f"Frame preparation error: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        if self.server:
            self.server.shutdown()
        if self.tcp_client:
            try:
                self.tcp_client.close()
            except:
                pass
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass
        if self.virtual_cam:
            try:
                self.virtual_cam.close()
            except:
                pass

class OAKDepthStreamer:
    def __init__(self, port=8082, tcp_port=8083, use_virtual_cam=False, viewer=None):
        # Use provided viewer or create a new one
        self.viewer = viewer if viewer is not None else OAKDepthViewer()
        self.streaming_server = StreamingServer(port=port, tcp_port=tcp_port, use_virtual_cam=use_virtual_cam)
        self.running = False
    
    def start(self):
        """Start the OAK viewer and streaming server."""
        if not self.viewer.start():
            print("Failed to start OAK device")
            return False
        
        self.streaming_server.start()
        self.running = True
        print("OAK Depth Streamer started")
        print("Press Ctrl+C to stop")
        return True
    
    def run(self):
        """Main loop to stream depth view to OBS."""
        if not self.start():
            return
        
        try:
            while self.running:
                # Get depth frame
                depthFrame = self.viewer.depthQueue.get()
                depthFrameData = depthFrame.getFrame()
                
                # Normalize depth frame for visualization
                depthFrameColor = cv2.normalize(depthFrameData, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
                depthFrameColor = cv2.equalizeHist(depthFrameColor)
                depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_HOT)
                
                # Get spatial data from calculator
                spatial_data = self.viewer.calculator.get_spatial_data(self.viewer.spatialCalcQueue, depthFrame)
                
                # Draw coordinates on frame
                if spatial_data:
                    depthFrameColor = self.viewer.draw_coordinates(depthFrameColor, spatial_data)
                    
                    # Print closest object info (optional, can be removed for production)
                    valid_data = [d for d in spatial_data if d['z'] > 0]
                    if valid_data:
                        closest = min(valid_data, key=lambda d: d['z'])
                        if self.streaming_server.frame_count % 30 == 0:  # Print every 30 frames
                            print(f"Closest: X={closest['x']:.3f}m Y={closest['y']:.3f}m Z={closest['z']:.3f}m")
                
                # Add title
                cv2.putText(depthFrameColor, "OAK Depth View", 
                           (10, depthFrameColor.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Resize depth frame to match streaming server dimensions (640x480)
                # This ensures the full image is visible in OBS
                target_width = 640
                target_height = 480
                if depthFrameColor.shape[1] != target_width or depthFrameColor.shape[0] != target_height:
                    depthFrameColor = cv2.resize(depthFrameColor, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
                
                # Update streaming server with the frame
                self.streaming_server.update_frame(depthFrameColor)
                
                time.sleep(0.033)  # ~30 FPS
        
        except KeyboardInterrupt:
            print("\nStopping OAK Depth Streamer")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the streamer and cleanup."""
        self.running = False
        self.streaming_server.stop()
        self.viewer.calculator.close()
        print("OAK Depth Streamer stopped")

if __name__ == "__main__":
    # Create and run the depth streamer
    # Port 8082 for HTTP stream (different from motion stream on 8080)
    # Port 8083 for TCP stream (different from motion stream on 8081)
    streamer = OAKDepthStreamer(port=8082, tcp_port=8083, use_virtual_cam=False)
    streamer.run()

