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
        self.last_wrist_y = None # 🆕 손목의 Y좌표 변화를 추적하기 위한 변수

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
                
                # 🆕 손목(0번 랜드마크)의 Y좌표를 가져옵니다.
                wrist_y = hand_landmarks.landmark[0].y
                
                # 🆕 Down Swipe 판별: 이전 프레임보다 손목이 0.1 이상(빠르게) 아래로 내려갔는지 확인
                is_swipe_down = False
                if self.last_wrist_y is not None:
                    if wrist_y - self.last_wrist_y > 0.1:
                        is_swipe_down = True
                self.last_wrist_y = wrist_y # 다음 프레임 비교를 위해 저장
                
                # 주먹 판별 (손바닥을 카메라 정면으로 보인 상태에서만 작동하도록 Y좌표 차이를 넉넉하게 줌)
                is_fist = True
                for tip, mcp in [(8, 5), (12, 9), (16, 13), (20, 17)]:
                    if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[mcp].y + 0.02:
                        is_fist = False 
                        break
                
                # 💡 우선순위: 아래로 내리는 움직임이 가장 먼저 감지되도록 설정
                if is_swipe_down:
                    current_gesture = "Down Swipe"
                elif is_fist:
                    current_gesture = "Fist"
                elif index_tip_x < index_mcp_x - 0.05:
                    current_gesture = "Left Swipe"
                elif index_tip_x > index_mcp_x + 0.05:
                    current_gesture = "Right Swipe"
        else:
            self.last_wrist_y = None # 손이 화면 밖으로 나가면 리셋
        
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
            elif current_gesture == "Down Swipe": # 💡 연속 동작이므로 last_gesture "None" 조건 제외
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