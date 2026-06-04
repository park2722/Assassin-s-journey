import cv2
import numpy as np
import trimesh
import pyrender

class AREngine:
    def __init__(self, viewport_width=640, viewport_height=480):
        self.BOARD_W, self.BOARD_H, self.SQUARE_SIZE = 8, 6, 30.0
        self.objp = np.zeros((self.BOARD_W * self.BOARD_H, 3), np.float32)
        self.objp[:, :2] = np.mgrid[0:self.BOARD_W, 0:self.BOARD_H].T.reshape(-1, 2) * self.SQUARE_SIZE

        self.MODEL_SCALE = 100.0 
        self.BUSH_SCALE = 17.0
        self.CREATURE_SCALE = 25.0 # 🆕 크리처 크기 조절
        
        self.OFFSET_X, self.OFFSET_Y, self.OFFSET_Z = 0.0, -75.0, 0.0
        self.current_y_angle = 180.0 

        try:
            self.camera_matrix = np.load('calibration_data/camera_matrix.npy')
            self.dist_coeffs = np.load('calibration_data/dist_coeffs.npy')
        except FileNotFoundError:
            exit()

        self.scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.3, 0.3, 0.3])
        
        # 1. 캐릭터 로드
        mesh = pyrender.Mesh.from_trimesh(list(trimesh.load('assets/models/character/scene.gltf').geometry.values()))
        self.model_node = self.scene.add(mesh, name='character')
        
        # 2. 부쉬 로드
        bush_mesh = pyrender.Mesh.from_trimesh(list(trimesh.load('assets/models/bush/scene.gltf').geometry.values()))
        self.bush_nodes = [self.scene.add(bush_mesh, name='bush') for _ in range(10)]

        # 🆕 3. 크리처 로드
        self.creature_nodes = []
        for i in range(1, 4): # 1, 2, 3 번 크리처 로드
            try:
                c_mesh = pyrender.Mesh.from_trimesh(list(trimesh.load(f'assets/models/creature_{i}/scene.gltf').geometry.values()))
                self.creature_nodes.append(self.scene.add(c_mesh, name=f'creature_{i}'))
            except Exception as e:
                print(f"🚨 크리처 {i} 로드 실패: {e}")
                exit()

        light = pyrender.DirectionalLight(color=np.ones(3), intensity=5.0)
        self.scene.add(light, pose=np.eye(4))
        virtual_camera = pyrender.IntrinsicsCamera(fx=self.camera_matrix[0,0], fy=self.camera_matrix[1,1], cx=self.camera_matrix[0,2], cy=self.camera_matrix[1,2], znear=0.1, zfar=10000.0)
        self.scene.add(virtual_camera, pose=np.eye(4)) 
        self.renderer = pyrender.OffscreenRenderer(viewport_width, viewport_height)

    def grid_to_world(self, gx, gy):
        return gx * self.SQUARE_SIZE + (self.SQUARE_SIZE / 2.0), gy * self.SQUARE_SIZE + (self.SQUARE_SIZE / 2.0)

    # 🔄 battle_info 파라미터 추가
    def render(self, frame_phone, char_dir, char_pos, bushes, battle_info):
        frame_phone = cv2.resize(frame_phone, (640, 480))
        dir_angles = {0: 180.0, 1: 90.0, 2: 0.0, 3: 270.0}
        
        self.current_y_angle = dir_angles[char_dir]
        gray = cv2.cvtColor(frame_phone, cv2.COLOR_BGR2GRAY)
        ret_board, corners = cv2.findChessboardCorners(gray, (self.BOARD_W, self.BOARD_H), None)

        if ret_board:
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            ret_pnp, rvec, tvec = cv2.solvePnP(self.objp, corners2, self.camera_matrix, self.dist_coeffs)

            if ret_pnp:
                R, _ = cv2.Rodrigues(rvec)
                transform = np.eye(4); transform[:3, :3] = R; transform[:3, 3] = tvec.flatten()
                flip_yz = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])

                cx, cy = self.grid_to_world(char_pos[0], char_pos[1])
                
                # ⚔️ 대치 상황 Offset: 전투 중이면 캐릭터를 살짝 뒤로 물립니다.
                char_cx, char_cy = cx, cy
                if battle_info['is_battle']:
                    char_cx -= 10.0  # 칸 내에서 뒤쪽으로 이동

                char_translation = np.eye(4); char_translation[0, 3] = char_cx + self.OFFSET_X; char_translation[1, 3] = char_cy + self.OFFSET_Y
                scale_matrix = np.eye(4); scale_matrix[0,0] = scale_matrix[1,1] = scale_matrix[2,2] = self.MODEL_SCALE
                angle_x, angle_y, angle_z = np.radians(0), np.radians(180), np.radians(self.current_y_angle)
                rx = np.array([[1, 0, 0, 0], [0, np.cos(angle_x), -np.sin(angle_x), 0], [0, np.sin(angle_x),  np.cos(angle_x), 0], [0, 0, 0, 1]])
                ry = np.array([[np.cos(angle_y), 0, np.sin(angle_y), 0], [0, 1, 0, 0], [-np.sin(angle_y), 0,  np.cos(angle_y), 0], [0, 0, 0, 1]])
                rz = np.array([[np.cos(angle_z), -np.sin(angle_z), 0, 0], [np.sin(angle_z), np.cos(angle_z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                
                self.scene.set_pose(self.model_node, pose=flip_yz @ transform @ char_translation @ (rx @ ry @ rz) @ scale_matrix)

                # 🌿 부쉬 렌더링
                bush_list = list(bushes)
                bush_scale = np.eye(4); bush_scale[0,0] = bush_scale[1,1] = bush_scale[2,2] = self.BUSH_SCALE

                bush_angle_x = np.radians(-90)  # 앞으로/뒤로 누워있을 때 세우는 축
                bush_angle_y = np.radians(0)
                bush_angle_z = np.radians(0)   # 오른쪽/왼쪽으로 누워있을 때 세우는 축

                brx = np.array([[1, 0, 0, 0], [0, np.cos(bush_angle_x), -np.sin(bush_angle_x), 0], [0, np.sin(bush_angle_x),  np.cos(bush_angle_x), 0], [0, 0, 0, 1]])
                bry = np.array([[np.cos(bush_angle_y), 0, np.sin(bush_angle_y), 0], [0, 1, 0, 0], [-np.sin(bush_angle_y), 0,  np.cos(bush_angle_y), 0], [0, 0, 0, 1]])
                brz = np.array([[np.cos(bush_angle_z), -np.sin(bush_angle_z), 0, 0], [np.sin(bush_angle_z), np.cos(bush_angle_z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                bush_rot = brx @ bry @ brz
                
                for i, node in enumerate(self.bush_nodes):
                    # 💡 전투 중인 칸의 부쉬는 숨깁니다!
                    if i < len(bush_list) and not (battle_info['is_battle'] and list(bush_list[i]) == char_pos):
                        bx, by = self.grid_to_world(bush_list[i][0], bush_list[i][1])
                        b_trans = np.eye(4); b_trans[0, 3] = bx + self.OFFSET_X; b_trans[1, 3] = by + self.OFFSET_Y
                        self.scene.set_pose(node, pose=flip_yz @ transform @ b_trans @ bush_rot @ bush_scale)
                    else:
                        hidden = np.eye(4); hidden[2, 3] = 10000.0
                        self.scene.set_pose(node, pose=hidden)

                # 🐉 크리처 렌더링
                # 🐉 크리처 렌더링 (전투 중일 때만)
                active_c_idx = battle_info.get('creature_idx', 0)
                
                # 🔄 [크리처 회전 행렬] 거꾸로 뒤집혀 있다면 X축이나 Z축을 180도 돌려보세요!
                c_angle_x = np.radians(180) # 💡 뒤집혀있을 때 세우는 축 (필요시 90, -90, 0 등으로 조절)
                c_angle_y = np.radians(0)
                c_angle_z = np.radians(0)   # 💡 옆으로 누워있을 때 세우는 축

                crx = np.array([[1, 0, 0, 0], [0, np.cos(c_angle_x), -np.sin(c_angle_x), 0], [0, np.sin(c_angle_x),  np.cos(c_angle_x), 0], [0, 0, 0, 1]])
                cry = np.array([[np.cos(c_angle_y), 0, np.sin(c_angle_y), 0], [0, 1, 0, 0], [-np.sin(c_angle_y), 0,  np.cos(c_angle_y), 0], [0, 0, 0, 1]])
                crz = np.array([[np.cos(c_angle_z), -np.sin(c_angle_z), 0, 0], [np.sin(c_angle_z), np.cos(c_angle_z), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
                creature_rot = crx @ cry @ crz

                for i, node in enumerate(self.creature_nodes):
                    if battle_info['is_battle'] and i == active_c_idx:
                        creature_trans = np.eye(4)
                        creature_trans[0, 3] = cx + 10.0 + self.OFFSET_X 
                        creature_trans[1, 3] = cy + self.OFFSET_Y
                        c_scale = np.eye(4); c_scale[0,0] = c_scale[1,1] = c_scale[2,2] = self.CREATURE_SCALE
                        
                        # 회전(creature_rot) 적용!
                        self.scene.set_pose(node, pose=flip_yz @ transform @ creature_trans @ creature_rot @ c_scale)
                    else:
                        hidden = np.eye(4); hidden[2, 3] = 10000.0
                        self.scene.set_pose(node, pose=hidden)

                color, depth = self.renderer.render(self.scene, flags=pyrender.RenderFlags.RGBA)
                alpha_channel = color[:, :, 3] / 255.0
                for c in range(0, 3):
                    frame_phone[:, :, c] = (alpha_channel * color[:, :, c] + (1 - alpha_channel) * frame_phone[:, :, c])
                    
        return frame_phone

    def close(self):
        if hasattr(self, 'renderer') and self.renderer is not None: self.renderer.delete()