import cv2
import mediapipe as mp
import numpy as np
from pythonosc import udp_client
import argparse
from collections import deque

class HandToOSC:
    def __init__(self, ip="127.0.0.1", port=7400):
        # Initialize MediaPipe
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
        # OSC client
        self.osc_client = udp_client.SimpleUDPClient(ip, port)
        
        # Smoothing buffers (reduce jitter)
        self.history_size = 3
        self.smoothing_buffers = {}
        
    def calculate_hand_features(self, landmarks, hand_id):
        """Extract musically relevant features from hand landmarks"""
        
        # Convert to numpy array for easier computation
        pts = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark])
        
        features = {}
        
        # 1. Palm center position (normalized 0-1)
        palm_indices = [0, 1, 5, 9, 13, 17]  # wrist + base of each finger
        palm_center = pts[palm_indices].mean(axis=0)
        features['palm_x'] = palm_center[0]
        features['palm_y'] = palm_center[1]
        features['palm_z'] = palm_center[2]
        
        # 2. Hand openness (0=closed fist, 1=open hand)
        # Distance from fingertips to palm center
        fingertip_indices = [4, 8, 12, 16, 20]
        fingertip_distances = [np.linalg.norm(pts[i][:2] - palm_center[:2]) 
                               for i in fingertip_indices]
        features['openness'] = np.mean(fingertip_distances) * 3  # scaled
        
        # 3. Pinch gesture (thumb to index distance)
        thumb_tip = pts[4]
        index_tip = pts[8]
        pinch_distance = np.linalg.norm(thumb_tip - index_tip)
        features['pinch'] = 1.0 - min(pinch_distance * 4, 1.0)  # inverted & scaled
        
        # 4. Wrist rotation (roll) - simplified from hand orientation
        wrist = pts[0]
        middle_base = pts[9]
        hand_vector = middle_base - wrist
        features['rotation'] = np.arctan2(hand_vector[0], hand_vector[1]) / np.pi
        
        # 5. Individual finger bend (0=straight, 1=bent) - just index for demo
        index_mcp = pts[5]
        index_pip = pts[6] 
        index_tip = pts[8]
        v1 = index_pip - index_mcp
        v2 = index_tip - index_pip
        cos_angle = np.dot(v1[:2], v2[:2]) / (np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2]))
        features['index_bend'] = (1 - cos_angle) / 2
        
        return features
    
    def smooth_value(self, key, value):
        """Apply moving average smoothing"""
        if key not in self.smoothing_buffers:
            self.smoothing_buffers[key] = deque(maxlen=self.history_size)
        
        self.smoothing_buffers[key].append(value)
        return np.mean(self.smoothing_buffers[key])
    
    def send_features(self, features, hand_id):
        """Send features via OSC with smoothing"""
        
        for feature_name, value in features.items():
            # Apply smoothing
            smoothed_value = self.smooth_value(f"{hand_id}_{feature_name}", value)
            
            # Clamp to 0-1 range
            smoothed_value = np.clip(smoothed_value, 0.0, 1.0)
            
            # Send OSC message
            address = f"/hand/{hand_id}/{feature_name}"
            self.osc_client.send_message(address, float(smoothed_value))
    
    def run(self):
        """Main capture and processing loop"""
        cap = cv2.VideoCapture(0)
        
        print("Starting hand tracking...")
        print("OSC messages being sent to port 7400")
        print("\nOSC addresses:")
        print("  /hand/[0-1]/palm_x    - Palm X position (0-1)")
        print("  /hand/[0-1]/palm_y    - Palm Y position (0-1)")
        print("  /hand/[0-1]/palm_z    - Palm depth (0-1)")
        print("  /hand/[0-1]/openness  - Hand openness (0=fist, 1=open)")
        print("  /hand/[0-1]/pinch     - Pinch amount (0=no pinch, 1=pinched)")
        print("  /hand/[0-1]/rotation  - Wrist rotation (-1 to 1)")
        print("  /hand/[0-1]/index_bend - Index finger bend (0-1)")
        print("\nPress 'q' to quit")
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Flip horizontally for mirror view
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process with MediaPipe
            results = self.hands.process(rgb_frame)
            
            if results.multi_hand_landmarks:
                for hand_id, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # Draw landmarks on frame
                    self.mp_drawing.draw_landmarks(
                        frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    
                    # Calculate and send features
                    features = self.calculate_hand_features(hand_landmarks, hand_id)
                    self.send_features(features, hand_id)
                    
                    # Display feature values on screen
                    y_offset = 30 + (hand_id * 150)
                    for i, (name, value) in enumerate(features.items()):
                        text = f"Hand {hand_id} {name}: {value:.3f}"
                        cv2.putText(frame, text, (10, y_offset + i*20),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            cv2.imshow('Hand Tracking', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="127.0.0.1", help="OSC destination IP")
    parser.add_argument("--port", type=int, default=7400, help="OSC destination port")
    args = parser.parse_args()
    
    tracker = HandToOSC(args.ip, args.port)
    tracker.run()