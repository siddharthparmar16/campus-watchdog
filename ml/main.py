import cv2
import requests
import datetime
import threading
import time
from flask import Flask, Response as FlaskResponse

# Load cascades
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

drowsy_count = 0
relaxed_count = 0

# Alert cooldown
last_alert_time = {}
COOLDOWN = 10

# Shared state
latest_frame = None
detection_results = {
    "drowsy": False,
    "faces": [],
    "drowsy_duration": 0,
    "drowsy_count": 0,    # ← add
    "relaxed_count": 0
}
lock = threading.Lock()
drowsy_counter = 0
drowsy_duration_counter = 0

# Stream state
app_stream = Flask(__name__)
output_frame = None
stream_lock = threading.Lock()

def send_alert(alert_type):
    now = datetime.datetime.now()
    if alert_type in last_alert_time:
        if (now - last_alert_time[alert_type]).total_seconds() < COOLDOWN:
            return
    last_alert_time[alert_type] = now
    try:
        r = requests.post("http://10.86.122.254:5000/alert", json={
                "type": "drowsy",
                "zone": "zone_2",
                "confidence": 0.9,
                "extra": {
                    "alert_level": alert_type,
                    "drowsy_count": drowsy_count,
                    "relaxed_count": relaxed_count
                }
            }, timeout=2)
        print(f"[ALERT SENT] {alert_type} → {r.status_code}")
    except Exception as e:
        print(f"[ALERT FAILED] {alert_type}: {e}")

def generate_stream():
    global output_frame
    while True:
        with stream_lock:
            if output_frame is None:
                time.sleep(0.033)
                continue
            _, buffer = cv2.imencode('.jpg', output_frame,
                                     [cv2.IMWRITE_JPEG_QUALITY, 60])
            frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               frame_bytes + b'\r\n')
        time.sleep(0.033)

@app_stream.route('/stream')
def video_stream():
    return FlaskResponse(generate_stream(),
                         mimetype='multipart/x-mixed-replace; boundary=frame')

def start_stream_server():
    app_stream.run(host='0.0.0.0', port=5001,
                   debug=False, use_reloader=False)

def detection_thread():
    global latest_frame, detection_results, drowsy_counter, drowsy_duration_counter, drowsy_count, relaxed_count
    frame_count = 0

    while True:
        with lock:
            if latest_frame is None:
                time.sleep(0.05)
                continue
            frame = latest_frame.copy()

        frame_count += 1

        if frame_count % 5 == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.3,
                minNeighbors=5, minSize=(60, 60)
            )

            eyes_detected = False
            faces_info = []

            for (fx, fy, fw, fh) in faces:
                roi_gray = gray[fy:fy+fh, fx:fx+fw]
                eyes = eye_cascade.detectMultiScale(
                    roi_gray, scaleFactor=1.1,
                    minNeighbors=5, minSize=(20, 20)
                )
                eyes_in_face = [(ex, ey, ew, eh) for (ex, ey, ew, eh) in eyes]
                faces_info.append((fx, fy, fw, fh, eyes_in_face))
                if len(eyes) >= 2:
                    eyes_detected = True
            
            drowsy_count = 0
            relaxed_count = 0
            for (fx, fy, fw, fh, eyes_in_face) in faces_info:
                if len(eyes_in_face) >= 2:
                    relaxed_count += 1
                else:
                    drowsy_count += 1

            if len(faces) > 0 and not eyes_detected:
                drowsy_counter += 1
                drowsy_duration_counter += 1
            else:
                drowsy_counter = max(0, drowsy_counter - 1)
                if drowsy_counter == 0:
                    drowsy_duration_counter = 0

            drowsy = drowsy_counter >= 8

            with lock:
                detection_results["drowsy"] = drowsy
                detection_results["faces"] = faces_info
                detection_results["drowsy_duration"] = drowsy_duration_counter
                detection_results["drowsy_count"] = drowsy_count      # ← add
                detection_results["relaxed_count"] = relaxed_count    # ← add

            if drowsy_counter == 8:
                send_alert("silent")

            if drowsy_duration_counter > 0 and drowsy_duration_counter % 40 == 0:
                send_alert("sound")

def run():
    global latest_frame, output_frame

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Start detection thread
    t = threading.Thread(target=detection_thread, daemon=True)
    t.start()

    # Start stream server
    stream_thread = threading.Thread(target=start_stream_server, daemon=True)
    stream_thread.start()
    print("[STREAM] Live feed at http://192.168.14.117:5001/stream")

    cv2.namedWindow("Campus Watchdog", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Campus Watchdog", cv2.WND_PROP_FULLSCREEN,
                           cv2.WINDOW_FULLSCREEN)
    time.sleep(2)

    while True:
        cap.grab()
        ret, frame = cap.retrieve()
        if not ret:
            break

        with lock:
            latest_frame = frame.copy()
            drowsy = detection_results["drowsy"]
            faces = detection_results["faces"]
            drowsy_duration = detection_results["drowsy_duration"]
            drowsy_count = detection_results["drowsy_count"]      # ← add
            relaxed_count = detection_results["relaxed_count"]    # ← add

        # Draw face and eye boxes
        for (fx, fy, fw, fh, eyes) in faces:
            cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (255, 0, 0), 2)
            if eyes:
                cv2.putText(frame, "RELAXED", (fx, fy-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                for (ex, ey, ew, eh) in eyes:
                    cv2.rectangle(frame,
                                  (fx+ex, fy+ey),
                                  (fx+ex+ew, fy+ey+eh),
                                  (0, 255, 0), 1)
            else:
                cv2.putText(frame, "DROWSY", (fx, fy-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        # Status text
        if drowsy:
            cv2.putText(frame, "ALERT: STUDENT DROWSINESS DETECTED",
                        (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 165, 255), 2)
            if drowsy_duration > 40:
                cv2.putText(frame, "WARNING: PROLONGED DROWSINESS",
                            (20, 90), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, (0, 0, 255), 2)
        else:
            cv2.putText(frame, "STATUS: ALL STUDENTS RELAXED",
                        (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)
            
        cv2.putText(frame, f'Relaxed: {relaxed_count}', (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, f'Drowsy: {drowsy_count}', (20, 160),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

        # Update stream output
        with stream_lock:
            output_frame = frame.copy()

        cv2.imshow("Campus Watchdog", frame)
        cv2.setWindowProperty("Campus Watchdog", cv2.WND_PROP_FULLSCREEN,
                               cv2.WINDOW_FULLSCREEN)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()
