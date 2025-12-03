import cv2 as cv
import mediapipe as mp
import numpy as np
import time
import os
from pathlib import Path
from collections import deque
import MaxShowmotion

def precheck():
    cam = cv.VideoCapture(0)
    if not cam.isOpened():
        raise RuntimeError("Could not open camera")
    root = Path(__file__).resolve().parents[2]
    model_path = root / 'V1.X.X' / 'Ableton' / 'gesture_recognizer.task'
    if not os.path.exists(model_path):
        raise RuntimeError("Could not find gesture_recognizer.task")
    return model_path, cam

class HandFeatureTracker:
    def __init__(self, history_size=3):
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5)
        self.drawer = mp.solutions.drawing_utils
        self.history_size = history_size
        self.buffers = {}

    def close(self):
        self.hands.close()

    def _smooth(self, key, value):
        if key not in self.buffers:
            self.buffers[key] = deque(maxlen=self.history_size)
        self.buffers[key].append(value)
        return np.mean(self.buffers[key])

    def _feature_list(self, pts):
        palm_indices = [0, 1, 5, 9, 13, 17]
        palm_center = pts[palm_indices].mean(axis=0)
        fingertip_indices = [4, 8, 12, 16, 20]
        fingertip_distances = [np.linalg.norm(pts[i][:2] - palm_center[:2]) for i in fingertip_indices]
        thumb_tip = pts[4]
        index_tip = pts[8]
        wrist = pts[0]
        middle_base = pts[9]
        hand_vector = middle_base - wrist
        index_mcp = pts[5]
        index_pip = pts[6]
        index_tip = pts[8]
        v1 = index_pip - index_mcp
        v2 = index_tip - index_pip
        cos_angle = np.dot(v1[:2], v2[:2]) / (np.linalg.norm(v1[:2]) * np.linalg.norm(v2[:2]))
        return [
            ("palm_x", float(palm_center[0])),
            ("palm_y", float(palm_center[1])),
            ("palm_z", float(palm_center[2])),
            ("openness", float(np.mean(fingertip_distances) * 3)),
            ("pinch", float(1.0 - min(np.linalg.norm(thumb_tip - index_tip) * 4, 1.0))),
            ("rotation", float(np.arctan2(hand_vector[0], hand_vector[1]) / np.pi)),
            ("index_bend", float((1 - cos_angle) / 2))
        ]

    def describe(self, frame, hand_results):
        annotated = []
        if not hand_results.multi_hand_landmarks:
            return annotated
        handedness_list = []
        if hand_results.multi_handedness:
            handedness_list = [h.classification[0].label for h in hand_results.multi_handedness]
        for hand_id, hand_landmarks in enumerate(hand_results.multi_hand_landmarks):
            self.drawer.draw_landmarks(frame, hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)
            pts = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])
            hand_values = []
            for name, raw_value in self._feature_list(pts):
                smoothed = self._smooth(f"{hand_id}_{name}", raw_value)
                if name == 'palm_z':
                    smoothed = float(smoothed)
                else:
                    smoothed = float(np.clip(smoothed, 0.0, 1.0))
                hand_values.append((name, smoothed))
            label = handedness_list[hand_id] if hand_id < len(handedness_list) else "Unknown"
            annotated.append((hand_id, label, hand_values))
        return annotated

def main(data_callback=None):
    model_path, camera = precheck()
    tracker = HandFeatureTracker()
    stream_server = MaxShowmotion.StreamingServer(port=8080, use_virtual_cam=True)
    stream_server.start()

    BaseOptions = mp.tasks.BaseOptions
    GestureRecognizer = mp.tasks.vision.GestureRecognizer
    GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
    GestureRecognizerResult = mp.tasks.vision.GestureRecognizerResult
    VisionRunningMode = mp.tasks.vision.RunningMode

    gesture_log = {}

    def handle_result(result: GestureRecognizerResult, _image: mp.Image, timestamp_ms: int):
        gesture_log.clear()
        if not result.gestures:
            return
        for hand_index, gesture_list in enumerate(result.gestures):
            if not gesture_list:
                continue
            top = gesture_list[0]
            gesture_log[hand_index] = (top.category_name, float(top.score), timestamp_ms)

    options = GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=VisionRunningMode.LIVE_STREAM,
        result_callback=handle_result)

    with GestureRecognizer.create_from_options(options) as recognizer:
        while True:
            ret, frame = camera.read()
            if not ret:
                break

            display_frame = cv.flip(frame, 1)
            rgb_frame = cv.cvtColor(display_frame, cv.COLOR_BGR2RGB)
            hand_results = tracker.hands.process(rgb_frame)
            hand_data = tracker.describe(display_frame, hand_results)

            if data_callback:
                for hand_id, hand_label, features in hand_data:
                    gesture_info = None
                    if hand_id in gesture_log:
                        gesture_name, score, _ts = gesture_log[hand_id]
                        gesture_info = {
                            'hand': hand_label,
                            'gesture': gesture_name,
                            'score': score
                        }
                    features_dict = dict(features)
                    data_callback({
                        'hand_id': hand_id,
                        'hand_label': hand_label,
                        'coordinates': features_dict,
                        'gesture': gesture_info
                    })

            try:
                import motiontask
                if "both" in motiontask.current_motion:
                    motion_text = motiontask.current_motion["both"]
                    (text_width, text_height), baseline = cv.getTextSize(motion_text, cv.FONT_HERSHEY_SIMPLEX, 1.0, 3)
                    cv.rectangle(display_frame, (15 - 5, 20 - text_height - 10), 
                                (15 + text_width + 5, 20 + 5), (200, 0, 0), -1)
                    cv.putText(display_frame, motion_text, (15, 20),
                               cv.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
                elif "left" in motiontask.current_motion:
                    motion_text = motiontask.current_motion["left"]
                    (text_width, text_height), baseline = cv.getTextSize(motion_text, cv.FONT_HERSHEY_SIMPLEX, 1.0, 3)
                    cv.rectangle(display_frame, (15 - 5, 20 - text_height - 10), 
                                (15 + text_width + 5, 20 + 5), (0, 200, 0), -1)
                    cv.putText(display_frame, motion_text, (15, 20),
                               cv.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
                elif "right" in motiontask.current_motion:
                    motion_text = motiontask.current_motion["right"]
                    (text_width, text_height), baseline = cv.getTextSize(motion_text, cv.FONT_HERSHEY_SIMPLEX, 1.0, 3)
                    cv.rectangle(display_frame, (15 - 5, 20 - text_height - 10), 
                                (15 + text_width + 5, 20 + 5), (200, 100, 0), -1)
                    cv.putText(display_frame, motion_text, (15, 20),
                               cv.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
            except:
                pass
            
            for hand_id, hand_label, features in hand_data:
                base_y = 60 + hand_id * 280
                x_offset = 15
                
                try:
                    import motiontask
                    if hand_id in motiontask.current_motion:
                        motion_text = motiontask.current_motion[hand_id]
                        (text_width, text_height), baseline = cv.getTextSize(motion_text, cv.FONT_HERSHEY_SIMPLEX, 0.9, 3)
                        cv.rectangle(display_frame, (x_offset - 5, base_y - text_height - 10), 
                                    (x_offset + text_width + 5, base_y + 5), (0, 100, 200), -1)
                        cv.putText(display_frame, motion_text, (x_offset, base_y),
                                   cv.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3)
                        base_y += 40
                except:
                    pass
                
                if hand_id in gesture_log:
                    gesture, score, _ts = gesture_log[hand_id]
                    gesture_text = f"{hand_label} Hand - {gesture} ({score:.2f})"
                    (text_width, text_height), baseline = cv.getTextSize(gesture_text, cv.FONT_HERSHEY_SIMPLEX, 1.0, 3)
                    cv.rectangle(display_frame, (x_offset - 5, base_y - text_height - 10), 
                                (x_offset + text_width + 5, base_y + 5), (0, 0, 0), -1)
                    cv.putText(display_frame, gesture_text, (x_offset, base_y),
                               cv.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 3)
                    base_y += 35
                
                header_text = f"Hand {hand_id} ({hand_label}) Coordinates:"
                (text_width, _), _ = cv.getTextSize(header_text, cv.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv.rectangle(display_frame, (x_offset - 5, base_y - 20), 
                            (x_offset + text_width + 5, base_y + 5), (20, 20, 20), -1)
                cv.putText(display_frame, header_text, (x_offset, base_y),
                           cv.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
                base_y += 30
                
                for idx, (name, value) in enumerate(features):
                    if name == 'palm_z':
                        text = f"  {name:12s}: {value:7.3f}"
                    else:
                        text = f"  {name:12s}: {value:6.3f}"
                    cv.putText(display_frame, text, (x_offset, base_y + idx * 35),
                               cv.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 100), 2)

            # Update stream server for OBS (no window display)
            stream_server.update_frame(display_frame)

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            recognizer.recognize_async(mp_image, int(time.time() * 1000))

            # Small delay to prevent excessive CPU usage
            time.sleep(0.033)  # ~30 FPS

    stream_server.stop()
    camera.release()
    tracker.close()
    # No windows to destroy since we're only streaming to OBS

if __name__ == "__main__":
    main()
