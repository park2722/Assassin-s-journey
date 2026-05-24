import cv2
import numpy as np
import glob
import os

# ==========================================
# 테스트용 체스보드 설정
# ==========================================
BOARD_W = 10       # 가로 내부 코너 수
BOARD_H = 7        # 세로 내부 코너 수
SQUARE_SIZE = 25.0 # 한 칸의 물리적 크기 (mm)

# 폴더 경로 설정
IMG_DIR = 'calibration_images'
SAVE_DIR = 'calibration_data'

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# 3D 공간상의 체스보드 코너 좌표 생성 (Z는 0)
# 형태: (0,0,0), (25,0,0), (50,0,0) ...
objp = np.zeros((BOARD_W * BOARD_H, 3), np.float32)
objp[:, :2] = np.mgrid[0:BOARD_W, 0:BOARD_H].T.reshape(-1, 2) * SQUARE_SIZE

objpoints = [] # 실제 3D 공간상의 점들 보관
imgpoints = [] # 2D 이미지 상의 코너점들 보관

# calibration_images 폴더 안의 모든 jpg/png 파일 불러오기
images = glob.glob(f'{IMG_DIR}/*.[jp][pn]g')

if len(images) == 0:
    print(f"오류: '{IMG_DIR}' 폴더에 이미지가 없습니다! 사진을 먼저 넣어주세요.")
    exit()

print(f"총 {len(images)}장의 이미지에서 캘리브레이션을 시작합니다...")

# 이미지 크기 저장용 변수
image_size = None

for fname in images:
    img = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if image_size is None:
        image_size = gray.shape[::-1] # (width, height)

    # 체스보드 코너 찾기
    ret, corners = cv2.findChessboardCorners(gray, (BOARD_W, BOARD_H), None)

    # 코너를 찾았다면
    if ret == True:
        objpoints.append(objp)

        # 코너 좌표의 정확도를 서브픽셀 단위로 높임
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        imgpoints.append(corners2)

        # 찾은 코너를 이미지에 그려서 화면에 잠시 보여줌 (확인용)
        cv2.drawChessboardCorners(img, (BOARD_W, BOARD_H), corners2, ret)
        cv2.imshow('Chessboard Detection', cv2.resize(img, (800, 600)))
        cv2.waitKey(200) # 0.2초씩 대기
    else:
        print(f"경고: '{fname}' 에서 {BOARD_W}x{BOARD_H} 체스보드를 찾지 못했습니다. 이 사진은 제외됩니다.")

cv2.destroyAllWindows()

# ==========================================
# 카메라 파라미터 계산 및 저장
# ==========================================
if len(objpoints) > 0:
    print("\n카메라 매트릭스 계산 중... 잠시만 기다려주세요.")
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, image_size, None, None)

    print("✅ 캘리브레이션 완료!")
    print("\n--- Camera Matrix (K) ---")
    print(camera_matrix)
    print("\n--- Distortion Coefficients ---")
    print(dist_coeffs)

    # 파일로 저장 (나중에 main.py 에서 불러다 쓸 목적)
    np.save(f'{SAVE_DIR}/camera_matrix.npy', camera_matrix)
    np.save(f'{SAVE_DIR}/dist_coeffs.npy', dist_coeffs)
    print(f"\n파라미터가 '{SAVE_DIR}' 폴더에 성공적으로 저장되었습니다!")
else:
    print("\n실패: 체스보드를 인식한 사진이 단 한 장도 없습니다. 사진을 다시 찍어주세요.")