import cv2
import mediapipe as mp

class GestureTracker:
    def __init__(self):
        # 🆕 MediaPipe 손 인식 모듈 초기화
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils

    def process_frame(self, frame_laptop):
        gesture_text = "None"
        angle_delta = 0.0

        # 거울 모드(좌우 반전)
        frame_laptop = cv2.flip(frame_laptop, 1) 
        
        # 💡 MediaPipe는 RGB 색상을 사용하므로 BGR에서 변환해줍니다.
        rgb_laptop = cv2.cvtColor(frame_laptop, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_laptop)
        
        # 💡 화면에 손이 인식되었다면
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 손가락 관절과 뼈대를 화면에 그립니다.
                self.mp_draw.draw_landmarks(frame_laptop, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                # 검지손가락 끝(TIP)과 검지 뿌리(MCP)의 X 좌표를 추출하여 방향 계산
                index_tip_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP].x
                index_mcp_x = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP].x
                
                # 끝부분이 뿌리보다 확실히 왼쪽(-0.05)에 있으면 Left
                if index_tip_x < index_mcp_x - 0.05:
                    gesture_text = "Left Swipe"
                    angle_delta = 5.0 # 왼쪽으로 회전
                elif index_tip_x > index_mcp_x + 0.05:
                    gesture_text = "Right Swipe"
                    angle_delta = -5.0 # 오른쪽으로 회전
        
        # 인식된 제스처 상태를 노트북 화면 좌측 상단에 띄워줍니다.
        cv2.putText(frame_laptop, f"Action: {gesture_text}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

        return frame_laptop, angle_delta, gesture_text

    def close(self):
        if hasattr(self, 'hands'):
            self.hands.close()