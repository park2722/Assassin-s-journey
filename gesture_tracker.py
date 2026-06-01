import cv2
import mediapipe as mp

class GestureTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils
        
        # 🆕 [추가] 이전 프레임의 제스처 상태를 기억하는 변수
        self.last_gesture = "None" 

    def process_frame(self, frame_laptop):
        gesture_text = "None"
        angle_delta = 0.0
        current_gesture = "None" # 현재 프레임에서 인식된 순수 손 모양

        # 거울 모드(좌우 반전)
        frame_laptop = cv2.flip(frame_laptop, 1) 
        
        rgb_laptop = cv2.cvtColor(frame_laptop, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_laptop)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(frame_laptop, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                index_tip_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP].x
                index_mcp_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP].x
                
                # 순수하게 현재 손이 어느 쪽으로 꺾여 있는지 판별
                if index_tip_x < index_mcp_x - 0.05:
                    current_gesture = "Left Swipe"
                elif index_tip_x > index_mcp_x + 0.05:
                    current_gesture = "Right Swipe"
        
        # 🔄 [핵심 로직] 이전 프레임이 "None"이었고, 지금 "Swipe"일 때만 90도 각도를 줍니다 (1회성 트리거)
        if current_gesture == "Left Swipe" and self.last_gesture == "None":
            angle_delta = 90.0 # 한 번에 90도 회전
            gesture_text = "Turn Left"
        elif current_gesture == "Right Swipe" and self.last_gesture == "None":
            angle_delta = -90.0 # 한 번에 90도 회전
            gesture_text = "Turn Right"
        else:
            # 트리거가 발생하지 않은 평상시에는 현재 손 모양만 텍스트로 띄워줍니다.
            gesture_text = current_gesture 

        # 🆕 다음 프레임 비교를 위해 현재 상태를 저장
        self.last_gesture = current_gesture

        # 상태 출력
        cv2.putText(frame_laptop, f"Action: {gesture_text}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

        return frame_laptop, angle_delta, gesture_text

    def close(self):
        if hasattr(self, 'hands'):
            self.hands.close()