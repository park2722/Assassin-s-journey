import cv2
import base64
import time
import threading
import os
import gc
import random 
import camera_connection

from gesture_tracker import GestureTracker
from ar_engine import AREngine

NGROK_TOKEN = "3EV7caK2Yup09RnuASEhU384L4r_7sy9tn88DH3rMjF88514" 
is_running = True

def game_loop(socketio, cap_phone):
    global is_running
    print("웹캠을 켜는 중...", flush=True)
    cap_laptop = cv2.VideoCapture(0)
    tracker = GestureTracker()
    ar_engine = AREngine(viewport_width=640, viewport_height=480)

    game_state = "EXPLORE" 
    char_pos = [4, 5] 
    prev_pos = [4, 5]      
    char_dir = 0 
    creature_hp = 2        
    current_creature_idx = 0

    bushes = set()
    event_msg = "Game Started" 

    bushes.add((5, 5))
    bushes.add((4, 4))
    
    while len(bushes) < 10:
        bx = random.randint(1, 6)
        by = random.randint(1, 4)
        if [bx, by] != char_pos:  
            bushes.add((bx, by))

    print("게임 루프 가동 완료. 대시보드를 띄워주세요.", flush=True)

    while is_running:
        ret_laptop, frame_laptop = cap_laptop.read()
        ret_phone, frame_phone = cap_phone.read()
        laptop_b64, phone_b64 = None, None

        try:
            if ret_laptop and frame_laptop is not None:
                frame_laptop, _, gesture = tracker.process_frame(frame_laptop)
                
                if game_state == "EXPLORE":
                    if gesture == "Turn Left":
                        char_dir = (char_dir - 1) % 4
                        event_msg = "Turned Left"
                    elif gesture == "Turn Right":
                        char_dir = (char_dir + 1) % 4
                        event_msg = "Turned Right"
                    elif gesture == "Forward":
                        dx, dy = 0, 0
                        if char_dir == 0: dx = 1    
                        elif char_dir == 1: dy = 1  
                        elif char_dir == 2: dx = -1 
                        elif char_dir == 3: dy = -1 
                        
                        nx, ny = char_pos[0] + dx, char_pos[1] + dy
                        if 0 <= nx <= 7 and 0 <= ny <= 5:
                            prev_pos = char_pos.copy() 
                            char_pos = [nx, ny]
                            event_msg = f"Moved to [{nx}, {ny}]"
                            
                            if tuple(char_pos) in bushes:
                                # 💡 아직 빠른 테스트를 위해 1.0(100%)로 두겠습니다.
                                if random.random() < 1.0: 
                                    game_state = "BATTLE"
                                    creature_hp = 2
                                    # 🆕 0~2 사이의 랜덤한 크리처 인덱스 뽑기
                                    current_creature_idx = random.randint(0, 2) 
                                    
                                    event_msg = f"BATTLE! Creature {current_creature_idx + 1} Appeared!"
                                    print(f"⚡ 앗! 야생의 크리처 {current_creature_idx + 1}가 튀어나왔다!!", flush=True)

                elif game_state == "BATTLE":
                    if gesture == "Forward": 
                        event_msg = "Gotcha! Caught it!"
                        bushes.remove(tuple(char_pos))
                        game_state = "EXPLORE"
                        print("✨ 몬스터를 포획했습니다!", flush=True)
                        
                    elif gesture in ["Turn Left", "Turn Right"]: 
                        creature_hp -= 1
                        if creature_hp > 0:
                            event_msg = f"Hit! Creature HP: {creature_hp}"
                        else:
                            event_msg = "Defeated the Creature!"
                            bushes.remove(tuple(char_pos))
                            game_state = "EXPLORE"
                            print("💥 몬스터를 쓰러뜨렸습니다!", flush=True)
                            
                    elif gesture == "Flee": 
                        event_msg = "Ran away!"
                        char_pos = prev_pos.copy() 
                        game_state = "EXPLORE"
                        print("💨 무사히 도망쳤습니다.", flush=True)

                cv2.putText(frame_laptop, f"State: {game_state}", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 3)
                cv2.putText(frame_laptop, event_msg, (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)

                ret, buffer = cv2.imencode('.jpg', frame_laptop, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret: laptop_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
            else:
                angle_delta = 0.0

            if ret_phone and frame_phone is not None:
                # 🔄 현재 싸우고 있는 크리처 인덱스를 렌더러에 같이 넘겨줍니다!
                battle_info = {
                    'is_battle': game_state == "BATTLE",
                    'creature_idx': current_creature_idx
                }
                
                frame_phone = ar_engine.render(frame_phone, char_dir, char_pos, bushes, battle_info)
                
                send_frame = cv2.resize(frame_phone, (640, 480)) 
                ret, buffer = cv2.imencode('.jpg', send_frame, [cv2.IMWRITE_JPEG_QUALITY, 50]) 
                if ret: phone_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
                    
        except Exception as e:
            time.sleep(0.01)
            continue

        socketio.emit('update_dashboard', {'laptop_img': laptop_b64, 'phone_img': phone_b64})
        time.sleep(0.05); gc.collect()

    # 🛑 [종료 로직 수정] 종료 메시지가 출력될 시간을 벌어주고 깔끔하게 닫습니다.
    print("\n[시스템] 카메라 자원을 안전하게 해제합니다...", flush=True)
    if hasattr(cap_laptop, 'release'): cap_laptop.release()
    if hasattr(cap_phone, 'release'): cap_phone.release()
    tracker.close(); ar_engine.close()
    time.sleep(1) # 글씨가 터미널에 찍힐 시간 확보
    os._exit(0)

if __name__ == "__main__":
    app, socketio, cap_phone = camera_connection.create_app(NGROK_TOKEN)
    
    @socketio.on('shutdown_server')
    def handle_shutdown():
        global is_running
        print("🔴 웹 브라우저로부터 종료 요청을 받았습니다.", flush=True)
        is_running = False

    threading.Thread(target=game_loop, args=(socketio, cap_phone), daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)