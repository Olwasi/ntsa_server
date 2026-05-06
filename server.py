"""
NTSA Lane Violation Cloud Server
==================================
- Receives violation reports from the Pi via POST /api/violation
- Serves a live NTSA dashboard at /
- Sends email to the driver on every fine (violation >= 3)
"""

import os
import base64
import smtplib
import datetime
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "douvonneli@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "eygd jwaa nmon jzyr")

# ============================================================
# IN-MEMORY VIOLATION STORE
# ============================================================
store_lock = threading.Lock()
violations = {}

def _seed_dummy():
    dummy_plate = "KAA123B"
    dummy_email = "dummy.driver@example.com"
    base_date = datetime.date.today().strftime("%Y-%m-%d")
    dummy_data = [
        {
            "fine_ref": f"NTSA-{base_date}-KAA123B-0001",
            "vehicle_plate": dummy_plate,
            "driver_email": dummy_email,
            "date": base_date,
            "time": "08:14:32",
            "session_violations": 3,
            "total_violations": 3,
            "offence": "Illegal crossing of yellow continuous centre line",
            "image_b64": "",
        },
        {
            "fine_ref": f"NTSA-{base_date}-KAA123B-0002",
            "vehicle_plate": dummy_plate,
            "driver_email": dummy_email,
            "date": base_date,
            "time": "09:47:10",
            "session_violations": 4,
            "total_violations": 4,
            "offence": "Illegal crossing of yellow continuous centre line",
            "image_b64": "",
        },
        {
            "fine_ref": f"WARN-{base_date}-KAA123B-0003",
            "vehicle_plate": dummy_plate,
            "driver_email": dummy_email,
            "date": base_date,
            "time": "11:02:55",
            "session_violations": 1,
            "total_violations": 5,
            "offence": "Illegal crossing of yellow continuous centre line",
            "image_b64": "",
        },
    ]
    violations[dummy_plate] = dummy_data

_seed_dummy()

# ============================================================
# EMAIL HELPER
# ============================================================
def send_driver_email(violation):
    try:
        fine_ref = violation["fine_ref"]
        plate = violation["vehicle_plate"]
        driver_email = violation["driver_email"]
        date_s = violation["date"]
        time_s = violation["time"]
        total_v = violation["total_violations"]
        image_b64 = violation.get("image_b64", "")

        subject = f"NTSA Fine Notice – {fine_ref} – Vehicle {plate}"

        body = f"""Dear Driver,

This is an official notice from the National Transport and Safety Authority (NTSA).

Your vehicle ({plate}) has been recorded committing a traffic violation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fine Reference : {fine_ref}
Date           : {date_s}
Time           : {time_s}
Vehicle        : {plate}
Total Violations on Record : {total_v}
Offence        : Illegal crossing of yellow continuous centre line
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Photographic evidence of the violation is attached.

NTSA Traffic Monitoring Division
"""

        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = driver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if image_b64:
            img_bytes = base64.b64decode(image_b64)
            img_part = MIMEImage(img_bytes, name=f"evidence_{fine_ref}.jpg")
            msg.attach(img_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            srv.sendmail(GMAIL_ADDRESS, driver_email, msg.as_string())

        print(f"[EMAIL] Sent to {driver_email} for {fine_ref}")

    except Exception as e:
        print(f"[EMAIL] Failed: {e}")

# ============================================================
# API ENDPOINT
# ============================================================
@app.route("/api/violation", methods=["POST"])
def receive_violation():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no data"}), 400

    plate = data.get("vehicle_plate", "UNKNOWN").upper().replace(" ", "")
    session_v = data.get("session_violations", 0)

    with store_lock:
        if plate not in violations:
            violations[plate] = []
        violations[plate].append(data)

    print(f"[SERVER] Violation received: {data.get('fine_ref')} – {plate} (session={session_v})")

    if session_v >= 3:
        print(f"[SERVER] Sending email for fine")
        threading.Thread(target=send_driver_email, args=(data,), daemon=True).start()

    return jsonify({"status": "ok"}), 200

# ============================================================
# DASHBOARD WITH ROAD BACKGROUND
# ============================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="5">
  <title>NTSA Live Violation Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
      background: linear-gradient(rgba(10, 14, 26, 0.85), rgba(15, 22, 34, 0.92)), url('https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?q=80&w=2069&auto=format&fit=crop');
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
      color: #ffffff;
      min-height: 100vh;
    }
    header {
      background: linear-gradient(135deg, #0a1a2f 0%, #0b2b3b 100%);
      border-bottom: 3px solid #ff6b35;
      padding: 20px 40px;
      display: flex;
      align-items: center;
      gap: 20px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .logo {
      background: linear-gradient(135deg, #ff6b35 0%, #ff8c42 100%);
      width: 55px;
      height: 55px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
      box-shadow: 0 2px 10px rgba(255,107,53,0.4);
    }
    .titles h1 {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 1px;
      background: linear-gradient(135deg, #ff6b35, #ffb347);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      font-family: 'Orbitron', monospace;
    }
    .titles p {
      font-size: 11px;
      color: #a0b3c9;
      margin-top: 4px;
      letter-spacing: 0.5px;
    }
    .live-badge {
      margin-left: auto;
      background: linear-gradient(135deg, #00d4ff, #0088ff);
      color: #fff;
      font-size: 11px;
      font-weight: 700;
      padding: 6px 14px;
      border-radius: 20px;
      animation: pulse 2s infinite;
      box-shadow: 0 0 15px rgba(0,180,255,0.5);
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.8; transform: scale(1.02); }
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;
      margin-bottom: 30px;
      padding: 0;
    }
    .stat-card {
      background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 16px;
      padding: 24px 20px;
      text-align: center;
      transition: transform 0.2s, box-shadow 0.2s;
      backdrop-filter: blur(10px);
    }
    .stat-card:hover {
      transform: translateY(-5px);
      box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    .stat-card .value {
      font-size: 42px;
      font-weight: 800;
      font-family: 'Orbitron', monospace;
    }
    .stat-card .label {
      font-size: 12px;
      font-weight: 600;
      margin-top: 8px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #a0b3c9;
    }
    .stat-card.danger .value { background: linear-gradient(135deg, #ff416c, #ff4b2b); -webkit-background-clip: text; background-clip: text; color: #ff4b2b; }
    .stat-card.warn .value { background: linear-gradient(135deg, #f7b733, #fc4a1a); -webkit-background-clip: text; background-clip: text; color: #f7b733; }
    .stat-card.info .value { background: linear-gradient(135deg, #00d4ff, #0088ff); -webkit-background-clip: text; background-clip: text; color: #00d4ff; }
    .stat-card.success .value { background: linear-gradient(135deg, #00e676, #00b0ff); -webkit-background-clip: text; background-clip: text; color: #00e676; }
    main { padding: 30px 40px; max-width: 1600px; margin: 0 auto; }
    .card {
      background: rgba(22, 27, 34, 0.85);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 20px;
      padding: 24px;
    }
    .card h2 {
      font-size: 16px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 2px solid rgba(255,107,53,0.5);
      color: #ff8c42;
    }
    #map-placeholder {
      background: linear-gradient(135deg, #0a1a2f, #0d1f2d);
      border-radius: 12px;
      height: 260px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 12px;
      color: #ff8c42;
      font-size: 14px;
      border: 1px solid rgba(255,107,53,0.3);
    }
    #map-placeholder svg { filter: drop-shadow(0 0 10px rgba(255,107,53,0.5)); }
    .tabs {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }
    .tab {
      padding: 8px 24px;
      border-radius: 30px;
      border: 1px solid rgba(255,255,255,0.2);
      background: rgba(10,14,26,0.8);
      color: #a0b3c9;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.3s;
    }
    .tab.active, .tab:hover {
      background: linear-gradient(135deg, #ff6b35, #ff8c42);
      border-color: #ff6b35;
      color: #fff;
      box-shadow: 0 4px 15px rgba(255,107,53,0.3);
    }
    .table-wrap { overflow-x: auto; border-radius: 12px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    thead th {
      background: rgba(255,107,53,0.15);
      color: #ff8c42;
      font-weight: 700;
      font-size: 12px;
      letter-spacing: 0.5px;
      padding: 14px 12px;
      text-align: left;
      border-bottom: 2px solid rgba(255,107,53,0.5);
    }
    tbody tr {
      border-bottom: 1px solid rgba(255,255,255,0.05);
      transition: background 0.2s;
    }
    tbody tr:hover { background: rgba(255,107,53,0.1); }
    tbody td { padding: 12px; color: #e0e6f0; }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 700;
    }
    .badge-fine { background: linear-gradient(135deg, #ff416c, #ff4b2b); color: #fff; }
    .badge-warning { background: linear-gradient(135deg, #f7b733, #fc4a1a); color: #fff; }
    .thumb {
      width: 70px;
      height: 50px;
      object-fit: cover;
      border-radius: 8px;
      border: 2px solid #ff6b35;
      cursor: pointer;
      transition: transform 0.2s;
    }
    .thumb:hover { transform: scale(2); border-radius: 4px; }
    .no-img {
      width: 70px;
      height: 50px;
      background: rgba(255,255,255,0.05);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      color: #5a6e8a;
    }
    #modal {
      display: none;
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.95);
      z-index: 1000;
      align-items: center;
      justify-content: center;
    }
    #modal.open { display: flex; }
    #modal img {
      max-width: 90vw;
      max-height: 85vh;
      border-radius: 12px;
      border: 3px solid #ff6b35;
      box-shadow: 0 0 50px rgba(255,107,53,0.3);
    }
    #modal-close {
      position: fixed; top: 30px; right: 40px;
      font-size: 40px; color: #ff6b35; cursor: pointer;
      font-weight: bold;
    }
    footer {
      text-align: center;
      padding: 25px;
      color: #5a6e8a;
      font-size: 12px;
      border-top: 1px solid rgba(255,255,255,0.05);
      margin-top: 30px;
    }
    @media (max-width: 900px) {
      .stats { grid-template-columns: repeat(2, 1fr); }
      main { padding: 20px; }
    }
  </style>
</head>
<body>
<header>
  <div class="logo"><span>🚦</span></div>
  <div class="titles">
    <h1>NTSA TRAFFIC VIOLATION MONITORING SYSTEM</h1>
    <p>National Transport and Safety Authority | Real-Time Enforcement Dashboard</p>
  </div>
  <span class="live-badge"><span>🟢</span> LIVE MONITORING</span>
</header>
<main>
  <div class="stats">
    <div class="stat-card danger"><div class="value">{{ total_fines }}</div><div class="label">🚨 FINES ISSUED</div></div>
    <div class="stat-card warn"><div class="value">{{ total_warnings }}</div><div class="label">⚠️ WARNINGS</div></div>
    <div class="stat-card info"><div class="value">{{ total_vehicles }}</div><div class="label">🚗 VEHICLES MONITORED</div></div>
    <div class="stat-card success"><div class="value">{{ last_updated }}</div><div class="label">🕐 LAST UPDATED</div></div>
  </div>
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-bottom: 30px;">
    <div class="card">
      <h2>📊 VIOLATIONS PER VEHICLE</h2>
      <canvas id="barChart" height="220"></canvas>
    </div>
    <div class="card">
      <h2>📍 LIVE INCIDENT MAP</h2>
      <div id="map-placeholder">
        <svg width="50" height="50" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
          <circle cx="12" cy="9" r="2.5"/>
        </svg>
        <span>🚧 GPS Integration Pending</span>
        <span style="font-size: 11px; color: #5a6e8a;">Live location tracking coming soon</span>
      </div>
    </div>
  </div>
  <div class="card">
    <h2>📋 VIOLATION LOG</h2>
    <div class="tabs" id="tabs">
      {% for plate in plates %}
      <div class="tab {% if loop.first %}active{% endif %}" onclick="showTab('{{ plate }}', this)">{{ plate }}</div>
      {% endfor %}
    </div>
    {% for plate, v_list in all_violations.items() %}
    <div class="table-wrap tab-content" id="tab-{{ plate }}" style="{% if not loop.first %}display:none{% endif %}">
      {% if v_list %}
      <table>
        <thead>
          <tr><th>🔖 Fine Reference</th><th>📅 Date</th><th>⏰ Time</th><th>📝 Offence</th><th>🎯 Session</th><th>📈 Total</th><th>🏷️ Type</th><th>📸 Evidence</th></tr>
        </thead>
        <tbody>
          {% for v in v_list | reverse %}
          <tr>
            <td style="font-family: monospace;">{{ v.fine_ref }}</td>
            <td>{{ v.date }}</td>
            <td>{{ v.time }}</td>
            <td>{{ v.offence }}</td>
            <td style="text-align: center;"><strong>{{ v.session_violations }}</strong></td>
            <td style="text-align: center;"><strong>{{ v.total_violations }}</strong></td>
            <td>{% if v.session_violations >= 3 %}<span class="badge badge-fine">🔴 FINE</span>{% else %}<span class="badge badge-warning">🟠 WARNING</span>{% endif %}</td>
            <td>{% if v.image_b64 %}<img class="thumb" src="data:image/jpeg;base64,{{ v.image_b64 }}" onclick="openModal(this.src)">{% else %}<div class="no-img">📷 No image</div>{% endif %}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <p style="color: #5a6e8a; padding: 40px; text-align: center;">🚗 No violations recorded for {{ plate }} yet</p>
      {% endif %}
    </div>
    {% endfor %}
  </div>
</main>
<div id="modal" onclick="closeModal()">
  <span id="modal-close" onclick="closeModal()">&times;</span>
  <img id="modal-img" src="">
</div>
<footer>
  <p>NTSA Traffic Monitoring System | Powered by AI & IR Sensors | Data refreshes every 5 seconds</p>
  <p>&copy; {{ year }} National Transport and Safety Authority — Keeping Kenyan Roads Safe</p>
</footer>
<script>
  const ctx = document.getElementById('barChart').getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: {{ chart_labels | tojson }},
      datasets: [
        { label: '🔴 Fines', data: {{ chart_fines | tojson }}, backgroundColor: 'rgba(255, 65, 108, 0.8)', borderColor: '#ff416c', borderWidth: 2, borderRadius: 8, barPercentage: 0.6 },
        { label: '🟠 Warnings', data: {{ chart_warnings | tojson }}, backgroundColor: 'rgba(247, 183, 51, 0.8)', borderColor: '#f7b733', borderWidth: 2, borderRadius: 8, barPercentage: 0.6 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { labels: { color: '#e0e6f0', font: { size: 12, weight: 'bold' } } } },
      scales: {
        x: { ticks: { color: '#a0b3c9', font: { weight: 'bold' } }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { ticks: { color: '#a0b3c9', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true }
      }
    }
  });
  function showTab(plate, el) {
    document.querySelectorAll('.tab-content').forEach(d => d.style.display = 'none');
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + plate).style.display = 'block';
    el.classList.add('active');
    localStorage.setItem('selectedTab', plate);
  }
  function openModal(src) {
    document.getElementById('modal-img').src = src;
    document.getElementById('modal').classList.add('open');
  }
  function closeModal() {
    document.getElementById('modal').classList.remove('open');
  }
  window.addEventListener('DOMContentLoaded', function() {
    const savedTab = localStorage.getItem('selectedTab');
    if (savedTab) {
      const tabs = document.querySelectorAll('.tab');
      for (let tab of tabs) {
        if (tab.innerText === savedTab) {
          showTab(savedTab, tab);
          break;
        }
      }
    }
  });
</script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    with store_lock:
        all_v = dict(violations)

    plates = list(all_v.keys())
    chart_fines = []
    chart_warnings = []
    total_fines = 0
    total_warnings = 0

    for plate in plates:
        fines = sum(1 for v in all_v[plate] if v["session_violations"] >= 3)
        warnings = sum(1 for v in all_v[plate] if v["session_violations"] < 3)
        chart_fines.append(fines)
        chart_warnings.append(warnings)
        total_fines += fines
        total_warnings += warnings

    return render_template_string(
        DASHBOARD_HTML,
        all_violations=all_v,
        plates=plates,
        chart_labels=plates,
        chart_fines=chart_fines,
        chart_warnings=chart_warnings,
        total_fines=total_fines,
        total_warnings=total_warnings,
        total_vehicles=len(plates),
        last_updated=datetime.datetime.now().strftime("%H:%M:%S"),
        year=datetime.date.today().year,
    )

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
