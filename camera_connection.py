import cv2
import numpy as np
import base64
import os
import io
import logging
from flask import Flask, render_template
from flask_socketio import SocketIO
from pyngrok import ngrok
import qrcode

phone_frame_global = None

class PhoneCamera:
    def __init__(self, ngrok_token):
        global phone_frame_global
        self.is_running = True
        self.first_frame_received = False  # 첫 프레임 수신 확인용 변수
        
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        base_dir = os.path.abspath(os.path.dirname(__file__))
        template_dir = os.path.join(base_dir, 'templates')
        
        self.app = Flask(__name__, template_folder=template_dir)
        # [핵심] 모바일 기기의 고해상도 이미지가 끊기지 않도록 버퍼 제한을 5MB로 확장
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading', max_http_buffer_size=5000000)

        @self.app.route('/')
        def index():
            return render_template('index.html', public_url=self.public_url, qr_img=self.qr_img_str)

        @self.socketio.on('phone_frame_send')
        def handle_phone_frame(data):
            global phone_frame_global
            try:
                if not data or ',' not in data:
                    return

                encoded_data = data.split(',')[1]
                if not encoded_data:
                    return

                img_bytes = base64.b64decode(encoded_data)
                if len(img_bytes) == 0:
                    return

                nparr = np.frombuffer(img_bytes, np.uint8)
                if nparr.size == 0:
                    return

                decoded_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if decoded_frame is not None and decoded_frame.size > 0:
                    phone_frame_global = decoded_frame
                    
                    # [핵심] 휴대폰 영상이 "정상적으로" 최초 디코딩 되었을 때 터미널에 출력!
                    if not self.first_frame_received:
                        print("\n✅ [성공] 휴대폰 카메라 영상 수신 및 디코딩 시작!")
                        self.first_frame_received = True

            except Exception as e:
                pass

        print("\n--- 서버 설정 중 ---")
        ngrok.set_auth_token(ngrok_token)
        self.public_url = ngrok.connect(5000, bind_tls=True).public_url
        
        qr = qrcode.QRCode(box_size=6, border=4)
        qr.add_data(self.public_url)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        
        buffered = io.BytesIO()
        img_qr.save(buffered, format="JPEG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        self.qr_img_str = f"data:image/jpeg;base64,{qr_base64}"
        
        print(f"\n[QR코드 주소] 휴대폰으로 접속하세요: {self.public_url}")
        print(f"[대시보드 주소] 웹 브라우저를 열고 접속하세요: http://localhost:5000\n")

    def read(self):
        global phone_frame_global
        if phone_frame_global is not None:
            return True, phone_frame_global.copy()
        return False, None

    def release(self):
        self.is_running = False
        ngrok.kill()

def create_app(ngrok_token):
    cam_instance = PhoneCamera(ngrok_token)
    return cam_instance.app, cam_instance.socketio, cam_instance