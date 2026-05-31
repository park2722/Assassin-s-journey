import cv2
import base64
import time
import threading
import os
import gc
import camera_connection

# 각 기능 모듈 Import
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

    # 전담 클래스들 소환
    tracker = GestureTracker()
    ar_engine = AREngine(viewport_width=640, viewport_height=480)

    print("게임 루프 가동 완료. 대시보드를 띄워주세요.")

    while is_running:
        ret_laptop, frame_laptop = cap_laptop.read()
        ret_phone, frame_phone = cap_phone.read()

        laptop_b64 = None
        phone_b64 = None

        try:
            # 1. 노트북 영상 -> AI 제스처 팀
            if ret_laptop and frame_laptop is not None and getattr(frame_laptop, 'size', 0) > 0:
                frame_laptop, angle_delta, _ = tracker.process_frame(frame_laptop)
                ret, buffer = cv2.imencode('.jpg', frame_laptop, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret: laptop_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
            else:
                angle_delta = 0.0

            # 2. 폰 영상 + 각도 변화량 -> AR 엔진 팀
            if ret_phone and frame_phone is not None and getattr(frame_phone, 'size', 0) > 0:
                frame_phone = ar_engine.render(frame_phone, angle_delta)
                
                send_frame = cv2.resize(frame_phone, (640, 480)) 
                ret, buffer = cv2.imencode('.jpg', send_frame, [cv2.IMWRITE_JPEG_QUALITY, 50]) 
                if ret: phone_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
                    
        except Exception as e:
            print(f"[렌더링 에러 방어] {e}")
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