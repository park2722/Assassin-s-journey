import cv2
import base64
import time
import threading
import os
import camera_connection

# [필수] 본인의 Ngrok 토큰을 입력하세요
NGROK_TOKEN = "3DI3r8yIrtDAyhegv2upug4K5UZ_5occ93smHoaiTrPGzt2JH"

# [추가] 프로그램 실행 상태를 제어하는 전역 변수
is_running = True

def game_loop(socketio, cap_phone):
    global is_running
    print("웹캠을 켜는 중...")
    cap_laptop = cv2.VideoCapture(0)
    
    if not cap_laptop.isOpened():
        print("노트북 웹캠을 열 수 없습니다!")
        return

    print("게임 루프 가동 완료. 대시보드를 띄워주세요.")

    # [수정] 무한 루프 대신 is_running 변수로 제어합니다.
    while is_running:
        ret_laptop, frame_laptop = cap_laptop.read()
        ret_phone, frame_phone = cap_phone.read()

        laptop_b64 = None
        phone_b64 = None

        try:
            if ret_laptop and frame_laptop is not None and getattr(frame_laptop, 'size', 0) > 0:
                ret, buffer = cv2.imencode('.jpg', frame_laptop, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    laptop_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')

            if ret_phone and frame_phone is not None and getattr(frame_phone, 'size', 0) > 0:
                ret, buffer = cv2.imencode('.jpg', frame_phone, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    phone_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
                    
        except Exception as e:
            print(f"[OpenCV 변환 에러 방어 작동] {e}")
            time.sleep(0.01)
            continue

        socketio.emit('update_dashboard', {
            'laptop_img': laptop_b64,
            'phone_img': phone_b64
        })

        time.sleep(0.03) 

    # ====================================================================
    # --- while 루프가 끝나면(is_running이 False가 되면) 실행되는 종료 처리 ---
    # ====================================================================
    print("\n[시스템] 카메라 자원을 안전하게 해제합니다...")
    
    # 객체가 튜플로 덮어씌워졌거나 비어있을 경우를 대비해, 
    # 'release' 기능이 살아있는지(hasattr) 확인하고 안전하게 해제합니다.
    if hasattr(cap_laptop, 'release'):
        cap_laptop.release()
        
    if hasattr(cap_phone, 'release'):
        cap_phone.release()
        
    print("[시스템] 서버가 완전히 종료되었습니다. 안녕히 가세요!")
    
    # Flask 서버 프로세스를 강제로 깔끔하게 종료
    os._exit(0)

if __name__ == "__main__":
    if NGROK_TOKEN != "3DI3r8yIrtDAyhegv2upug4K5UZ_5occ93smHoaiTrPGzt2JH":
        print("NGROK 토큰을 입력해주세요!")
        exit()

    app, socketio, cap_phone = camera_connection.create_app(NGROK_TOKEN)

    # [추가] 웹 대시보드에서 종료 버튼을 눌렀을 때 실행되는 이벤트
    @socketio.on('shutdown_server')
    def handle_shutdown():
        global is_running
        print("\n🚨 [알림] 대시보드에서 시스템 종료 요청이 들어왔습니다.")
        is_running = False

    loop_thread = threading.Thread(target=game_loop, args=(socketio, cap_phone))
    loop_thread.daemon = True
    loop_thread.start()

    print("웹 서버 구동 시작...")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)