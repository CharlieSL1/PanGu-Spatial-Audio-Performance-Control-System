import GetMediaPipe
from collections import deque
import time

hand_history = {}
hand_labels = {}
hand_gestures = {}
last_action_time = {}
current_motion = {}
osc_callback = None

def detect_swipe(hand_id, hand_label, palm_x, palm_y):
    if hand_id not in hand_history:
        hand_history[hand_id] = deque(maxlen=10)
    
    hand_labels[hand_id] = hand_label
    hand_history[hand_id].append((palm_x, palm_y))
    
    if len(hand_history[hand_id]) < 5:
        return None
    
    positions = list(hand_history[hand_id])
    start_x, start_y = positions[0]
    end_x, end_y = positions[-1]
    
    dx = end_x - start_x
    dy = end_y - start_y
    
    if abs(dx) > abs(dy) * 1.8:
        if hand_label == "Left" and start_x < 0.45 and end_x > 0.55 and dx > 0.25:
            return "right_track"
        elif hand_label == "Right" and start_x > 0.55 and end_x < 0.45 and dx < -0.25:
            return "left_track"
    elif abs(dy) > abs(dx) * 2.0:
        if dy < -0.22:
            return "up"
        elif dy > 0.22:
            return "down"
    
    return None

def check_left_hand_gesture():
    for hand_id in hand_history:
        if hand_id not in hand_labels:
            continue
        if hand_id not in hand_gestures:
            continue
        
        hand_label = hand_labels[hand_id]
        if hand_label == "Left":
            gesture_name = hand_gestures[hand_id]
            if gesture_name == "Thumb_Up" or gesture_name == "Thumbs_Up":
                return "up_scene"
            elif gesture_name == "Thumb_Down" or gesture_name == "Thumbs_Down":
                return "down_scene"
    
    return None

def check_right_hand_gesture():
    for hand_id in hand_history:
        if hand_id not in hand_labels:
            continue
        if hand_id not in hand_gestures:
            continue
        
        hand_label = hand_labels[hand_id]
        if hand_label == "Right":
            gesture_name = hand_gestures[hand_id]
            if gesture_name == "Victory":
                return "fire_clip"
            elif gesture_name == "Pointing_Up":
                return "fire_scene"
    
    return None

def check_both_hands_holding():
    if len(hand_gestures) < 2:
        return None
    
    holding_count = 0
    for hand_id in hand_gestures:
        gesture_name = hand_gestures[hand_id]
        if gesture_name == "Closed_Fist" or gesture_name == "Open_Palm":
            holding_count += 1
    
    if holding_count >= 2:
        return "master_track"
    return None

def process_hand_data(data):
    hand_id = data['hand_id']
    hand_label = data['hand_label']
    coordinates = data['coordinates']
    gesture = data.get('gesture')
    
    palm_x = coordinates.get('palm_x', 0.5)
    palm_y = coordinates.get('palm_y', 0.5)
    
    if gesture:
        hand_gestures[hand_id] = gesture['gesture']
    
    swipe = detect_swipe(hand_id, hand_label, palm_x, palm_y)
    
    current_time = time.time()
    
    if swipe in ["right_track", "left_track"]:
        if hand_id not in last_action_time or current_time - last_action_time[hand_id] > 2.5:
            last_action_time[hand_id] = current_time
            hand_history[hand_id].clear()
            
            if swipe == "right_track":
                current_motion[hand_id] = "Select right track"
                print(f"Hand {hand_id} ({hand_label}): Select right track")
                if osc_callback:
                    osc_callback("right_track", hand_id)
            elif swipe == "left_track":
                current_motion[hand_id] = "Select left track"
                print(f"Hand {hand_id} ({hand_label}): Select left track")
                if osc_callback:
                    osc_callback("left_track", hand_id)
    
    left_gesture = check_left_hand_gesture()
    if left_gesture:
        if "left_gesture" not in last_action_time or current_time - last_action_time["left_gesture"] > 1.5:
            last_action_time["left_gesture"] = current_time
            
            if left_gesture == "up_scene":
                current_motion["left"] = "Select up scene"
                print("Left Thumb_Up: Select up scene")
                if osc_callback:
                    osc_callback("up_scene", None)
            elif left_gesture == "down_scene":
                current_motion["left"] = "Select down scene"
                print("Left Thumb_Down: Select down scene")
                if osc_callback:
                    osc_callback("down_scene", None)
    
    right_gesture = check_right_hand_gesture()
    if right_gesture:
        if "right_gesture" not in last_action_time or current_time - last_action_time["right_gesture"] > 1.5:
            last_action_time["right_gesture"] = current_time
            
            if right_gesture == "fire_clip":
                current_motion["right"] = "Fire/Stop Clip Slot"
                print("Right Victory: Fire/Stop Clip Slot")
                if osc_callback:
                    osc_callback("fire_clip", None)
            elif right_gesture == "fire_scene":
                current_motion["right"] = "Fire/Stop Scene"
                print("Right Pointing_Up: Fire/Stop Scene")
                if osc_callback:
                    osc_callback("fire_scene", None)
    
    both_holding = check_both_hands_holding()
    if both_holding:
        if "both_holding" not in last_action_time or current_time - last_action_time["both_holding"] > 2.0:
            last_action_time["both_holding"] = current_time
            current_motion["both"] = "Choose MasterTrack"
            print("Both hands holding: Choose MasterTrack")
            if osc_callback:
                osc_callback("master_track", None)
    
    if hand_id in current_motion:
        if time.time() - last_action_time.get(hand_id, 0) > 2.5:
            current_motion.pop(hand_id, None)
    if "left" in current_motion:
        if time.time() - last_action_time.get("left_gesture", 0) > 1.5:
            current_motion.pop("left", None)
    if "right" in current_motion:
        if time.time() - last_action_time.get("right_gesture", 0) > 1.5:
            current_motion.pop("right", None)
    if "both" in current_motion:
        if time.time() - last_action_time.get("both_holding", 0) > 2.0:
            current_motion.pop("both", None)

def set_osc_callback(callback):
    global osc_callback
    osc_callback = callback

if __name__ == "__main__":
    GetMediaPipe.main(data_callback=process_hand_data)