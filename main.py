import cv2
import numpy as np
import base64
import time
import threading
import os
import trimesh
import pyrender
import gc
import mediapipe as mp  # 🆕 손가락 관절 추적을 위한 미디어파이프 라이브러리 추가
import camera_connection

NGROK_TOKEN = "3DI3r8yIrtDAyhegv2upug4K5UZ_5occ93smHoaiTrPGzt2JH" 
is_running = True

# ==========================================================
# 1. 테스트용 체스보드 및 카메라 캘리브레이션
# ==========================================================
BOARD_W = 8
BOARD_H = 6
SQUARE_SIZE = 30.0

objp = np.zeros((BOARD_W * BOARD_H, 3), np.float32)
objp[:, :2] = np.mgrid[0:BOARD_W, 0:BOARD_H].T.reshape(-1, 2) * SQUARE_SIZE

try:
    camera_matrix = np.load('calibration_data/camera_matrix.npy')
    dist_coeffs = np.load('calibration_data/dist_coeffs.npy')
except FileNotFoundError:
    print("🚨 [오류] calibration_data 폴더에 파라미터 파일이 없습니다!")
    exit()

# ==========================================================
# 2. 3D 렌더링 엔진 초기화
# ==========================================================
def setup_3d_scene(viewport_width, viewport_height):
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.3, 0.3, 0.3])
    try:
        gltf_model = trimesh.load('assets/models/character/scene.gltf')
        if isinstance(gltf_model, trimesh.Scene):
            mesh = pyrender.Mesh.from_trimesh(list(gltf_model.geometry.values()))
        else:
            mesh = pyrender.Mesh.from_trimesh(gltf_model)
    except Exception as e:
        return None, None, None

    model_node = scene.add(mesh, name='character')
    light = pyrender.DirectionalLight(color=np.ones(3), intensity=5.0)
    scene.add(light, pose=np.eye(4))

    fx, fy = camera_matrix[0,0], camera_matrix[1,1]
    cx, cy = camera_matrix[0,2], camera_matrix[1,2]
    
    virtual_camera = pyrender.IntrinsicsCamera(fx=fx, fy=fy, cx=cx, cy=cy, znear=0.1, zfar=10000.0)
    scene.add(virtual_camera, pose=np.eye(4)) 

    renderer = pyrender.OffscreenRenderer(viewport_width, viewport_height)
    return scene, model_node, renderer

# ==========================================================
# 3. 메인 게임 루프 
# ==========================================================
def game_loop(socketio, cap_phone):
    global is_running
    print("웹캠을 켜는 중...")
    cap_laptop = cv2.VideoCapture(0)
    
    if not cap_laptop.isOpened():
        print("노트북 웹캠을 열 수 없습니다!")
        return

    # 🆕 MediaPipe 손 인식 모듈 초기화 (루프 밖에서 한 번만 선언해야 빠릅니다)
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
    mp_draw = mp.solutions.drawing_utils

    scene, model_node, renderer = None, None, None
    print("게임 루프 가동 완료. 대시보드를 띄워주세요.")

    while is_running:
        ret_laptop, frame_laptop = cap_laptop.read()
        ret_phone, frame_phone = cap_phone.read()

        laptop_b64 = None
        phone_b64 = None

        try:
            # ---------------------------------------------------------
            # 🔄 [수정됨] 노트북 카메라: 거울 모드 및 제스처 인식 파트
            # ---------------------------------------------------------
            if ret_laptop and frame_laptop is not None and getattr(frame_laptop, 'size', 0) > 0:
                frame_laptop = cv2.flip(frame_laptop, 1) # 거울 모드(좌우 반전)
                
                # 💡 MediaPipe는 RGB 색상을 사용하므로 BGR에서 변환해줍니다.
                rgb_laptop = cv2.cvtColor(frame_laptop, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb_laptop)
                
                gesture_text = "None"
                
                # 💡 화면에 손이 인식되었다면
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # 손가락 관절과 뼈대를 화면에 그립니다.
                        mp_draw.draw_landmarks(frame_laptop, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                        
                        # 검지손가락 끝(TIP)과 검지 뿌리(MCP)의 X 좌표를 추출하여 방향 계산
                        index_tip_x = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x
                        index_mcp_x = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP].x
                        
                        # 끝부분이 뿌리보다 확실히 왼쪽(-0.05)에 있으면 Left
                        if index_tip_x < index_mcp_x - 0.05:
                            gesture_text = "Left Swipe"
                        elif index_tip_x > index_mcp_x + 0.05:
                            gesture_text = "Right Swipe"
                
                # 인식된 제스처 상태를 노트북 화면 좌측 상단에 띄워줍니다.
                cv2.putText(frame_laptop, f"Action: {gesture_text}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

                ret, buffer = cv2.imencode('.jpg', frame_laptop, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret: laptop_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')

            # ---------------------------------------------------------
            # [휴대폰 카메라: 체스보드 인식 및 3D 합성]
            # ---------------------------------------------------------
            if ret_phone and frame_phone is not None and getattr(frame_phone, 'size', 0) > 0:
                h, w = frame_phone.shape[:2]

                if scene is None:
                    scene, model_node, renderer = setup_3d_scene(w, h)

                gray = cv2.cvtColor(frame_phone, cv2.COLOR_BGR2GRAY)
                ret_board, corners = cv2.findChessboardCorners(gray, (BOARD_W, BOARD_H), None)

                if ret_board and scene is not None:
                    corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                    ret_pnp, rvec, tvec = cv2.solvePnP(objp, corners2, camera_matrix, dist_coeffs)

                    if ret_pnp:
                        R, _ = cv2.Rodrigues(rvec)
                        transform = np.eye(4)
                        transform[:3, :3] = R
                        transform[:3, 3] = tvec.flatten()

                        flip_yz = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
                        
                        MODEL_SCALE = 100.0 
                        scale_matrix = np.eye(4)
                        scale_matrix[0,0] = scale_matrix[1,1] = scale_matrix[2,2] = MODEL_SCALE

                        angle_x = np.radians(0)    # 💡 90도에서 0도로 변경 (여전히 누워있다면 -90으로 변경)
                        angle_y = np.radians(180)  # 앞모습을 보기 위한 Y축 180도 회전
                        angle_z = np.radians(0)

                        rx = np.array([[1, 0, 0, 0], [0, np.cos(angle_x), -np.sin(angle_x), 0], [0, np.sin(angle_x),  np.cos(angle_x), 0], [0, 0, 0, 1]])
                        ry = np.array([[np.cos(angle_y), 0, np.sin(angle_y), 0], [0, 1, 0, 0], [-np.sin(angle_y), 0,  np.cos(angle_y), 0], [0, 0, 0, 1]])
                        rz = np.array([[np.cos(angle_z), -np.sin(angle_z), 0, 0], [np.sin(angle_z), np.cos(angle_z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                        model_rotation = rx @ ry @ rz

                        OFFSET_X, OFFSET_Y, OFFSET_Z = 110.0, 75.0, 0.0 
                        translation_matrix = np.eye(4)
                        translation_matrix[0, 3] = OFFSET_X
                        translation_matrix[1, 3] = OFFSET_Y
                        translation_matrix[2, 3] = OFFSET_Z

                        final_pose = flip_yz @ transform @ translation_matrix @ model_rotation @ scale_matrix
                        scene.set_pose(model_node, pose=final_pose)

                        color, depth = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)
                        alpha_channel = color[:, :, 3] / 255.0
                        
                        for c in range(0, 3):
                            frame_phone[:, :, c] = (alpha_channel * color[:, :, c] + (1 - alpha_channel) * frame_phone[:, :, c])

                send_frame = cv2.resize(frame_phone, (640, 480)) 
                ret, buffer = cv2.imencode('.jpg', send_frame, [cv2.IMWRITE_JPEG_QUALITY, 50]) 
                
                if ret: 
                    phone_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
                    
        except Exception as e:
            print(f"[렌더링 에러 방어] {e}")
            time.sleep(0.01)
            continue

        socketio.emit('update_dashboard', {
            'laptop_img': laptop_b64,
            'phone_img': phone_b64
        })

        time.sleep(0.05) 
        gc.collect()

    print("\n[시스템] 카메라 자원을 안전하게 해제합니다...")
    if hasattr(cap_laptop, 'release'): cap_laptop.release()
    if hasattr(cap_phone, 'release'): cap_phone.release()
    if renderer is not None: renderer.delete() 
    if 'hands' in locals(): hands.close() # 🆕 MediaPipe 자원 해제
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