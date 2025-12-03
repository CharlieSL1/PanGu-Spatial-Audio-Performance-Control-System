import depthai as dai
import numpy as np
import time
import cv2

# Check depthai version - XLinkOut/XLinkIn were removed in 3.0+
def check_depthai_version():
    """
    Check if depthai version is compatible.
    This code requires depthai < 3.0 because XLinkOut/XLinkIn nodes were removed in 3.0+.
    """
    try:
        dai_version = dai.__version__
        major_version = int(dai_version.split('.')[0])
        if major_version >= 3:
            error_msg = (
                f"\n{'='*70}\n"
                f"DEPTHAI VERSION INCOMPATIBILITY\n"
                f"{'='*70}\n"
                f"Installed version: depthai {dai_version}\n"
                f"Required version: depthai >= 2.0, < 3.0\n\n"
                f"ISSUE: XLinkOut/XLinkIn nodes were removed in depthai 3.0+.\n"
                f"This code uses these nodes for data streaming.\n\n"
                f"SOLUTION: Downgrade depthai to version 2.x:\n"
                f"  pip install 'depthai>=2.0,<3.0'\n\n"
                f"Or if using a virtual environment:\n"
                f"  pip install --upgrade 'depthai>=2.0,<3.0'\n"
                f"{'='*70}\n"
            )
            raise RuntimeError(error_msg)
        return True
    except (AttributeError, ValueError) as e:
        # Version check failed, but continue - will fail later if XLinkOut doesn't exist
        print(f"Warning: Could not determine depthai version: {e}")
        return False

# Perform version check
check_depthai_version()

class OAKSpatialCalculator:
    def __init__(self, callback=None):
        self.callback = callback
        self.pipeline = None
        self.device = None
        self.setup_pipeline()
    
    def setup_pipeline(self):
        """
        Setup OAK camera pipeline for passive stereo depth perception.
        
        Uses left/right mono camera pair for disparity-based depth calculation.
        This approach works well for textured surfaces but may struggle with
        featureless surfaces like walls or ceilings.
        
        References:
        - Depth Perception: https://docs.luxonis.com/hardware/platform/features/depth/
        - StereoDepth Node: https://docs.luxonis.com/software/depthai-components/nodes/stereo_depth
        """
        self.pipeline = dai.Pipeline()
        
        # Create left and right mono cameras for passive stereo depth
        # Passive stereo depth requires a stereo camera pair (like human eyes)
        # Using MonoCamera node (still available in depthai 2.x)
        # Note: Camera node exists but requires different configuration for mono mode
        monoLeft = self.pipeline.create(dai.node.MonoCamera)
        monoRight = self.pipeline.create(dai.node.MonoCamera)
        
        depth = self.pipeline.create(dai.node.StereoDepth)
        spatialCalc = self.pipeline.create(dai.node.SpatialLocationCalculator)
        
        # Try to create XLinkOut/XLinkIn nodes
        # Note: In depthai 3.0+, these may not exist and require a different approach
        try:
            xoutDepth = self.pipeline.create(dai.node.XLinkOut)
            xoutSpatialData = self.pipeline.create(dai.node.XLinkOut)
            xinSpatialCalcConfig = self.pipeline.create(dai.node.XLinkIn)
        except AttributeError:
            raise RuntimeError(
                "XLinkOut/XLinkIn nodes are not available in depthai 3.0+. "
                "This code requires depthai < 3.0 or needs to be updated for the new API. "
                "Please install depthai 2.x: pip install 'depthai<3.0'"
            )
        
        xoutDepth.setStreamName("depth")
        xoutSpatialData.setStreamName("spatialData")
        xinSpatialCalcConfig.setStreamName("spatialCalcConfig")
        
        # Configure cameras
        # Use CAM_B and CAM_C instead of deprecated LEFT and RIGHT
        # CAM_B = left mono camera, CAM_C = right mono camera
        # Reference: https://docs.luxonis.com/software/depthai-components/nodes/stereo_depth
        monoLeft.setBoardSocket(dai.CameraBoardSocket.CAM_B)  # Left camera
        monoRight.setBoardSocket(dai.CameraBoardSocket.CAM_C)  # Right camera
        
        # Set resolution to 400P (400x400 pixels)
        monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        
        # Configure StereoDepth node for passive stereo depth perception
        # Reference: https://docs.luxonis.com/software/depthai-components/nodes/stereo_depth
        # 
        # StereoDepth calculates disparity and depth from stereo camera pair.
        # Disparity is the pixel distance between corresponding points in left/right images.
        # Depth is calculated from disparity using: depth = (focal_length * baseline) / disparity
        #
        # Using DEFAULT preset (replaces deprecated HIGH_DENSITY)
        # This preset provides good balance between accuracy and performance
        # Matches "Default" and "Robotics" presets from documentation
        # Reference: https://docs.luxonis.com/software/depthai-components/nodes/stereo_depth
        depth.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        
        # Depth Post-Processing Filters (from StereoDepth documentation)
        # Median filter reduces noise and improves depth quality
        # 7x7 kernel is used in Default/Robotics presets
        # Note: Median filtering is disabled when subpixel mode is set to 4 or 5 bits
        depth.initialConfig.setMedianFilter(dai.MedianFilter.KERNEL_7x7)
        
        # Stereo Mode Configuration (from StereoDepth documentation)
        #
        # Left-Right Check (LR-Check):
        # - Removes incorrectly calculated disparity pixels due to occlusions
        # - Computes disparity in both R->L and L->R directions
        # - Validates consistency between both directions
        # - Recommended for better accuracy, especially at object borders
        depth.setLeftRightCheck(True)
        
        # Extended Disparity:
        # - Increases max disparity search from 96 to 191 pixels
        # - Reduces minimum depth perception (allows closer objects)
        # - Computes disparity on original + 2x downscaled images, then merges
        # - Tradeoff: Slightly slower due to extra computation
        # - Disabled here to prioritize max depth range
        depth.setExtendedDisparity(False)
        
        # Subpixel Disparity:
        # - Improves precision, especially for long-range measurements
        # - Helps with better surface normal estimation
        # - 3-bit subpixel: 94 depth steps * 8 subpixel steps + 2 = 754 depth steps
        # - 5-bit subpixel: Even more precision (used in Face/High Detail presets)
        # - Disabled here (0-bit) for standard operation, can enable for higher precision
        depth.setSubpixel(False)
        
        # Additional configuration options available (not set here):
        # - Confidence threshold: Controls depth confidence filtering
        # - LR check threshold: Threshold for LR-RL disparity difference validation
        # - Disparity shift: Can lower min depth but significantly reduces max depth
        
        # Link left and right mono cameras to StereoDepth node
        # The StereoDepth node performs disparity matching internally
        monoLeft.out.link(depth.left)
        monoRight.out.link(depth.right)
        
        # Link StereoDepth outputs to SpatialLocationCalculator
        # passthroughDepth: Passes through the depth map for visualization/processing
        # depth: Main depth output used for spatial calculations
        spatialCalc.passthroughDepth.link(xoutDepth.input)
        depth.depth.link(spatialCalc.inputDepth)
        
        # Link SpatialLocationCalculator outputs and inputs
        spatialCalc.out.link(xoutSpatialData.input)
        xinSpatialCalcConfig.out.link(spatialCalc.inputConfig)
        
        # Configure SpatialLocationCalculator ROI (Region of Interest)
        # Reference: https://docs.luxonis.com/software-v3/depthai/examples/spatial_location_calculator/spatial_location_calculator/
        # 
        # Depth Thresholds (in millimeters):
        # - lowerThreshold: 100mm = 10cm minimum depth
        # - upperThreshold: 10000mm = 10m maximum depth
        # These thresholds filter out depth values outside the valid range
        #
        # ROI (Region of Interest):
        # - Normalized coordinates (0.0 to 1.0)
        # - spatialCoordinates X/Y/Z are relative to depth map center (camera optical center)
        # - If ROI is at image center and object is at center, X/Y will be 0 (correct behavior)
        # - To get non-zero X/Y for objects not at center, use multiple ROIs at different positions
        #
        # Calculation Algorithm:
        # - MEDIAN: Uses median depth value in ROI (good for noisy depth, recommended)
        # - MEAN: Uses average depth value
        # - MIN/MAX: Uses minimum/maximum depth value
        # - MODE: Uses most common depth value
        # Reference: https://docs.luxonis.com/software-v3/depthai/examples/spatial_location_calculator/spatial_location_calculator/
        
        # Use multiple small ROIs in a 3x3 grid to detect objects at different positions
        # This allows X/Y coordinates to vary based on object position
        # Each ROI is 0.15 x 0.15 (15% of image) in a 3x3 grid
        roi_size = 0.15  # 15% of image per ROI
        roi_spacing = 0.3  # Spacing between ROI centers
        
        for row in range(3):
            for col in range(3):
                # Calculate ROI position in normalized coordinates
                center_x = 0.2 + col * roi_spacing  # 0.2, 0.5, 0.8
                center_y = 0.2 + row * roi_spacing  # 0.2, 0.5, 0.8
                
                topLeft = dai.Point2f(
                    max(0.0, center_x - roi_size / 2),
                    max(0.0, center_y - roi_size / 2)
                )
                bottomRight = dai.Point2f(
                    min(1.0, center_x + roi_size / 2),
                    min(1.0, center_y + roi_size / 2)
                )
                
                roi_config = dai.SpatialLocationCalculatorConfigData()
                roi_config.depthThresholds.lowerThreshold = 100
                roi_config.depthThresholds.upperThreshold = 10000
                
                # Set calculation algorithm to MEDIAN (recommended for noisy depth data)
                try:
                    roi_config.calculationAlgorithm = dai.SpatialLocationCalculatorAlgorithm.MEDIAN
                except AttributeError:
                    # Fallback if calculationAlgorithm doesn't exist
                    pass
                
                roi_config.roi = dai.Rect(topLeft, bottomRight)
                spatialCalc.initialConfig.addROI(roi_config)
        
        # Note on Depth Accuracy (from StereoDepth documentation):
        # - Accuracy depends on texture, lighting, baseline, and distance
        # - Works best on textured surfaces (struggles with featureless walls/ceilings)
        # - Low lighting reduces confidence and increases noise
        # - Baseline affects min/max depth range and accuracy at different distances
        # - For OAK-D (7.5cm baseline): theoretical max distance ~38.25 meters
        # - There's a vertical band on left/right edges where depth cannot be calculated
        #   (only visible to one camera)
    
    def start(self, device_info=None):
        """
        Start the OAK device.
        
        Args:
            device_info: Optional device info or IP address for POE devices.
                        If None, will try to connect to first available USB device.
                        If string (e.g., "169.254.1.222"), will connect to POE device at that IP.
        """
        try:
            # Check for available devices
            available_devices = dai.Device.getAllAvailableDevices()
            
            # If device_info is provided (e.g., IP address for POE), use it
            if device_info:
                if isinstance(device_info, str):
                    # Assume it's an IP address for POE device
                    print(f"Attempting to connect to POE device at IP: {device_info}")
                    try:
                        # Try to create DeviceInfo directly from IP address
                        # For POE devices, we can connect directly even if not in available_devices
                        device_info_obj = dai.DeviceInfo(device_info)
                        print(f"Created DeviceInfo for IP: {device_info}")
                    except Exception as e:
                        print(f"Error creating device info from IP {device_info}: {e}")
                        # Try to find device by IP in available devices
                        if available_devices:
                            device_info_obj = None
                            for dev in available_devices:
                                dev_mxid = dev.getMxId() if hasattr(dev, 'getMxId') else str(dev)
                                dev_name = dev.getName() if hasattr(dev, 'getName') else str(dev)
                                if dev_mxid == device_info or dev_name == device_info:
                                    device_info_obj = dev
                                    print(f"Found device in available devices: {dev_mxid}")
                                    break
                            if device_info_obj is None:
                                print(f"Device with IP/name '{device_info}' not found in available devices")
                                print("Available devices:")
                                for dev in available_devices:
                                    mxid = dev.getMxId() if hasattr(dev, 'getMxId') else "N/A"
                                    name = dev.getName() if hasattr(dev, 'getName') else "N/A"
                                    print(f"  - {mxid} ({name})")
                                # Still try to connect directly with IP
                                print(f"Attempting direct connection to IP: {device_info}")
                                try:
                                    device_info_obj = dai.DeviceInfo(device_info)
                                except Exception as e2:
                                    print(f"Direct connection failed: {e2}")
                                    return None, None, None
                        else:
                            # No available devices, but try direct connection anyway
                            print(f"No devices found in scan, attempting direct connection to IP: {device_info}")
                            try:
                                device_info_obj = dai.DeviceInfo(device_info)
                            except Exception as e2:
                                print(f"Direct connection failed: {e2}")
                                print("Please check:")
                                print("  1. POE device is powered on and connected to network")
                                print("  2. IP address is correct")
                                print("  3. OAK Viewer or other applications are not using the device")
                                return None, None, None
                else:
                    device_info_obj = device_info
            else:
                # Auto-detect: Use first available device (USB or POE)
                if not available_devices:
                    print("Error: No OAK devices found")
                    print("Please check:")
                    print("  1. USB device is connected, or")
                    print("  2. POE device is on the network")
                    print("  3. Set OAK_DEVICE_IP in main.py if using POE device")
                    return None, None, None
                device_info_obj = available_devices[0]
            
            device_name = device_info_obj.getMxId() if hasattr(device_info_obj, 'getMxId') else str(device_info_obj)
            print(f"Connecting to device: {device_name}")
            
            # Create device with device info
            self.device = dai.Device(device_info_obj)
            self.device.startPipeline(self.pipeline)
            
            print("Device connected successfully!")
            
            # Get camera calibration for calculating 3D coordinates from depth
            calibData = self.device.readCalibration()
            self.camera_intrinsics = calibData.getCameraIntrinsics(
                dai.CameraBoardSocket.CAM_B, 
                dai.MonoCameraProperties.SensorResolution.THE_400_P
            )
            
            depthQueue = self.device.getOutputQueue(name="depth", maxSize=4, blocking=False)
            spatialCalcQueue = self.device.getOutputQueue(name="spatialData", maxSize=4, blocking=False)
            spatialCalcConfigInQueue = self.device.getInputQueue("spatialCalcConfig")
            
            return depthQueue, spatialCalcQueue, spatialCalcConfigInQueue
        except Exception as e:
            print(f"Error starting OAK device: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None
    
    def get_spatial_data(self, spatialCalcQueue, depthFrame=None):
        """
        Get spatial data from SpatialLocationCalculator.
        
        If depthFrame is provided, also calculate X/Y from depth map using camera intrinsics.
        This provides more accurate X/Y coordinates even when ROI is at image center.
        
        The issue: SpatialLocationCalculator returns X/Y=0 when ROI covers full image and
        calculates average point. We calculate X/Y from pixel coordinates and depth instead.
        """
        inSpatial = spatialCalcQueue.tryGet()
        if inSpatial is not None:
            spatialData = inSpatial.getSpatialLocations()
            results = []
            
            for depthData in spatialData:
                roi = depthData.config.roi
                roi = roi.denormalize(width=400, height=400)
                
                # Get raw spatial coordinates (in millimeters)
                # spatialCoordinates are 3D coordinates relative to camera optical center:
                # X: left/right from camera center (positive = right, negative = left)
                # Y: up/down from camera center (positive = down, negative = up)
                # Z: depth from camera (positive = forward)
                raw_x = depthData.spatialCoordinates.x
                raw_y = depthData.spatialCoordinates.y
                raw_z = depthData.spatialCoordinates.z
                
                # Convert to meters
                x = raw_x / 1000.0
                y = raw_y / 1000.0
                z = raw_z / 1000.0
                
                # Calculate ROI center position in image
                roi_center_x = roi.x + roi.width / 2.0
                roi_center_y = roi.y + roi.height / 2.0
                
                # Calculate X/Y from pixel coordinates and depth using camera intrinsics
                # This gives accurate X/Y coordinates even when ROI is at image center
                # Formula: X = (u - cx) * Z / fx, Y = (v - cy) * Z / fy
                # Reference: https://docs.luxonis.com/software/depthai-components/nodes/spatial_location_calculator/
                if hasattr(self, 'camera_intrinsics') and z > 0:
                    # Get camera intrinsics
                    fx = self.camera_intrinsics[0][0]  # Focal length X
                    fy = self.camera_intrinsics[1][1]  # Focal length Y
                    cx = self.camera_intrinsics[0][2]  # Principal point X (usually image center)
                    cy = self.camera_intrinsics[1][2]  # Principal point Y (usually image center)
                    
                    # Calculate 3D coordinates from pixel coordinates and depth
                    u = roi_center_x
                    v = roi_center_y
                    
                    # Calculate X and Y in 3D space (in meters)
                    # This gives the actual 3D position relative to camera center
                    # Note: If ROI center is at image center (u=cx, v=cy), then X=0, Y=0
                    # This is correct - objects on the optical axis have X=Y=0
                    x_calculated = (u - cx) * z / fx
                    y_calculated = (v - cy) * z / fy
                    
                    # Use calculated values for more accurate X/Y
                    # spatialCoordinates might be 0 if ROI covers full image (calculates average)
                    x = x_calculated
                    y = y_calculated
                    
                    # Debug output (uncomment to see values):
                    # print(f"ROI center: ({u:.1f}, {v:.1f}), Camera center: ({cx:.1f}, {cy:.1f})")
                    # print(f"Calculated: X={x_calculated:.3f}m, Y={y_calculated:.3f}m, Z={z:.3f}m")
                
                results.append({
                    'x': x,  # 3D X coordinate (meters, relative to camera center)
                    'y': y,  # 3D Y coordinate (meters, relative to camera center)
                    'z': z,  # 3D Z coordinate (meters, depth)
                    'roi': (roi.x, roi.y, roi.width, roi.height),
                    'roi_center': (roi_center_x, roi_center_y),
                    'raw': (raw_x, raw_y, raw_z)  # Raw values in mm
                })
            
            # Only call callback with the closest valid object (for Panning control)
            # This ensures we send only one set of coordinates per frame
            if results and self.callback:
                valid_results = [r for r in results if r['z'] > 0]
                if valid_results:
                    # Get the closest object (smallest Z/depth) - this is likely the person
                    closest = min(valid_results, key=lambda r: r['z'])
                    self.callback(closest['x'], closest['y'], closest['z'])
            
            return results
        return None
    
    def update_roi(self, spatialCalcConfigInQueue, topLeft, bottomRight):
        config = dai.SpatialLocationCalculatorConfigData()
        config.depthThresholds.lowerThreshold = 100
        config.depthThresholds.upperThreshold = 10000
        config.roi = dai.Rect(topLeft, bottomRight)
        
        cfg = dai.SpatialLocationCalculatorConfig()
        cfg.addROI(config)
        spatialCalcConfigInQueue.send(cfg)
    
    def close(self):
        if self.device:
            del self.device

def run_oak_spatial_calculator(callback=None, device_info=None):
    """
    Run OAK spatial calculator with optional device info.
    
    Args:
        callback: Optional callback function for XYZ coordinates.
        device_info: Optional device info or IP address for POE devices.
    """
    calculator = OAKSpatialCalculator(callback=callback)
    depthQueue, spatialCalcQueue, spatialCalcConfigInQueue = calculator.start(device_info=device_info)
    
    if depthQueue is None:
        print("Failed to start OAK device")
        return None
    
    print("OAK Spatial Calculator started")
    
    try:
        while True:
            depthFrame = depthQueue.get()
            # Pass depthFrame to get_spatial_data for calculating X/Y from depth map
            spatial_data = calculator.get_spatial_data(spatialCalcQueue, depthFrame)
            if spatial_data:
                # Filter out invalid results (Z=0 means no depth data)
                valid_data = [d for d in spatial_data if d['z'] > 0]
                
                if valid_data:
                    # Get the closest object (smallest Z/depth)
                    closest = min(valid_data, key=lambda d: d['z'])
                    print(f"XY Location: X={closest['x']:.3f}m, Y={closest['y']:.3f}m, Z={closest['z']:.3f}m")
                    
                    # Optionally print all valid results for debugging:
                    # for data in valid_data:
                    #     print(f"  ROI at ({data['roi_center'][0]:.0f}, {data['roi_center'][1]:.0f}): X={data['x']:.3f}m, Y={data['y']:.3f}m, Z={data['z']:.3f}m")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping OAK Spatial Calculator")
    finally:
        calculator.close()
    
    return calculator

if __name__ == "__main__":
    def xy_callback(x, y, z):
        print(f"Callback: X={x:.3f}m, Y={y:.3f}m, Z={z:.3f}m")
    
    run_oak_spatial_calculator(callback=xy_callback)
