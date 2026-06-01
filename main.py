import cv2
import base64
import time
import threading
import os
import gc
import random  # 🆕 필수 추가
import camera_connection

from gesture_tracker import GestureTracker
from ar_engine import AREngine

NGROK_TOKEN = "3EV7caK2Yup09RnuASEhU384L4r_7sy9tn88DH3rMjF88514" 
is_running = True

def game_loop(socketio, cap_phone):
    global is_running
    print("웹캠을 켜는 중...")
    cap_laptop = cv2.VideoCapture(0)
    
    if not cap_laptop.isOpened():
        print("노트북 웹캠을 열 수 없습니다!")
        return

    tracker = GestureTracker()
    ar_engine = AREngine(viewport_width=640, viewport_height=480)

    # 🚨 [매우 중요] 반드시 while 루프 '바깥'에 있어야 합니다! 
    char_pos = [4, 5] 
    char_dir = 0 
    bushes = set()
    event_msg = "Game Started" # 🆕 화면에 띄울 이벤트 텍스트

    # 부쉬 10개 랜덤 생성
    while len(bushes) < 10:
        bx = random.randint(1, 6)
        by = random.randint(1, 4)
        if [bx, by] != char_pos:  
            bushes.add((bx, by))

    print("게임 루프 가동 완료. 대시보드를 띄워주세요.")

    while is_running:
        ret_laptop, frame_laptop = cap_laptop.read()
        ret_phone, frame_phone = cap_phone.read()

        laptop_b64 = None
        phone_b64 = None

        try:
            # 1. 노트북 영상 -> AI 제스처 팀
            if ret_laptop and frame_laptop is not None and getattr(frame_laptop, 'size', 0) > 0:
                frame_laptop, angle_delta, gesture = tracker.process_frame(frame_laptop)
                
                # 💡 캐릭터 이동 및 방향 상태 관리
                if gesture == "Turn Left":
                    char_dir = (char_dir - 1) % 4
                    event_msg = "Turned Left"
                elif gesture == "Turn Right":
                    char_dir = (char_dir + 1) % 4
                    event_msg = "Turned Right"
                elif gesture == "Forward":
                    dx, dy = 0, 0
                    if char_dir == 0: dx = 1    # (기존: 위쪽) -> 이제 캐릭터가 보는 정면(오른쪽)으로 전진!
                    elif char_dir == 1: dy = 1  # (기존: 오른쪽) -> 아래쪽
                    elif char_dir == 2: dx = -1 # (기존: 아래쪽) -> 왼쪽
                    elif char_dir == 3: dy = -1 # (기존: 왼쪽) -> 위쪽
                    
                    nx, ny = char_pos[0] + dx, char_pos[1] + dy
                    
                    # 체스보드 경계(8x6) 밖으로 나가지 못하게 방어
                    if 0 <= nx <= 7 and 0 <= ny <= 5:
                        char_pos = [nx, ny]
                        event_msg = f"Moved to [{nx}, {ny}]"
                        print(f"🚶 이동 완료: {char_pos}", flush=True) # flush=True로 터미널 강제 출력
                        
                        # 🌿 조우 판정
                        if tuple(char_pos) in bushes:
                            if random.random() < 0.5: 
                                event_msg = "Creature Appeared!!"
                                print("⚡ 앗! 야생의 크리처가 튀어나왔다!!", flush=True)
                            else:
                                event_msg = "Nothing happened."
                                print("바스락... 다행히 아무 일도 일어나지 않았다.", flush=True)
                    else:
                        event_msg = "Blocked by boundary!"

                # 🆕 이벤트 메시지를 노트북 화면에 직접 띄워줍니다.
                cv2.putText(frame_laptop, event_msg, (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)

                ret, buffer = cv2.imencode('.jpg', frame_laptop, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret: laptop_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
            else:
                angle_delta = 0.0

            # 2. 폰 영상 + 각도 변화량 -> AR 엔진 팀
            if ret_phone and frame_phone is not None and getattr(frame_phone, 'size', 0) > 0:
                frame_phone = ar_engine.render(frame_phone, angle_delta, char_pos, bushes)
                
                send_frame = cv2.resize(frame_phone, (640, 480)) 
                ret, buffer = cv2.imencode('.jpg', send_frame, [cv2.IMWRITE_JPEG_QUALITY, 50]) 
                if ret: phone_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
                    
        except Exception as e:
            print(f"[렌더링 에러 방어] {e}", flush=True)
            time.sleep(0.01)
            continue

        # 3. 결과물 웹소켓 전송
        socketio.emit('update_dashboard', {
            'laptop_img': laptop_b64,
            'phone_img': phone_b64
        })

        time.sleep(0.05) 
        gc.collect()

    print("\n[시스템] 카메라 자원을 안전하게 해제합니다...")
    if hasattr(cap_laptop, 'release'): cap_laptop.release()
    if hasattr(cap_phone, 'release'): cap_phone.release()
    tracker.close()
    ar_engine.close()
    os._exit(0)

if __name__ == "__main__":
    if NGROK_TOKEN == "여기에_본인의_토큰_입력":
        print("🚨 NGROK 토큰을 입력해주세요!")
        exit()

    app, socketio, cap_phone = camera_connection.create_app(NGROK_TOKEN)

    @socketio.on('shutdown_server')
    def handle_shutdown():
        global is_running
        is_running = False

    loop_thread = threading.Thread(target=game_loop, args=(socketio, cap_phone))
    loop_thread.daemon = True
    loop_thread.start()

    print("웹 서버 구동 시작...")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)