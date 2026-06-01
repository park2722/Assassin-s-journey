import cv2
import numpy as np
import trimesh
import pyrender

class AREngine:
    def __init__(self, viewport_width=640, viewport_height=480):
        # 체스보드 파라미터 (원본 유지)
        self.BOARD_W = 8
        self.BOARD_H = 6
        self.SQUARE_SIZE = 30.0
        
        self.objp = np.zeros((self.BOARD_W * self.BOARD_H, 3), np.float32)
        self.objp[:, :2] = np.mgrid[0:self.BOARD_W, 0:self.BOARD_H].T.reshape(-1, 2) * self.SQUARE_SIZE

        # 모델 세팅 파라미터 (원본 유지 및 회전각 변수 추가)
        self.MODEL_SCALE = 100.0 
        self.OFFSET_X = 110.0
        self.OFFSET_Y = 75.0
        self.OFFSET_Z = 0.0
        self.current_y_angle = 180.0 # 초기 방향 (앞모습)

        try:
            self.camera_matrix = np.load('calibration_data/camera_matrix.npy')
            self.dist_coeffs = np.load('calibration_data/dist_coeffs.npy')
        except FileNotFoundError:
            print("🚨 [오류] calibration_data 폴더에 파라미터 파일이 없습니다!")
            exit()

        self.scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.3, 0.3, 0.3])
        try:
            gltf_model = trimesh.load('assets/models/character/scene.gltf')
            if isinstance(gltf_model, trimesh.Scene):
                mesh = pyrender.Mesh.from_trimesh(list(gltf_model.geometry.values()))
            else:
                mesh = pyrender.Mesh.from_trimesh(gltf_model)
        except Exception as e:
            print(f"🚨 모델 로드 실패: {e}")
            exit()

        self.model_node = self.scene.add(mesh, name='character')

        # 🆕 2. 부쉬(Bush) 모델 로드 추가
        self.BUSH_SCALE = 17.0 # 부쉬 크기에 맞게 조절하세요!
        try:
            bush_gltf = trimesh.load('assets/models/bush/scene.gltf') # 🚨 부쉬 모델 경로!
            if isinstance(bush_gltf, trimesh.Scene):
                bush_mesh = pyrender.Mesh.from_trimesh(list(bush_gltf.geometry.values()))
            else:
                bush_mesh = pyrender.Mesh.from_trimesh(bush_gltf)
        except Exception as e:
            print(f"🚨 부쉬 모델 로드 실패: {e}")
            exit()

        # 💡 매 프레임마다 그렸다 지우면 렉이 걸리므로, 미리 10개의 빈 부쉬 노드를 만들어 둡니다.
        self.bush_nodes = []
        for _ in range(10):
            self.bush_nodes.append(self.scene.add(bush_mesh, name='bush'))

        light = pyrender.DirectionalLight(color=np.ones(3), intensity=5.0)
        self.scene.add(light, pose=np.eye(4))

        fx, fy = self.camera_matrix[0,0], self.camera_matrix[1,1]
        cx, cy = self.camera_matrix[0,2], self.camera_matrix[1,2]
        
        virtual_camera = pyrender.IntrinsicsCamera(fx=fx, fy=fy, cx=cx, cy=cy, znear=0.1, zfar=10000.0)
        self.scene.add(virtual_camera, pose=np.eye(4)) 

        self.renderer = pyrender.OffscreenRenderer(viewport_width, viewport_height)

    def grid_to_world(self, gx, gy):
        world_x = gx * self.SQUARE_SIZE + (self.SQUARE_SIZE / 2.0)
        world_y = gy * self.SQUARE_SIZE + (self.SQUARE_SIZE / 2.0)
        return world_x, world_y

    def render(self, frame_phone, angle_delta, char_pos, bushes):
        frame_phone = cv2.resize(frame_phone, (640, 480))
        h, w = frame_phone.shape[:2]
        
        # 제스처 회전 누적
        self.current_y_angle += angle_delta

        gray = cv2.cvtColor(frame_phone, cv2.COLOR_BGR2GRAY)
        ret_board, corners = cv2.findChessboardCorners(gray, (self.BOARD_W, self.BOARD_H), None)

        if ret_board:
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            ret_pnp, rvec, tvec = cv2.solvePnP(self.objp, corners2, self.camera_matrix, self.dist_coeffs)

            if ret_pnp:
                R, _ = cv2.Rodrigues(rvec)
                transform = np.eye(4)
                transform[:3, :3] = R
                transform[:3, 3] = tvec.flatten()

                flip_yz = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
                
                scale_matrix = np.eye(4)
                scale_matrix[0,0] = scale_matrix[1,1] = scale_matrix[2,2] = self.MODEL_SCALE

                angle_x = np.radians(0)    
                angle_y = np.radians(180)  
                angle_z = np.radians(self.current_y_angle) # 👈 회전값을 Z축으로 이동

                rx = np.array([[1, 0, 0, 0], [0, np.cos(angle_x), -np.sin(angle_x), 0], [0, np.sin(angle_x),  np.cos(angle_x), 0], [0, 0, 0, 1]])
                ry = np.array([[np.cos(angle_y), 0, np.sin(angle_y), 0], [0, 1, 0, 0], [-np.sin(angle_y), 0,  np.cos(angle_y), 0], [0, 0, 0, 1]])
                rz = np.array([[np.cos(angle_z), -np.sin(angle_z), 0, 0], [np.sin(angle_z), np.cos(angle_z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                model_rotation = rx @ ry @ rz

                # 🔄 [수정됨] 1. 캐릭터 위치 적용
                cx, cy = self.grid_to_world(char_pos[0], char_pos[1])
                char_translation = np.eye(4)
                char_translation[0, 3] = cx
                char_translation[1, 3] = cy
                char_translation[2, 3] = 0.0 # Z축 높이

                scale_matrix = np.eye(4)
                scale_matrix[0,0] = scale_matrix[1,1] = scale_matrix[2,2] = self.MODEL_SCALE

                char_pose = flip_yz @ transform @ char_translation @ model_rotation @ scale_matrix
                self.scene.set_pose(self.model_node, pose=char_pose)

                # 🆕 2. 부쉬 위치 적용
                bush_list = list(bushes)
                bush_scale = np.eye(4)
                bush_scale[0,0] = bush_scale[1,1] = bush_scale[2,2] = self.BUSH_SCALE

                # 🔄 [추가] 부쉬를 똑바로 세우기 위한 전용 회전 행렬
                # 💡 만약 X축으로 돌렸는데 여전히 누워있다면, angle_x는 0으로 두고 angle_z를 np.radians(90)이나 -90으로 바꿔보세요!
                bush_angle_x = np.radians(-90)  # 앞으로/뒤로 누워있을 때 세우는 축
                bush_angle_y = np.radians(0)
                bush_angle_z = np.radians(0)   # 오른쪽/왼쪽으로 누워있을 때 세우는 축

                brx = np.array([[1, 0, 0, 0], [0, np.cos(bush_angle_x), -np.sin(bush_angle_x), 0], [0, np.sin(bush_angle_x),  np.cos(bush_angle_x), 0], [0, 0, 0, 1]])
                bry = np.array([[np.cos(bush_angle_y), 0, np.sin(bush_angle_y), 0], [0, 1, 0, 0], [-np.sin(bush_angle_y), 0,  np.cos(bush_angle_y), 0], [0, 0, 0, 1]])
                brz = np.array([[np.cos(bush_angle_z), -np.sin(bush_angle_z), 0, 0], [np.sin(bush_angle_z), np.cos(bush_angle_z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                bush_rotation = brx @ bry @ brz
                
                for i, node in enumerate(self.bush_nodes):
                    if i < len(bush_list):
                        # 부쉬가 있을 자리라면 위치를 이동시켜서 보여줌
                        bx, by = self.grid_to_world(bush_list[i][0], bush_list[i][1])
                        bush_trans = np.eye(4)
                        bush_trans[0, 3] = bx
                        bush_trans[1, 3] = by
                        bush_trans[2, 3] = 0.0

                        # 🔄 [수정] 회전 행렬(bush_rotation)을 곱해줍니다!
                        bush_pose = flip_yz @ transform @ bush_trans @ bush_rotation @ bush_scale
                        self.scene.set_pose(node, pose=bush_pose)
                    else:
                        # 남는 부쉬 노드는 카메라 저 멀리(Z축 10000) 치워서 안 보이게 숨김
                        hidden_pose = np.eye(4)
                        hidden_pose[2, 3] = 10000.0
                        self.scene.set_pose(node, pose=hidden_pose)

                color, depth = self.renderer.render(self.scene, flags=pyrender.RenderFlags.RGBA)
                alpha_channel = color[:, :, 3] / 255.0
                
                for c in range(0, 3):
                    frame_phone[:, :, c] = (alpha_channel * color[:, :, c] + (1 - alpha_channel) * frame_phone[:, :, c])
                    
        return frame_phone

    def close(self):
        if hasattr(self, 'renderer') and self.renderer is not None:
            self.renderer.delete()