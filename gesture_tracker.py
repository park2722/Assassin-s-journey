import cv2
import mediapipe as mp
import time  # 🆕 시간 측정을 위해 추가

class GestureTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils
        
        self.last_gesture = "None" 
        
        # 🆕 [추가] 쿨다운(대기 시간) 시스템
        self.last_action_time = 0.0
        self.cooldown = 0.8  # 0.8초 동안은 아무리 손을 흔들어도 추가 입력을 철벽 방어! (필요에 따라 0.5, 1.0 등으로 조절)

    def process_frame(self, frame_laptop):
        gesture_text = "None"
        angle_delta = 0.0
        current_gesture = "None"

        # 거울 모드(좌우 반전)
        frame_laptop = cv2.flip(frame_laptop, 1) 
        
        rgb_laptop = cv2.cvtColor(frame_laptop, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_laptop)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(frame_laptop, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                index_tip_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP].x
                index_mcp_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP].x
                
                # 🆕 ✊ 주먹 쥐기 판별: 4개 손가락 끝이 마디보다 아래(Y값이 큼)에 있는지 확인
                is_fist = True
                for tip, mcp in [(8, 5), (12, 9), (16, 13), (20, 17)]:
                    if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[mcp].y:
                        is_fist = False # 하나라도 펴져있으면 주먹이 아님
                        break
                
                if is_fist:
                    current_gesture = "Fist"
                elif index_tip_x < index_mcp_x - 0.05:
                    current_gesture = "Left Swipe"
                elif index_tip_x > index_mcp_x + 0.05:
                    current_gesture = "Right Swipe"
        
        # 🆕 현재 시간을 가져와서 쿨다운 적용
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
            # 🚀 [추가] 주먹을 쥐었을 때 전진 명령 하달!
            elif current_gesture == "Fist" and self.last_gesture == "None":
                gesture_text = "Forward"  
                self.last_action_time = current_time
            else:
                gesture_text = current_gesture 
        else:
            gesture_text = "Wait..."

        self.last_gesture = current_gesture

        # 상태 출력
        cv2.putText(frame_laptop, f"Action: {gesture_text}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

        return frame_laptop, angle_delta, gesture_text

    def close(self):
        if hasattr(self, 'hands'):
            self.hands.close()