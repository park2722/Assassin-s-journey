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
        light = pyrender.DirectionalLight(color=np.ones(3), intensity=5.0)
        self.scene.add(light, pose=np.eye(4))

        fx, fy = self.camera_matrix[0,0], self.camera_matrix[1,1]
        cx, cy = self.camera_matrix[0,2], self.camera_matrix[1,2]
        
        virtual_camera = pyrender.IntrinsicsCamera(fx=fx, fy=fy, cx=cx, cy=cy, znear=0.1, zfar=10000.0)
        self.scene.add(virtual_camera, pose=np.eye(4)) 

        self.renderer = pyrender.OffscreenRenderer(viewport_width, viewport_height)

    def render(self, frame_phone, angle_delta):
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
                angle_y = np.radians(self.current_y_angle)  
                angle_z = np.radians(0)

                rx = np.array([[1, 0, 0, 0], [0, np.cos(angle_x), -np.sin(angle_x), 0], [0, np.sin(angle_x),  np.cos(angle_x), 0], [0, 0, 0, 1]])
                ry = np.array([[np.cos(angle_y), 0, np.sin(angle_y), 0], [0, 1, 0, 0], [-np.sin(angle_y), 0,  np.cos(angle_y), 0], [0, 0, 0, 1]])
                rz = np.array([[np.cos(angle_z), -np.sin(angle_z), 0, 0], [np.sin(angle_z), np.cos(angle_z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                model_rotation = rx @ ry @ rz

                translation_matrix = np.eye(4)
                translation_matrix[0, 3] = self.OFFSET_X
                translation_matrix[1, 3] = self.OFFSET_Y
                translation_matrix[2, 3] = self.OFFSET_Z

                final_pose = flip_yz @ transform @ translation_matrix @ model_rotation @ scale_matrix
                self.scene.set_pose(self.model_node, pose=final_pose)

                color, depth = self.renderer.render(self.scene, flags=pyrender.RenderFlags.RGBA)
                alpha_channel = color[:, :, 3] / 255.0
                
                for c in range(0, 3):
                    frame_phone[:, :, c] = (alpha_channel * color[:, :, c] + (1 - alpha_channel) * frame_phone[:, :, c])
                    
        return frame_phone

    def close(self):
        if hasattr(self, 'renderer') and self.renderer is not None:
            self.renderer.delete()