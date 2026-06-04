import cv2
import mediapipe as mp
import time

class GestureTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils
        
        self.last_gesture = "None" 
        self.last_action_time = 0.0
        self.cooldown = 0.8  
        self.y_history = [] 

    def process_frame(self, frame_laptop):
        gesture_text = "None"
        angle_delta = 0.0
        current_gesture = "None"

        frame_laptop = cv2.flip(frame_laptop, 1) 
        rgb_laptop = cv2.cvtColor(frame_laptop, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_laptop)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(frame_laptop, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                index_tip_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP].x
                index_mcp_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP].x
                
                wrist_y = hand_landmarks.landmark[0].y
                self.y_history.append(wrist_y)
                if len(self.y_history) > 10:
                    self.y_history.pop(0)
                
                is_swipe_down = False
                if len(self.y_history) >= 5: 
                    if wrist_y - self.y_history[0] > 0.15:
                        is_swipe_down = True
                        self.y_history.clear() 
                
                # 🚀 [완벽한 주먹 판별법] 손가락 끝과 마디 사이의 거리를 계산합니다!
                # 손을 어떻게 눕히든, 거리가 0.08 이내로 좁혀지면 무조건 주먹으로 인정합니다.
                is_fist = True
                for tip, mcp in [(8, 5), (12, 9), (16, 13), (20, 17)]:
                    dist = ((hand_landmarks.landmark[tip].x - hand_landmarks.landmark[mcp].x)**2 + 
                            (hand_landmarks.landmark[tip].y - hand_landmarks.landmark[mcp].y)**2)**0.5
                    if dist > 0.08: 
                        is_fist = False 
                        break
                
                if is_swipe_down:
                    current_gesture = "Down Swipe"
                elif is_fist:
                    current_gesture = "Fist"
                elif index_tip_x < index_mcp_x - 0.05:
                    current_gesture = "Left Swipe"
                elif index_tip_x > index_mcp_x + 0.05:
                    current_gesture = "Right Swipe"
        else:
            self.y_history.clear() 
        
        current_time = time.time()

        if current_time - self.last_action_time > self.cooldown:
            if current_gesture == "Left Swipe" and self.last_gesture == "None":
                angle_delta = 90.0 
                gesture_text = "Turn Left"
                self.last_action_time = current_time
            elif current_gesture == "Right Swipe" and self.last_gesture == "None":
                angle_delta = -90.0 
                gesture_text = "Turn Right"
                self.last_action_time = current_time
            elif current_gesture == "Fist" and self.last_gesture == "None":
                gesture_text = "Forward"  
                self.last_action_time = current_time
            elif current_gesture == "Down Swipe": 
                gesture_text = "Flee"
                self.last_action_time = current_time
            else:
                gesture_text = current_gesture 
        else:
            gesture_text = "Wait..."

        self.last_gesture = current_gesture

        cv2.putText(frame_laptop, f"Action: {gesture_text}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        return frame_laptop, angle_delta, gesture_text

    def close(self):
        if hasattr(self, 'hands'):
            self.hands.close()