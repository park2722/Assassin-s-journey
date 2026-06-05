# AR Encounter and Capture Creature 

노트북 웹캠의 **AI 제스처 인식**과 스마트폰 카메라의 **AR 3D 렌더링**을 결합한 실시간 증강현실 몬스터 포획 게임입니다. 
체스보드 위를 탐험하며 야생의 크리처를 만나고, 손동작을 통해 전투와 포획을 진행할 수 있습니다.

<br>

##  핵심 기능 (Features)

- **AI 기반 무선 제스처 컨트롤 (`gesture_tracker.py`)**
  - MediaPipe Hands를 활용한 실시간 손가락 관절(Landmark) 추적
  - 손가락 끝과 마디의 물리적 거리 계산을 통한 완벽한 **'주먹(Fist)'** 인식 (전진/포획)
  - 히스토리 버퍼(History Buffer) 큐를 활용한 부드러운 **'아래로 스와이프(Down Swipe)'** 인식 (도망)
  - 입력 과부하 방지를 위한 쿨다운(Cooldown) 및 디바운싱 시스템 적용

- **3D AR 엔진 & 상태 머신 (`ar_engine.py` & `main.py`)**
  - OpenCV `solvePnP`를 활용한 8x6 체스보드 마커리스 AR 투영
  - Pyrender & Trimesh를 이용한 3D 모델(gltf) 렌더링
  - 캐릭터의 이동(Grid Movement) 및 7x5 안전지대 부쉬(Bush) 랜덤 생성
  - 상태 머신(EXPLORE / BATTLE)에 따른 오프셋 자동 조정 및 3종 크리처 랜덤 조우

- **실시간 웹 대시보드 (`camera_connection.py` & `index.html`)**
  - Flask-SocketIO를 활용한 양방향 실시간 영상 스트리밍
  - Ngrok API를 통한 외부망 접속 링크 자동 생성
  - 게임 내 이벤트(조우, 데미지, 포획 등)를 실시간으로 보여주는 웹 System Log UI

<br>

## 하드웨어 요구사항 (Hardware Requirements)

1. **노트북 (또는 데스크탑 + 웹캠):** 제스처 인식 및 서버 구동용
2. **스마트폰:** 체스보드를 비추고 AR 화면을 확인할 웹 대시보드 접속용
3. **체스보드 출력물:** 가로 8칸, 세로 6칸 (내부 코너 기준 8x6, 칸당 30mm 권장) - assets 파일 내 'Checkerboard-A4-30mm-8x6.pdf' 참고

<br>

## 소프트웨어 설치 및 실행 방법 (Installation & Setup)

### 1. 사전 준비물
- Python 3.8 이상 권장
- [Ngrok 계정 및 Auth Token](https://dashboard.ngrok.com/get-started/your-authtoken) (무료)  
  현재 제작자의 계정으로 테스트 Token이 포함되어 있지만, Ngrok 서버가 불안정해질 수 있으므로 반드시 본인 계정으로 발급받은 토큰을 입력하는 것을 권장드립니다.

### 2. 패키지 설치
프로젝트 폴더에서 가상 환경(venv)을 생성하고 필요한 라이브러리를 설치합니다.
```bash
python -m venv venv
call venv\Scripts\activate   # Mac/Linux: source venv/bin/activate
pip install opencv-python mediapipe numpy trimesh pyrender flask flask-socketio requests  

### 3. Ngrok 토큰 입력
`main.py` 파일을 열고 상단의 `NGROK_TOKEN` 변수에 본인의 토큰을 입력합니다.
```python
NGROK_TOKEN = "여기에_본인의_토큰_입력" 
```

### 4. 에셋 및 캘리브레이션 데이터 세팅
해당 프로젝트에서는 아래와 같은 폴더 구조로 3D 모델과 카메라 캘리브레이션 데이터를 관리합니다.  
(체스보드 패턴과 3D 모델은 `assets` 폴더 내에 포함되어 있습니다.)
```text
📦 프로젝트 폴더
 ┣ 📂 assets
 ┃ ┗ 📂 models
 ┃    ┣ 📂 character  (캐릭터 모델: scene.gltf 등)
 ┃    ┣ 📂 bush       (부쉬 모델)
 ┃    ┣ 📂 creature_1 (크리처 1)
 ┃    ┣ 📂 creature_2 (크리처 2)
 ┃    ┗ 📂 creature_3 (크리처 3)
 ┣ 📂 calibration_data
 ┃    ┣ 📜 camera_matrix.npy
 ┃    ┗ 📜 dist_coeffs.npy
 ┣ 📂 calibration_data
 ┃    ┗ 📜 image_(number).jpg (현재 총 26장의 이미 존재)
```

만약 카메라 캘리브레이션 데이터가 없거나, calibration용 이미지를 추가하고 싶다면  
직접 찍은 이미지를 calibration_data에 추가해주세요.  
이후 'calibrate_camera.py'를 활용해 체스보드 패턴을 이용한 캘리브레이션을 진행하여 `camera_matrix.npy`와 `dist_coeffs.npy` 파일로 저장해 주세요.

### 5. 게임 실행 (Windows 전용)
폴더에 포함된 **`Run_Game.bat`** 파일을 더블클릭하면 자동으로 가상환경 활성화, 한글 인코딩 패치, 서버 구동이 완료되며 터미널에 **접속 링크**가 출력됩니다.  
(해당 링크를 `Ctrl + 클릭` 하여 브라우저를 열어주세요.)  

[.bat Run_Game]()

링크를 클릭하면 해당 화면의 웹사이트로 이어집니다.  


<br>

## 플레이 가이드 (How to Play)

### 탐험 모드 (EXPLORE State)
체스보드 위에 랜덤으로 생성된 부쉬(Bush)를 향해 이동하세요! 부쉬에 진입하면 확률적으로 야생의 크리처와 조우합니다.
- **방향 전환:** 손바닥을 펴고 화면을 향해 좌/우로 휙 넘기기 (Left/Right Swipe) 
  *(※ 체스판 기준 절대 각도로 90도씩 회전합니다.)*
- **전진:** 카메라를 향해 주먹(Fist) 꽉 쥐기

### 전투 모드 (BATTLE State)
크리처와 마주치면 전투 상태로 돌입하며 이동이 제한됩니다.
- **공격 (Hit):** 손바닥 좌/우 스와이프 (크리처 HP 2회 타격 시 승리)
- **포획 (Catch):** 주먹 쥐기 (확률적으로 몬스터 포획 성공)
- **도망 (Flee):** 손바닥을 활짝 펴고 위에서 아래로 슥 내리기 (Down Swipe) -> 이전 칸으로 후퇴

<br>

## 문제 해결 (Troubleshooting)

- **Q. 스마트폰 화면에 3D 모델이 뜨지 않습니다.**
  - 카메라가 체스보드의 전체 8x6 코너를 완벽하게 인식해야 합니다. 조명이 너무 어둡거나 밝아 체스보드 대비가 무너지지 않았는지 확인하세요.
- **Q. 손 인식(제스처)이 잘 안 됩니다.**
  - 역광이거나 배경이 복잡할 경우 MediaPipe의 인식률이 떨어집니다. 노트북 웹캠 화면(대시보드 좌측)을 보며 손뼈대(Landmark)가 초록색으로 잘 그려지는지 확인하세요. 도망(Down Swipe)은 손목의 Y축 변화를 감지하므로 팔 전체를 아래로 스무스하게 내려주세요.
- **Q. `Run_Game.bat` 실행 시 모듈이 없다고 뜹니다 (`ModuleNotFoundError`).**
  - 가상 환경 폴더명이 `venv`가 아니거나 폴더 위치가 다를 경우 발생합니다. `Run_Game.bat` 파일을 메모장으로 열어 `call venv\Scripts\activate` 부분의 경로를 수정해 주세요.

<br>

## Credits & 3D Assets  

* **Small Low Res Bush** * Author: [AlkaliDragon](https://sketchfab.com/AlkaliDragon)
  * Source: [Sketchfab Link](https://sketchfab.com/3d-models/small-low-res-bush-b04c3f2143c74fcdac16b1ba2a53d97b)

* **Desert Silent Assassin Model Low Poly** (Main Character)
  * Author: [Pigcraft](https://sketchfab.com/s8819296)
  * Source: [Sketchfab Link](https://sketchfab.com/3d-models/desert-silent-assassin-model-low-poly-4f3e07690d8f4428a5b97e2cbef0c5b4)

* **Gigantic Lowpoly monster fish** (Creature 1)
  * Author: [Khyoocumber](https://sketchfab.com/Khyoocumber)
  * Source: [Sketchfab Link](https://sketchfab.com/3d-models/gigantic-lowpoly-monster-fish-2bddbbde07474d4aae424c06b4b603d7)

* **Lowpoly Ice tiger pet** (Creature 2)
  * Author: [Khyoocumber](https://sketchfab.com/Khyoocumber)
  * Source: [Sketchfab Link](https://sketchfab.com/3d-models/lowpoly-ice-tiger-pet-6a6c23f54d34438ab3a8b514c0fd7278)

* **Lowpoly mech boss tripple canons** (Creature 3)
  * Author: [Khyoocumber](https://sketchfab.com/Khyoocumber)
  * Source: [Sketchfab Link](https://sketchfab.com/3d-models/lowpoly-mech-boss-tripple-canons-0e68941739814732818502113f032d9d)