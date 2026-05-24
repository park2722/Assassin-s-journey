import cv2
import numpy as np
import base64
import time
import threading
import os
import gc
import trimesh
import pyrender
import camera_connection

# [필수] 본인의 Ngrok 토큰을 입력하세요
NGROK_TOKEN = "3DI3r8yIrtDAyhegv2upug4K5UZ_5occ93smHoaiTrPGzt2JH"

is_running = True

# ==========================================================
# 1. 테스트용 체스보드 및 카메라 캘리브레이션 데이터 세팅
# ==========================================================
BOARD_W = 10
BOARD_H = 7
SQUARE_SIZE = 25.0  # 25mm

# 3D 공간의 체스보드 기준 좌표(objp) 생성
objp = np.zeros((BOARD_W * BOARD_H, 3), np.float32)
objp[:, :2] = np.mgrid[0:BOARD_W, 0:BOARD_H].T.reshape(-1, 2) * SQUARE_SIZE

# 미리 추출해둔 내 휴대폰의 렌즈 파라미터 불러오기
try:
    camera_matrix = np.load('calibration_data/camera_matrix.npy')
    dist_coeffs = np.load('calibration_data/dist_coeffs.npy')
    print("[시스템] 카메라 파라미터를 성공적으로 불러왔습니다.")
except FileNotFoundError:
    print("🚨 [오류] calibration_data 폴더에 파라미터 파일이 없습니다!")
    exit()

# ==========================================================
# 2. 3D 렌더링 엔진 초기화 함수
# ==========================================================
def setup_3d_scene(viewport_width, viewport_height):
    """pyrender 씬(Scene)과 오프스크린 렌더러를 준비합니다."""
    # 배경을 투명하게(Alpha 0) 설정하여 현실 영상과 겹칠 수 있게 함
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.3, 0.3, 0.3])
    
    # 💡 [모델 불러오기] 에셋 폴더의 캐릭터 모델 로드
    try:
        gltf_model = trimesh.load('assets/models/character/scene.gltf')
        # 모델이 여러 파츠로 나뉘어 있을 수 있으므로 모두 병합해서 가져옵니다.
        if isinstance(gltf_model, trimesh.Scene):
            mesh = pyrender.Mesh.from_trimesh(list(gltf_model.geometry.values()))
        else:
            mesh = pyrender.Mesh.from_trimesh(gltf_model)
    except Exception as e:
        print(f"🚨 [오류] 3D 모델을 불러오지 못했습니다: {e}")
        return None, None, None

    # 씬에 모델 추가 (추후 위치는 계속 갱신됨)
    model_node = scene.add(mesh, name='character')

    # 조명 추가 (빛이 없으면 까맣게 나옴)
    light = pyrender.DirectionalLight(color=np.ones(3), intensity=5.0)
    scene.add(light, pose=np.eye(4))

    # 가상 카메라 추가 (현실 휴대폰 카메라의 파라미터를 그대로 이식!)
    fx, fy = camera_matrix[0,0], camera_matrix[1,1]
    cx, cy = camera_matrix[0,2], camera_matrix[1,2]
    
    # 🔄 [수정됨] 카메라가 밀리미터(mm) 단위의 먼 거리도 볼 수 있게 시야(znear, zfar) 설정 추가!
    virtual_camera = pyrender.IntrinsicsCamera(
        fx=fx, fy=fy, cx=cx, cy=cy,
        znear=0.1, zfar=10000.0
    )
    # 카메라는 항상 원점(0,0,0)에 고정하고, 체스보드(오브젝트)를 움직입니다.
    scene.add(virtual_camera, pose=np.eye(4)) 

    # 렌더러 생성 (스레드 내부에서 생성해야 안전함)
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

    print("게임 루프 가동 완료. 대시보드를 띄워주세요.")

    # 렌더러와 씬 변수 초기화 (휴대폰 프레임이 들어올 때 해상도에 맞춰 생성)
    scene, model_node, renderer = None, None, None
    
    # 💡 3D 모델의 크기를 조절하는 변수 (너무 크거나 작으면 이 숫자를 조절하세요!)
    MODEL_SCALE = 100

    while is_running:
        ret_laptop, frame_laptop = cap_laptop.read()
        ret_phone, frame_phone = cap_phone.read()

        laptop_b64 = None
        phone_b64 = None

        try:
            # ---------------------------------------------------------
            # [노트북 카메라: 제스처 인식 파트] (나중에 채워넣을 곳)
            # ---------------------------------------------------------
            if ret_laptop and frame_laptop is not None and getattr(frame_laptop, 'size', 0) > 0:
                ret, buffer = cv2.imencode('.jpg', frame_laptop, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret: laptop_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')

            # ---------------------------------------------------------
            # [휴대폰 카메라: 체스보드 인식 및 3D AR 렌더링 파트]
            # ---------------------------------------------------------
            if ret_phone and frame_phone is not None and getattr(frame_phone, 'size', 0) > 0:
                
                h, w = frame_phone.shape[:2]

                # 최초 1회 3D 씬 및 렌더러 세팅 (휴대폰 해상도에 맞춤)
                if scene is None:
                    scene, model_node, renderer = setup_3d_scene(w, h)

                # 1. 흑백 이미지로 변환하여 체스보드 찾기
                gray = cv2.cvtColor(frame_phone, cv2.COLOR_BGR2GRAY)
                ret_board, corners = cv2.findChessboardCorners(gray, (BOARD_W, BOARD_H), None)

                if ret_board and scene is not None:

                    # 좀 더 정밀한 코너 위치 찾기
                    cv2.drawChessboardCorners(frame_phone, (BOARD_W, BOARD_H), corners, ret_board)
                    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                    corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

                    # 2. PnP 알고리즘: 현실 카메라와 체스보드의 3D 공간적 위치 관계 계산
                    ret_pnp, rvec, tvec = cv2.solvePnP(objp, corners2, camera_matrix, dist_coeffs)

                    if ret_pnp:
                        # 회전 벡터(rvec)를 3x3 회전 행렬로 변환
                        R, _ = cv2.Rodrigues(rvec)
                        
                        # 4x4 변환 행렬(Transformation Matrix) 만들기
                        transform = np.eye(4)
                        transform[:3, :3] = R
                        transform[:3, 3] = tvec.flatten()

                        # 3. 스케일 및 축 변환 (OpenCV -> OpenGL)
                        # OpenCV는 Y가 아래, Z가 앞쪽 / OpenGL(pyrender)은 Y가 위, Z가 뒤쪽
                        flip_yz = np.array([
                            [1,  0,  0, 0],
                            [0, -1,  0, 0],
                            [0,  0, -1, 0],
                            [0,  0,  0, 1]
                        ])
                        
                        scale_matrix = np.eye(4)
                        scale_matrix[0,0] = scale_matrix[1,1] = scale_matrix[2,2] = MODEL_SCALE

                        # 🆕 [추가됨] 모델을 X축 기준으로 180도(pi) 강제 회전시키는 행렬
                        # (만약 180도를 돌렸는데도 옆으로 누워있다면 np.pi / 2 (90도) 등으로 숫자를 바꿔보세요)
                        angle_x = np.pi 
                        rx = np.array([
                            [1, 0, 0, 0],
                            [0, np.cos(angle_x), -np.sin(angle_x), 0],
                            [0, np.sin(angle_x),  np.cos(angle_x), 0],
                            [0, 0, 0, 1]
                        ])

                        # 💡 회전 행렬(rx)을 중간에 끼워 넣어서 같이 곱해줍니다.
                        final_pose = flip_yz @ transform @ rx @ scale_matrix
                        scene.set_pose(model_node, pose=final_pose)

                        # 4. 렌더링 수행 (배경은 투명하고 캐릭터만 그려진 이미지 반환)
                        color, depth = renderer.render(scene, flags=pyrender.RenderFlags.RGBA)

                        # 5. 현실 영상(frame_phone) 위에 3D 캐릭터(color)를 알파 블렌딩(합성)
                        alpha_channel = color[:, :, 3] / 255.0
                        for c in range(0, 3):
                            frame_phone[:, :, c] = (alpha_channel * color[:, :, c] + 
                                                    (1 - alpha_channel) * frame_phone[:, :, c])

                # 최종 합성된 이미지를 Base64로 인코딩하여 웹으로 송출
                ret, buffer = cv2.imencode('.jpg', frame_phone, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret: phone_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8')
                    
        except Exception as e:
            print(f"[렌더링/변환 에러 방어] {e}")
            time.sleep(0.01)
            continue

        socketio.emit('update_dashboard', {
            'laptop_img': laptop_b64,
            'phone_img': phone_b64
        })

        # 🔄 [수정됨] 네트워크 병목을 막기 위해 0.03에서 0.06으로 휴식 시간 늘림 (약 15 FPS로 안정화)
        time.sleep(0.06) 
        
        # 🆕 [추가됨] 렌더링 과정에서 쌓인 불필요한 메모리를 강제로 즉시 비워냄
        gc.collect()
        

    # --- 종료 처리 ---
    print("\n[시스템] 카메라 자원을 안전하게 해제합니다...")
    if hasattr(cap_laptop, 'release'): cap_laptop.release()
    if hasattr(cap_phone, 'release'): cap_phone.release()
    if renderer is not None: renderer.delete() # 렌더러 메모리 해제
    
    print("[시스템] 서버가 완전히 종료되었습니다. 안녕히 가세요!")
    os._exit(0)

if __name__ == "__main__":
    if NGROK_TOKEN == "여기에_본인의_토큰_입력":
        print("NGROK 토큰을 입력해주세요!")
        exit()

    app, socketio, cap_phone = camera_connection.create_app(NGROK_TOKEN)

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