import threading
import time
from flask import Flask, Response

app = Flask(__name__)

latest_frame_bytes = None
lock = threading.Lock()

def update_stream(frame_bytes: bytes):
    """Called by your main loop to push the newest frame."""
    global latest_frame_bytes
    with lock:
        latest_frame_bytes = frame_bytes

def generate_frames():
    global latest_frame_bytes
    while True:
        with lock:
            frame = latest_frame_bytes
            
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.1) # Wait briefly if the first frame hasn't arrived yet

@app.route('/')
def index():
    return '''
    <html>
      <head><title>Live Fire Camera</title></head>
      <body>
        <h1>Live Feed</h1>
        <img src="/video_feed" width="640" height="480">
      </body>
    </html>
    '''

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def start_server():
    server_thread = threading.Thread(
        target=app.run, 
        kwargs={'host': '0.0.0.0', 'port': 5000, 'debug': False, 'use_reloader': False},
        daemon=True
    )
    server_thread.start()
