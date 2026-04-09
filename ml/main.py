import cv2
import requests
import datetime
import threading
from ultralytics import YOLO
import time

# Load models
model = YOLO('yolov8n.pt')
pose_model = YOLO('yolov8n-pose.pt')

# Alert cooldown
last_alert_time = {}
COOLDOWN = 5

# Shared state between threads
latest_frame = None
detection_results = {
    "person_count": 0,
    "alert": False,
    "distress": False,
    "boxes": []
}
lock = threading.Lock()

def send_alert(alert_type):
    now = datetime.datetime.now()
    if alert_type in last_alert_time:
        if (now - last_alert_time[alert_type]).total_seconds() < COOLDOWN:
            return
    last_alert_time[alert_type] = now
    try:
        r = requests.post("http://10.86.122.254:5000/alert", json={
            "type": alert_type,
            "zone": "zone_2",
            "confidence": 0.9
        }, timeout=2)
        print(f"[ALERT SENT] {alert_type} → {r.status_code}")
    except Exception as e:
        print(f"[ALERT FAILED] {alert_type}: {e}")

def detection_thread(zone):
    global latest_frame, detection_results
    frame_count = 0

    while True:
        with lock:
            if latest_frame is None:
                time.sleep(0.05)
                continue
            frame = latest_frame.copy()

        frame_count += 1

        # Person detection
        results = model(frame, imgsz=256, conf=0.5, verbose=False)
        person_count = 0
        alert = False
        boxes_data = []
        for box in results[0].boxes:
            cls = int(box.cls[0])
            if cls == 0:
                person_count += 1
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                person_cx = (x1 + x2) // 2
                person_cy = (y1 + y2) // 2
                in_zone = zone[0] < person_cx < zone[2] and zone[1] < person_cy < zone[3]
                if in_zone:
                    alert = True
                boxes_data.append((x1, y1, x2, y2, in_zone))
        
        # Pose detection every 10th frame
        distress = detection_results["distress"]
        if frame_count % 10 == 0:
            pose_results = pose_model(frame, imgsz=256, conf=0.5, verbose=False)
            distress = False
            for person in pose_results[0].keypoints.xy:
                if len(person) >= 10:
                    if (person[9][1] < person[5][1] and
                            person[10][1] < person[6][1]):
                        distress = True

        with lock:
            detection_results["person_count"] = person_count
            detection_results["alert"] = alert
            detection_results["distress"] = distress
            detection_results["boxes"] = boxes_data

        # Send alerts
        if person_count > 3:
            send_alert("crowd")
        if alert:
            send_alert("breach")
        if distress:
            send_alert("distress")

def run():
    global latest_frame

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    zone = (200, 50, 450, 380)

    # Start detection in background thread
    t = threading.Thread(target=detection_thread, args=(zone,), daemon=True)
    t.start()
    
    cv2.namedWindow("Campus Watchdog", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Campus Watchdog", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    time.sleep(2)

    while True:
        cap.grab()
        ret, frame = cap.retrieve()
        if not ret:
            break

        # Update shared frame
        with lock:
            latest_frame = frame.copy()
            person_count = detection_results["person_count"]
            alert = detection_results["alert"]
            distress = detection_results["distress"]
            boxes = detection_results["boxes"]

        for (x1, y1, x2, y2, in_zone) in boxes:
            color = (0, 0, 255) if in_zone else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Draw everything on frame
        cv2.rectangle(frame, (zone[0], zone[1]), (zone[2], zone[3]), (0, 0, 255), 2)
        cv2.putText(frame, "RESTRICTED", (zone[0], zone[1]-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.putText(frame, f'Persons: {person_count}', (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        if person_count > 3:
            cv2.putText(frame, "ALERT: CROWD DETECTED", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        if alert:
            cv2.putText(frame, "ALERT: RESTRICTED ZONE BREACH", (20, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        if distress:
            cv2.putText(frame, "ALERT: DISTRESS GESTURE DETECTED", (20, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("Campus Watchdog", frame)
        cv2.setWindowProperty("Campus Watchdog", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()