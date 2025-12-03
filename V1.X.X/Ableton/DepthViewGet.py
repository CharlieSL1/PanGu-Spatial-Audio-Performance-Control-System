import cv2
import time
from XYlocationGet import OAKSpatialCalculator

class OAKDepthViewer:
    def __init__(self, calculator=None, device_info=None):
        """
        Initialize OAK Depth Viewer.
        
        Args:
            calculator: Optional OAKSpatialCalculator instance. If None, creates a new one.
            device_info: Optional device info or IP address for POE devices.
                        If None, will try to connect to first available USB device.
        """
        # Use provided calculator or create a new one
        self.calculator = calculator if calculator is not None else OAKSpatialCalculator()
        self.device_info = device_info
        self.depthQueue = None
        self.spatialCalcQueue = None
    
    def start(self):
        """Start the OAK calculator and get queues."""
        queues = self.calculator.start(device_info=self.device_info)
        if queues[0] is None:
            print("Failed to start OAK device")
            return False
        
        self.depthQueue, self.spatialCalcQueue, _ = queues
        return True
    
    def draw_coordinates(self, frame, spatial_data):
        """Draw coordinates on depth frame."""
        if not spatial_data:
            return frame
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4
        thickness = 1
        color = (255, 255, 255)
        
        # Draw all ROIs and coordinates
        for data in spatial_data:
            roi = data['roi']
            x, y, z = data['x'], data['y'], data['z']
            roi_center = data['roi_center']
            
            # Draw ROI rectangle
            xmin = int(roi[0])
            ymin = int(roi[1])
            xmax = int(roi[0] + roi[2])
            ymax = int(roi[1] + roi[3])
            
            cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)
            
            # Draw center point
            cv2.circle(frame, (int(roi_center[0]), int(roi_center[1])), 3, (0, 255, 0), -1)
            
            # Draw coordinate text
            text_y = ymin + 15
            cv2.putText(frame, f"X: {x*1000:.0f}mm", (xmin + 5, text_y), font, font_scale, color, thickness)
            cv2.putText(frame, f"Y: {y*1000:.0f}mm", (xmin + 5, text_y + 15), font, font_scale, color, thickness)
            cv2.putText(frame, f"Z: {z*1000:.0f}mm", (xmin + 5, text_y + 30), font, font_scale, color, thickness)
        
        # Draw closest object info at top
        valid_data = [d for d in spatial_data if d['z'] > 0]
        if valid_data:
            closest = min(valid_data, key=lambda d: d['z'])
            info_text = f"Closest: X={closest['x']:.3f}m Y={closest['y']:.3f}m Z={closest['z']:.3f}m"
            cv2.putText(frame, info_text, (10, 20), font, 0.5, (0, 255, 0), 2)
        
        return frame
    
    def run(self):
        """Main loop to display depth view with coordinates."""
        if not self.start():
            print("ERROR: Failed to start OAK device. Please check camera connection.")
            return
        
        print("OAK Depth Viewer started")
        print("Press 'q' to quit")
        
        frame_count = 0
        try:
            while True:
                # Get depth frame
                try:
                    depthFrame = self.depthQueue.get(timeout=5.0)
                except:
                    print("WARNING: No depth frame received. Check camera connection.")
                    continue
                
                depthFrameData = depthFrame.getFrame()
                
                # Check if frame is valid
                if depthFrameData is None or depthFrameData.size == 0:
                    print("WARNING: Empty depth frame received.")
                    continue
                
                # Normalize depth frame for visualization
                depthFrameColor = cv2.normalize(depthFrameData, None, 255, 0, cv2.NORM_INF, cv2.CV_8UC1)
                depthFrameColor = cv2.equalizeHist(depthFrameColor)
                depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_HOT)
                
                # Get spatial data from calculator
                spatial_data = self.calculator.get_spatial_data(self.spatialCalcQueue, depthFrame)
                
                # Draw coordinates on frame
                if spatial_data:
                    depthFrameColor = self.draw_coordinates(depthFrameColor, spatial_data)
                    
                    # Print closest object info
                    valid_data = [d for d in spatial_data if d['z'] > 0]
                    if valid_data:
                        closest = min(valid_data, key=lambda d: d['z'])
                        if frame_count % 30 == 0:  # Print every 30 frames
                            print(f"Closest: X={closest['x']:.3f}m Y={closest['y']:.3f}m Z={closest['z']:.3f}m")
                else:
                    # Show message if no spatial data
                    cv2.putText(depthFrameColor, "No spatial data detected", 
                               (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
                # Add instructions
                cv2.putText(depthFrameColor, "OAK Depth View - Press 'q' to quit", 
                           (10, depthFrameColor.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Show frame
                cv2.imshow("OAK Depth View", depthFrameColor)
                
                # Print frame info on first frame
                if frame_count == 0:
                    print(f"Frame size: {depthFrameColor.shape[1]}x{depthFrameColor.shape[0]}")
                    print("Window should be visible now. If not, check if it's minimized or behind other windows.")
                
                frame_count += 1
                
                # Check for quit
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                
                time.sleep(0.01)
        
        except KeyboardInterrupt:
            print("\nStopping OAK Depth Viewer")
        except Exception as e:
            print(f"ERROR in depth viewer: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cv2.destroyAllWindows()
            self.calculator.close()

if __name__ == "__main__":
    viewer = OAKDepthViewer()
    viewer.run()

