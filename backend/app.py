from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from collections import deque
import threading
import time
import uuid
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ── config ──────────────────────────────────────
COOLDOWN_SECONDS = 10
MAX_ALERTS = 100
IDLE_CLEAR_SECONDS = 15

ZONE_NAMES = {
    "zone_1": "Main Gate",
    "zone_2": "Computer Lab",
    "zone_3": "Canteen",
    "zone_4": "Server Room",
    "zone_5": "Corridor B",
    "zone_6": "Classroom A",
    "zone_7": "Classroom B",
    "zone_8": "Classroom C",
}

ROUTING_TABLE = {
    "crowd":    {"authority": "Security Guard",  "severity": "medium"},
    "breach":   {"authority": "HOD + Security",  "severity": "high"},
    "distress": {"authority": "Nearest Faculty", "severity": "critical"},
    "phone":    {"authority": "Class Teacher",   "severity": "medium"},
    "drowsy":   {"authority": "Class Teacher",   "severity": "high"},
}

# ── in-memory store ──────────────────────────────
alerts = deque(maxlen=MAX_ALERTS)
alert_lock = threading.Lock()
sse_subscribers = []
sse_lock = threading.Lock()
cooldowns = {}
last_alert_received = time.time()

# ── idle watcher thread ──────────────────────────
def idle_watcher():
    global last_alert_received
    while True:
        time.sleep(5)
        if time.time() - last_alert_received > IDLE_CLEAR_SECONDS:
            with alert_lock:
                if len(alerts) > 0:
                    alerts.clear()
                    cooldowns.clear()
                    print("[WATCHDOG] No alerts for 15s — store cleared automatically")

threading.Thread(target=idle_watcher, daemon=True).start()

# ── helpers ──────────────────────────────────────
def is_on_cooldown(zone, alert_type):
    key = f"{zone}_{alert_type}"
    now = time.time()
    if key in cooldowns and now - cooldowns[key] < COOLDOWN_SECONDS:
        return True
    cooldowns[key] = now
    return False

def build_alert(alert_type, zone, confidence, extra=None):
    routing = ROUTING_TABLE.get(alert_type, {"authority": "Security", "severity": "low"})
    return {
        "id":         str(uuid.uuid4())[:8],
        "type":       alert_type,
        "zone":       zone,
        "zone_name":  ZONE_NAMES.get(zone, zone),
        "severity":   routing["severity"],
        "authority":  routing["authority"],
        "confidence": round(float(confidence), 2),
        "timestamp":  datetime.now().strftime("%H:%M:%S"),
        "extra":      extra or {},
    }

def push_to_subscribers(alert):
    data = f"data: {json.dumps(alert)}\n\n"
    with sse_lock:
        dead = []
        for q in sse_subscribers:
            try:
                q.append(data)
            except Exception:
                dead.append(q)
        for q in dead:
            sse_subscribers.remove(q)

# ── routes ───────────────────────────────────────
@app.route("/")
def health():
    return '''<!DOCTYPE html>
<html>
<head>
  <title>Campus Watchdog</title>
  <meta charset="UTF-8">
  <style>
    body { background: #1a1a1a; color: #d4d4d4; font-family: monospace; font-size: 14px; padding: 20px; }
    .key { color: #9cdcfe; }
    .str { color: #ce9178; }
    .num { color: #b5cea8; transition: color 0.3s; }
    .num.updated { color: #4ec9b0; }
    .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #555; margin-right: 6px; }
    .dot.live { background: #4ec9b0; }
    #status { font-size: 12px; color: #888; margin-bottom: 16px; }
  </style>
</head>
<body>
  <div id="status"><span class="dot" id="dot"></span>Connecting to live stream...</div>
  <pre>{
  <span class="key">"status"</span>: <span class="str">"AI Campus Watchdog Running"</span>,
  <span class="key">"alerts_stored"</span>: <span class="num" id="alert-count">0</span>,
  <span class="key">"alert_types"</span>: <span class="str">"crowd | breach | distress | phone | drowsy"</span>,
  <span class="key">"endpoints"</span>: {
    <span class="key">"DEL"</span>: <span class="str">"/alerts/clear"</span>,
    <span class="key">"GET"</span>: <span class="str">"/alerts"</span>,
    <span class="key">"MAP"</span>: <span class="str">"/zones"</span>,
    <span class="key">"POST"</span>: <span class="str">"/alert"</span>,
    <span class="key">"SSE"</span>: <span class="str">"/stream"</span>
  }
}</pre>
  <script>
    const countEl = document.getElementById("alert-count");
    const dot = document.getElementById("dot");
    const statusEl = document.getElementById("status");

    fetch("/alerts").then(r => r.json()).then(data => {
      countEl.textContent = data.length;
    });

    const es = new EventSource("/stream");
    es.onopen = () => {
      dot.className = "dot live";
      statusEl.innerHTML = "<span class=\\"dot live\\"></span>Live — updates automatically";
    };
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "connected") return;
      if (data.type === "cleared") {
        countEl.textContent = "0";
        return;
      }
      const current = parseInt(countEl.textContent) || 0;
      countEl.textContent = current + 1;
      countEl.classList.add("updated");
      setTimeout(() => countEl.classList.remove("updated"), 800);
    };
    es.onerror = () => {
      dot.className = "dot";
      statusEl.innerHTML = "<span class=\\"dot\\"></span>Reconnecting...";
    };
  </script>
</body>
</html>''', 200, {'Content-Type': 'text/html'}


@app.route("/alert", methods=["POST"])
def receive_alert():
    global last_alert_received
    data = request.get_json(force=True)
    alert_type = data.get("type")
    zone       = data.get("zone", "zone_1")
    confidence = data.get("confidence", 1.0)
    extra      = data.get("extra", {})

    if not alert_type:
        return jsonify({"error": "Missing: type"}), 400
    if alert_type not in ROUTING_TABLE:
        return jsonify({"error": f"Unknown type. Use: crowd, breach, distress, phone, drowsy"}), 400
    if zone not in ZONE_NAMES:
        return jsonify({"error": f"Unknown zone. Use: zone_1 to zone_8"}), 400
    if is_on_cooldown(zone, alert_type):
        return jsonify({"status": "cooldown"}), 200

    last_alert_received = time.time()

    alert = build_alert(alert_type, zone, confidence, extra)
    with alert_lock:
        alerts.appendleft(alert)
    push_to_subscribers(alert)
    print(f"[{alert['timestamp']}] {alert_type.upper():8} | {alert['zone_name']:15} -> {alert['authority']}")
    return jsonify({"status": "ok", "alert_id": alert["id"]}), 201


@app.route("/alerts", methods=["GET"])
def get_alerts():
    limit = int(request.args.get("limit", 50))
    with alert_lock:
        result = list(alerts)[:limit]
    return jsonify(result)


@app.route("/alerts/clear", methods=["DELETE"])
def clear_alerts():
    with alert_lock:
        alerts.clear()
    cooldowns.clear()
    return jsonify({"status": "cleared"})


@app.route("/zones", methods=["GET"])
def get_zones():
    return jsonify(ZONE_NAMES)


@app.route("/stream")
def stream():
    my_queue = []
    with sse_lock:
        sse_subscribers.append(my_queue)
    def generate():
        yield 'data: {"type": "connected"}\n\n'
        while True:
            if my_queue:
                yield my_queue.pop(0)
            else:
                yield ": heartbeat\n\n"
                time.sleep(1)
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.route("/dashboard")
def dashboard():
    return send_file("../frontend/main.html")


# ── start ─────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  AI Campus Watchdog — Backend")
    print("  Running on http://0.0.0.0:5000")
    print("  Alert types: crowd, breach, distress, phone, drowsy")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
