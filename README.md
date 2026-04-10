# 🎓 Campus Watchdog
### AI-Powered Student Drowsiness Detection System
**Unitedworld Institute of Technology | 36-Hour Hackathon | April 2026**

---

## 🧠 What It Does

Campus Watchdog is a real-time student wellness monitoring system that uses computer vision to detect drowsiness in classroom students and instantly notifies the teacher via a web dashboard.

The system monitors students through a classroom camera, detects whether their eyes are open or closed, and classifies each student as **RELAXED** or **DROWSY** in real time.

---

## ⚡ Key Features

- **Real-time drowsiness detection** using OpenCV Haar Cascade face and eye detection
- **Two-level alert system:**
  - Silent notification — sent immediately when drowsiness first detected
  - Sound notification — sent if drowsiness continues for 10+ seconds
- **Live camera feed** streamed directly to teacher's dashboard
- **Student count tracking** — shows number of relaxed vs drowsy students
- **Teacher login system** — teacher enters name and classroom number
- **Beautiful dark dashboard** with real-time SSE updates
- **Alert history** with timestamps

---

## 🏗️ System Architecture
---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Computer Vision | OpenCV, Haar Cascade |
| Streaming | MJPEG over Flask |
| Backend | Python, Flask, Flask-CORS, SSE |
| Frontend | HTML, CSS, JavaScript |
| Real-time | Server-Sent Events (SSE) |
| Threading | Python threading module |

---

## 🚀 How To Run

### Prerequisites
```bash
pip install opencv-python flask flask-cors requests
```

### Step 1 — Start Flask Backend
```bash
cd backend
python app.py
```
Backend runs at `http://0.0.0.0:5000`

### Step 2 — Start Detection
```bash
cd ml
python main.py
```
- OpenCV window opens fullscreen
- Live stream available at `http://YOUR_IP:5001/stream`

### Step 3 — Open Dashboard
Open in any browser on same WiFi:
---

## 👥 Team

| Member | Role |
|--------|------|
| Sidd | ML Lead — drowsiness detection, streaming |
| Yashi | Backend — Flask API, SSE, alert routing |
| Naivam | Frontend — dashboard UI, login page |
| Aaska | Frontend support — alert components |
| Bhupendra | GitHub, README, demo video |
| Meet | Pitch deck, Shark Tank presentation |

---

## 🎯 Problem Statement

**Track 1 — Smart Campus**

Teachers cannot monitor every student simultaneously in large classrooms. Early detection of drowsiness improves student engagement, academic performance, and health outcomes.

---

## 💡 Real-World Impact

- Deployable on any existing classroom webcam
- No GPU required — runs on standard school computers
- Scalable to multiple classrooms from single dashboard
- Privacy-first — no video stored, only metadata transmitted

---

## 🏆 Hackathon

**Event:** KIIF x UIT 36-Hour Hackathon  
**Track:** T1 — Smart Campus  
**Date:** April 09-10, 2026  
**Institution:** Unitedworld Institute of Technology, Karnavati University
