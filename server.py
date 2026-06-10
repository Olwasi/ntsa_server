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
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "eygdjwaanmonjzyr")

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
            "offence": "Yellow line crossed - warning issued",
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
        fine_ref     = violation["fine_ref"]
        plate        = violation["vehicle_plate"]
        driver_email = violation["driver_email"]
        date_s       = violation["date"]
        time_s       = violation["time"]
        total_v      = violation["total_violations"]
        offence      = violation.get("offence", "Traffic violation")
        image_b64    = violation.get("image_b64", "")

        if "RECKLESS" in fine_ref:
            fine_amount = "KES 5,000"
        elif "NTSA" in fine_ref:
            fine_amount = "KES 3,000"
        elif "WARN" in fine_ref:
            fine_amount = "KES 0 (Warning — no charge)"
        elif "EXCPT" in fine_ref:
            fine_amount = "KES 0 (Exception — no charge)"
        else:
            fine_amount = "KES 3,000"

        subject = f"NTSA Fine Notice - {fine_ref} - Vehicle {plate}"
        body = f"""Dear Driver,

This is an official notice from the National Transport and Safety Authority (NTSA).

Your vehicle ({plate}) has been recorded committing a traffic violation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fine Reference             : {fine_ref}
Date                       : {date_s}
Time                       : {time_s}
Vehicle                    : {plate}
Offence                    : {offence}
Amount Payable             : {fine_amount}
Total Violations on Record : {total_v}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Photographic evidence of the violation is attached (if available).

NTSA Traffic Monitoring Division
"""
        msg = MIMEMultipart()
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = driver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if image_b64:
            img_bytes = base64.b64decode(image_b64)
            img_part  = MIMEImage(img_bytes, name=f"evidence_{fine_ref}.jpg")
            msg.attach(img_part)

        with smtplib.SMTP("smtp.gmail.com", 587) as srv:
            srv.ehlo()
            srv.starttls()
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

    plate     = data.get("vehicle_plate", "UNKNOWN").upper().replace(" ", "")
    session_v = data.get("session_violations", 0)

    with store_lock:
        if plate not in violations:
            violations[plate] = []
        violations[plate].append(data)

    print(f"[SERVER] Violation received: {data.get('fine_ref')} - {plate} (session={session_v})")

    if session_v >= 3:
        print(f"[EMAIL] Attempting to send for {data.get('fine_ref')}...")
        threading.Thread(target=send_driver_email, args=(data,), daemon=False).start()

    return jsonify({"status": "ok"}), 200

# ============================================================
# DASHBOARD HTML
# ============================================================
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="10">
<title>NTSA Live Monitoring Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=DM+Mono:wght@400;500&family=Barlow+Condensed:wght@300;400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {
  --page:    #f0f2f5;
  --surface: #ffffff;
  --navy:    #1a2332;
  --navy2:   #243040;
  --border:  #e0e4ea;
  --border2: #c8d0da;
  --red:     #c8102e;
  --red-bg:  #fef0f2;
  --red-bd:  #f4a8b4;
  --amb:     #b36b00;
  --amb-bg:  #fef8ec;
  --amb-bd:  #f4d08a;
  --grn:     #1a7a3c;
  --grn-bg:  #edf7f0;
  --grn-bd:  #a8d8b5;
  --blu:     #1a6eb5;
  --blu-bg:  #eff5fc;
  --blu-bd:  #a8c8e8;
  --t1:      #1a2332;
  --t2:      #4a5568;
  --t3:      #8a96a8;
  --fh: 'Rajdhani', sans-serif;
  --fd: 'DM Mono', monospace;
  --fb: 'Barlow Condensed', sans-serif;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--page);
  color: var(--t1);
  font-family: var(--fb);
  min-height: 100vh;
}

/* HEADER */
header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 40px;
  height: 68px;
  display: flex;
  align-items: center;
  gap: 18px;
  position: sticky;
  top: 0;
  z-index: 200;
  box-shadow: 0 1px 8px rgba(26,35,50,0.07);
  position: relative;
}
header::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg,
    #c8102e 0%, #c8102e 33%,
    #006600 33%, #006600 67%,
    #000    67%, #000    69.5%,
    #fff    69.5%, #fff  100%
  );
}
.logo-shield { width: 48px; height: 48px; flex-shrink: 0; }
.header-text h1 {
  font-family: var(--fh);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: var(--t1);
  line-height: 1;
}
.header-text p {
  font-family: var(--fd);
  font-size: 9px;
  color: var(--t3);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-top: 3px;
}
.header-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14px;
}
.live-pill {
  display: flex;
  align-items: center;
  gap: 7px;
  background: var(--grn-bg);
  border: 1px solid var(--grn-bd);
  padding: 5px 13px;
  border-radius: 2px;
  font-family: var(--fd);
  font-size: 10px;
  color: var(--grn);
  letter-spacing: 1.5px;
  text-transform: uppercase;
}
.live-dot {
  width: 6px; height: 6px;
  background: #27ae60;
  border-radius: 50%;
  animation: blink 1.4s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0.2;} }
.clock {
  font-family: var(--fd);
  font-size: 17px;
  color: var(--t2);
  letter-spacing: 2px;
}

/* SUBHEADER BAND */
.subband {
  background: var(--navy);
  padding: 7px 40px;
  display: flex;
  align-items: center;
  gap: 20px;
}
.subband span {
  font-family: var(--fd);
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #4a5e78;
}
.subband .hot { color: var(--red); }
.subband .sep { color: #2e3d52; }

/* MAIN */
main { padding: 24px 40px 40px; max-width: 1600px; margin: 0 auto; }

/* STAT CARDS */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 22px;
}
.stat {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid transparent;
  padding: 18px 20px 14px;
  box-shadow: 0 1px 4px rgba(26,35,50,0.04);
  transition: box-shadow 0.2s;
}
.stat:hover { box-shadow: 0 3px 12px rgba(26,35,50,0.09); }
.stat.danger { border-left-color: var(--red); }
.stat.warn   { border-left-color: var(--amb); }
.stat.info   { border-left-color: var(--blu); }
.stat.ok     { border-left-color: #006600; }
.stat-label {
  font-family: var(--fd);
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--t3);
  margin-bottom: 8px;
}
.stat-value {
  font-family: var(--fd);
  font-size: 36px;
  font-weight: 500;
  line-height: 1;
}
.stat.danger .stat-value { color: var(--red); }
.stat.warn   .stat-value { color: var(--amb); }
.stat.info   .stat-value { color: var(--blu); }
.stat.ok     .stat-value { color: #006600; font-size: 22px; margin-top: 6px; }
.stat-sub {
  font-family: var(--fd);
  font-size: 10px;
  color: var(--t3);
  margin-top: 6px;
}

/* PANELS */
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: 0 1px 4px rgba(26,35,50,0.04);
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border);
  background: #f7f9fb;
}
.panel-head-left {
  display: flex;
  align-items: center;
  gap: 9px;
}
.ph-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ph-dot.red   { background: var(--red); }
.ph-dot.amb   { background: var(--amb); }
.ph-dot.blu   { background: var(--blu); }
.ph-dot.grn   { background: #006600; }
.panel-title {
  font-family: var(--fh);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: var(--t2);
}
.panel-meta {
  font-family: var(--fd);
  font-size: 9px;
  color: var(--t3);
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

/* GRID LAYOUTS */
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 18px;
}
.grid-bottom {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 18px;
  margin-bottom: 18px;
}

/* MAP */
#map { height: 280px; width: 100%; }
.leaflet-container { background: #dce6f0; }
.leaflet-popup-content-wrapper {
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: 3px;
  box-shadow: 0 2px 8px rgba(26,35,50,0.12);
  padding: 0;
}
.leaflet-popup-content {
  margin: 10px 14px;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: var(--t1);
  line-height: 1.6;
}
.leaflet-popup-tip { background: var(--surface); }

/* CHART */
.chart-body {
  padding: 18px 20px;
  height: 280px;
  display: flex;
  align-items: center;
}

/* REGIONAL BARS */
.region-list { padding: 16px 18px; display: flex; flex-direction: column; gap: 10px; }
.ritem {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #f7f9fb;
  border: 1px solid var(--border);
  border-left: 3px solid var(--red);
}
.ritem.amb  { border-left-color: var(--amb); }
.ritem.blu  { border-left-color: var(--blu); }
.ritem.grn  { border-left-color: #006600; }
.ritem.grey { border-left-color: var(--t3); }
.rname {
  font-family: var(--fh);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--t2);
  min-width: 80px;
}
.rbar-wrap {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}
.rbar { height: 100%; border-radius: 2px; transition: width 1s ease; }
.rbar.red  { background: var(--red); }
.rbar.amb  { background: var(--amb); }
.rbar.blu  { background: var(--blu); }
.rbar.grn  { background: #006600; }
.rbar.grey { background: var(--t3); }
.rnum {
  font-family: var(--fd);
  font-size: 12px;
  font-weight: 500;
  min-width: 24px;
  text-align: right;
}
.rnum.red  { color: var(--red); }
.rnum.amb  { color: var(--amb); }
.rnum.blu  { color: var(--blu); }
.rnum.grn  { color: #006600; }
.rnum.grey { color: var(--t3); }

/* DOUGHNUT */
.doughnut-body { padding: 16px 20px; height: 260px; display: flex; align-items: center; justify-content: center; }

/* VIOLATION TABLE */
.tabs-bar {
  padding: 10px 14px;
  background: #f7f9fb;
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.tab-btn {
  padding: 4px 14px;
  background: transparent;
  border: 1px solid var(--border2);
  color: var(--t3);
  font-family: var(--fd);
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s;
}
.tab-btn:hover  { border-color: var(--red); color: var(--red); background: var(--red-bg); }
.tab-btn.active { background: var(--red-bg); border-color: var(--red-bd); color: var(--red); }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
  background: #f7f9fb;
  color: var(--t3);
  font-family: var(--fd);
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 11px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border2);
  white-space: nowrap;
}
tbody tr { border-bottom: 1px solid #f0f2f5; transition: background 0.12s; }
tbody tr:hover { background: #f7f9fb; }
tbody td { padding: 11px 16px; color: var(--t2); vertical-align: middle; }
.mono {
  font-family: var(--fd);
  font-size: 10px;
  letter-spacing: 0.5px;
  color: var(--t2);
}
.badge {
  display: inline-block;
  padding: 3px 10px;
  font-family: var(--fd);
  font-size: 9px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  border-radius: 2px;
  border: 1px solid;
}
.badge-fine  { background: var(--red-bg); border-color: var(--red-bd); color: var(--red); }
.badge-warn  { background: var(--amb-bg); border-color: var(--amb-bd); color: var(--amb); }
.badge-excpt { background: var(--grn-bg); border-color: var(--grn-bd); color: var(--grn); }
.thumb {
  width: 72px; height: 48px;
  object-fit: cover;
  border: 1px solid var(--border2);
  cursor: pointer;
  display: block;
  transition: border-color 0.15s, transform 0.15s;
}
.thumb:hover { border-color: var(--red); transform: scale(1.05); }
.no-img {
  width: 72px; height: 48px;
  background: #f0f2f5;
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--fd);
  font-size: 9px;
  color: var(--t3);
  letter-spacing: 1px;
}
.empty-state {
  padding: 48px;
  text-align: center;
  color: var(--t3);
  font-family: var(--fd);
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

/* MODAL */
#modal {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(26,35,50,0.85);
  z-index: 9999;
  align-items: center;
  justify-content: center;
}
#modal.open { display: flex; }
#modal img {
  max-width: 88vw;
  max-height: 84vh;
  border: 1px solid var(--border2);
  box-shadow: 0 8px 40px rgba(26,35,50,0.3);
}
#modal-close {
  position: fixed;
  top: 24px; right: 32px;
  font-size: 30px;
  color: #fff;
  cursor: pointer;
  line-height: 1;
  opacity: 0.7;
  transition: opacity 0.15s;
}
#modal-close:hover { opacity: 1; }

/* FOOTER */
footer {
  background: var(--navy);
  text-align: center;
  padding: 20px;
  font-family: var(--fd);
  font-size: 9px;
  color: #4a5e78;
  letter-spacing: 2px;
  text-transform: uppercase;
}
footer span { margin: 0 10px; }

@media (max-width: 1024px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .grid-2, .grid-bottom { grid-template-columns: 1fr; }
  main { padding: 18px 20px 32px; }
  header, .subband { padding-left: 20px; padding-right: 20px; }
}
</style>
</head>
<body>

<header>
  <svg class="logo-shield" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
    <circle cx="100" cy="100" r="97" fill="#006600" stroke="#ccc" stroke-width="3"/>
    <circle cx="100" cy="100" r="80" fill="#fff"/>
    <circle cx="100" cy="100" r="66" fill="#006600"/>
    <path d="M100 46 L116 60 L116 108 L100 126 L84 108 L84 60 Z" fill="#c8102e" stroke="#fff" stroke-width="2"/>
    <line x1="84" y1="84" x2="116" y2="84" stroke="#fff" stroke-width="3"/>
    <line x1="87" y1="38" x2="87" y2="152" stroke="#111" stroke-width="3.5"/>
    <line x1="113" y1="38" x2="113" y2="152" stroke="#111" stroke-width="3.5"/>
    <polygon points="87,38 83,50 91,50" fill="#111"/>
    <polygon points="113,38 109,50 117,50" fill="#111"/>
    <polygon points="87,152 83,140 91,140" fill="#111"/>
    <polygon points="113,152 109,140 117,140" fill="#111"/>
  </svg>
  <div class="header-text">
    <h1>NTSA Monitoring System</h1>
    <p>Traffic Violation Enforcement &bull; Real-Time Dashboard</p>
  </div>
  <div class="header-right">
    <div class="live-pill"><div class="live-dot"></div>Live</div>
    <div class="clock" id="clock">--:--:--</div>
  </div>
</header>

<div class="subband">
  <span>Session Active</span>
  <span class="sep">&bull;</span>
  {% for plate in plates %}
  <span class="hot">{{ plate }} &mdash; MONITORED</span>
  {% if not loop.last %}<span class="sep">&bull;</span>{% endif %}
  {% endfor %}
  <span class="sep">&bull;</span>
  <span>Nairobi Region</span>
  <span style="margin-left:auto;">Refresh: 10s</span>
</div>

<main>
  <div class="stats-grid">
    <div class="stat danger">
      <div class="stat-label">Fines Issued</div>
      <div class="stat-value">{{ total_fines }}</div>
      <div class="stat-sub">Session total</div>
    </div>
    <div class="stat warn">
      <div class="stat-label">Warnings</div>
      <div class="stat-value">{{ total_warnings }}</div>
      <div class="stat-sub">Pre-fine alerts</div>
    </div>
    <div class="stat info">
      <div class="stat-label">Vehicles Tracked</div>
      <div class="stat-value">{{ total_vehicles }}</div>
      <div class="stat-sub">Unique plates</div>
    </div>
    <div class="stat ok">
      <div class="stat-label">Last Updated</div>
      <div class="stat-value">{{ last_updated }}</div>
      <div class="stat-sub">Auto-refresh 10s</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-head-left"><div class="ph-dot blu"></div><span class="panel-title">Kenyan Road Network &mdash; Nairobi</span></div>
        <span class="panel-meta">Interactive Map</span>
      </div>
      <div id="map"></div>
    </div>
    <div class="panel">
      <div class="panel-head">
        <div class="panel-head-left"><div class="ph-dot amb"></div><span class="panel-title">Violations Per Vehicle</span></div>
        <span class="panel-meta">Current Session</span>
      </div>
      <div class="chart-body"><canvas id="barChart"></canvas></div>
    </div>
  </div>

  <div class="grid-bottom">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-head-left"><div class="ph-dot grn"></div><span class="panel-title">Regional Activity</span></div>
      </div>
      <div class="region-list">
        <div class="ritem">
          <div class="rname">Nairobi</div>
          <div class="rbar-wrap"><div class="rbar red" style="width:{{ nairobi_pct }}%"></div></div>
          <div class="rnum red">{{ nairobi_v }}</div>
        </div>
        <div class="ritem amb"><div class="rname">Mombasa</div><div class="rbar-wrap"><div class="rbar amb" style="width:0%"></div></div><div class="rnum amb">0</div></div>
        <div class="ritem blu"><div class="rname">Kisumu</div><div class="rbar-wrap"><div class="rbar blu" style="width:0%"></div></div><div class="rnum blu">0</div></div>
        <div class="ritem grn"><div class="rname">Nakuru</div><div class="rbar-wrap"><div class="rbar grn" style="width:0%"></div></div><div class="rnum grn">0</div></div>
        <div class="ritem grey"><div class="rname">Eldoret</div><div class="rbar-wrap"><div class="rbar grey" style="width:0%"></div></div><div class="rnum grey">0</div></div>
        <div class="ritem grey"><div class="rname">Thika</div><div class="rbar-wrap"><div class="rbar grey" style="width:0%"></div></div><div class="rnum grey">0</div></div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head">
        <div class="panel-head-left"><div class="ph-dot red"></div><span class="panel-title">Offence Breakdown</span></div>
      </div>
      <div class="doughnut-body"><canvas id="doughnutChart"></canvas></div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div class="panel-head-left"><div class="ph-dot red"></div><span class="panel-title">Violation Log</span></div>
      <span class="panel-meta">{{ total_fines + total_warnings }} Records</span>
    </div>
    <div class="tabs-bar" id="tabs">
      {% for plate in plates %}
      <button class="tab-btn {% if loop.first %}active{% endif %}" onclick="showTab('{{ plate }}', this)">{{ plate }}</button>
      {% endfor %}
    </div>
    {% for plate, v_list in all_violations.items() %}
    <div class="table-scroll tab-content" id="tab-{{ plate }}" {% if not loop.first %}style="display:none"{% endif %}>
      {% if v_list %}
      <table>
        <thead>
          <tr>
            <th>Fine Reference</th><th>Date</th><th>Time</th><th>Offence</th>
            <th>Session</th><th>Total</th><th>Status</th><th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {% for v in v_list | reverse %}
          <tr>
            <td class="mono">{{ v.fine_ref }}</td>
            <td>{{ v.date }}</td>
            <td class="mono">{{ v.time }}</td>
            <td>{{ v.offence }}</td>
            <td style="text-align:center;font-family:var(--fd);font-weight:500;">{{ v.session_violations }}</td>
            <td style="text-align:center;font-family:var(--fd);font-weight:500;">{{ v.total_violations }}</td>
            <td>
              {% if 'EXCPT' in v.fine_ref %}
                <span class="badge badge-excpt">Exception</span>
              {% elif v.session_violations >= 3 %}
                <span class="badge badge-fine">Fine</span>
              {% else %}
                <span class="badge badge-warn">Warning</span>
              {% endif %}
            </td>
            <td>
              {% if v.image_b64 %}
                <img class="thumb" src="data:image/jpeg;base64,{{ v.image_b64 }}" onclick="openModal(this.src)" alt="evidence">
              {% else %}
                <div class="no-img">No Image</div>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <div class="empty-state">No violations recorded for {{ plate }}</div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
</main>

<div id="modal" onclick="closeModal()">
  <span id="modal-close" onclick="closeModal()">&times;</span>
  <img id="modal-img" src="" alt="evidence full">
</div>

<footer>
  <span>NTSA Traffic Monitoring System</span>
  <span>&bull;</span>
  <span>AI + IR Sensor Enforcement</span>
  <span>&bull;</span>
  <span>&copy; {{ year }} National Transport and Safety Authority</span>
  <span>&bull;</span>
  <span>Keeping Kenyan Roads Safe</span>
</footer>

<script>
function tick() {
  const n = new Date();
  document.getElementById('clock').textContent =
    n.getHours().toString().padStart(2,'0') + ':' +
    n.getMinutes().toString().padStart(2,'0') + ':' +
    n.getSeconds().toString().padStart(2,'0');
}
tick(); setInterval(tick, 1000);

const map = L.map('map', { zoomControl: true, attributionControl: false }).setView([-1.286389, 36.817223], 12);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { subdomains: 'abcd', maxZoom: 19 }).addTo(map);
const redDot = L.divIcon({ className: '', html: `<div style="width:13px;height:13px;background:#c8102e;border:2px solid #fff;border-radius:50%;box-shadow:0 1px 6px rgba(200,16,46,0.5);"></div>`, iconSize: [13,13], iconAnchor: [6,6] });
const ambDot = L.divIcon({ className: '', html: `<div style="width:10px;height:10px;background:#d4870a;border:2px solid #fff;border-radius:50%;"></div>`, iconSize: [10,10], iconAnchor: [5,5] });
[
  { lat:-1.2921, lng:36.8219, icon:redDot, html:"<strong>KAA123B</strong><br>Fine &mdash; Yellow Line<br><span style='color:#8a96a8'>09:47:10</span>" },
  { lat:-1.3031, lng:36.8100, icon:ambDot, html:"<strong>KBQ987D</strong><br>Warning<br><span style='color:#8a96a8'>11:02:55</span>" },
].forEach(p => L.marker([p.lat, p.lng], { icon: p.icon }).addTo(map).bindPopup(p.html));
L.circle([-1.286389, 36.817223], { radius: 1800, color: '#c8102e', weight: 1, fill: true, fillColor: '#c8102e', fillOpacity: 0.04, dashArray: '5 8' }).addTo(map).bindPopup("Nairobi Monitoring Zone");

new Chart(document.getElementById('barChart').getContext('2d'), {
  type: 'bar',
  data: {
    labels: {{ chart_labels | tojson }},
    datasets: [
      { label: 'Fines', data: {{ chart_fines | tojson }}, backgroundColor: 'rgba(200,16,46,0.8)', borderColor: '#c8102e', borderWidth: 1, borderRadius: 2 },
      { label: 'Warnings', data: {{ chart_warnings | tojson }}, backgroundColor: 'rgba(179,107,0,0.75)', borderColor: '#b36b00', borderWidth: 1, borderRadius: 2 }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#8a96a8', font: { family: 'DM Mono', size: 11 }, boxWidth: 10, boxHeight: 10 } } },
    scales: {
      x: { ticks: { color: '#8a96a8', font: { family: 'DM Mono', size: 11 } }, grid: { color: '#f0f2f5' } },
      y: { ticks: { color: '#8a96a8', font: { family: 'DM Mono', size: 11 }, stepSize: 1 }, grid: { color: '#f0f2f5' }, beginAtZero: true }
    }
  }
});

new Chart(document.getElementById('doughnutChart').getContext('2d'), {
  type: 'doughnut',
  data: {
    labels: ['Yellow Line Fines', 'Yellow Line Warnings', 'Reckless Lane Hopping', 'Exceptions'],
    datasets: [{
      data: [{{ total_fines }}, {{ total_warnings }}, 0, 0],
      backgroundColor: ['rgba(200,16,46,0.85)','rgba(179,107,0,0.85)','rgba(26,110,181,0.85)','rgba(26,122,60,0.85)'],
      borderColor: ['#c8102e','#b36b00','#1a6eb5','#1a7a3c'],
      borderWidth: 1, hoverOffset: 5,
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: true, cutout: '58%',
    plugins: { legend: { position: 'bottom', labels: { color: '#8a96a8', font: { family: 'DM Mono', size: 10 }, boxWidth: 10, boxHeight: 10, padding: 14 } } }
  }
});

function showTab(plate, el) {
  document.querySelectorAll('.tab-content').forEach(d => d.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
  const tab = document.getElementById('tab-' + plate);
  if (tab) tab.style.display = 'block';
  el.classList.add('active');
  localStorage.setItem('ntsa_tab', plate);
}
window.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('ntsa_tab');
  if (saved) document.querySelectorAll('.tab-btn').forEach(btn => { if (btn.textContent.trim() === saved) showTab(saved, btn); });
});

function openModal(src) { document.getElementById('modal-img').src = src; document.getElementById('modal').classList.add('open'); }
function closeModal() { document.getElementById('modal').classList.remove('open'); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
</script>
</body>
</html>
"""

# ============================================================
# DASHBOARD ROUTE
# ============================================================
@app.route("/")
def dashboard():
    with store_lock:
        all_v = dict(violations)

    plates         = list(all_v.keys())
    chart_fines    = []
    chart_warnings = []
    total_fines    = 0
    total_warnings = 0
    nairobi_v      = 0

    for plate in plates:
        fines  = sum(1 for v in all_v[plate] if v["session_violations"] >= 3 and "EXCPT" not in v.get("fine_ref",""))
        warns  = sum(1 for v in all_v[plate] if v["session_violations"] < 3)
        chart_fines.append(fines)
        chart_warnings.append(warns)
        total_fines    += fines
        total_warnings += warns
        nairobi_v      += len(all_v[plate])

    nairobi_pct = min(100, nairobi_v * 20)

    return render_template_string(
        DASHBOARD_HTML,
        all_violations = all_v,
        plates         = plates,
        chart_labels   = plates,
        chart_fines    = chart_fines,
        chart_warnings = chart_warnings,
        total_fines    = total_fines,
        total_warnings = total_warnings,
        total_vehicles = len(plates),
        last_updated   = datetime.datetime.now().strftime("%H:%M:%S"),
        nairobi_v      = nairobi_v,
        nairobi_pct    = nairobi_pct,
        year           = datetime.date.today().year,
    )

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

def _keep_alive():
    import requests as req
    import time as t
    while True:
        t.sleep(840)
        try:
            req.get("https://ntsa-server.onrender.com/health", timeout=10)
            print("[KEEPALIVE] pinged")
        except Exception as e:
            print(f"[KEEPALIVE] Failed: {e}")

threading.Thread(target=_keep_alive, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
