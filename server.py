"""
NTSA Lane Violation Cloud Server
==================================
- Receives violation reports from the Pi via POST /api/violation
- Serves a live NTSA dashboard at /
- Sends email to the driver on every fine (violation >= 3)
- Pre-seeded with dummy vehicle KAA123B for demo purposes
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

# ─────────────────────────────────────────────────────────────────
# CONFIGURATION  –  set these as environment variables on Render
# ─────────────────────────────────────────────────────────────────
GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS",      "your_email@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "xxxx xxxx xxxx xxxx")

# ─────────────────────────────────────────────────────────────────
# IN-MEMORY VIOLATION STORE
# violations = { "KBQ987D": [ {...}, {...} ], "KAA123B": [ {...} ] }
# ─────────────────────────────────────────────────────────────────
store_lock = threading.Lock()
violations = {}

def _seed_dummy():
    """Pre-seed dummy vehicle KAA123B with realistic violations."""
    dummy_plate = "KAA123B"
    dummy_email = "dummy.driver@example.com"
    base_date   = datetime.date.today().strftime("%Y-%m-%d")
    dummy_data  = [
        {
            "fine_ref":           f"NTSA-{base_date}-KAA123B-0001",
            "vehicle_plate":      dummy_plate,
            "driver_email":       dummy_email,
            "date":               base_date,
            "time":               "08:14:32",
            "session_violations": 3,
            "total_violations":   3,
            "offence":            "Illegal crossing of yellow continuous centre line",
            "image_b64":          "",
        },
        {
            "fine_ref":           f"NTSA-{base_date}-KAA123B-0002",
            "vehicle_plate":      dummy_plate,
            "driver_email":       dummy_email,
            "date":               base_date,
            "time":               "09:47:10",
            "session_violations": 4,
            "total_violations":   4,
            "offence":            "Illegal crossing of yellow continuous centre line",
            "image_b64":          "",
        },
        {
            "fine_ref":           f"WARN-{base_date}-KAA123B-0003",
            "vehicle_plate":      dummy_plate,
            "driver_email":       dummy_email,
            "date":               base_date,
            "time":               "11:02:55",
            "session_violations": 1,
            "total_violations":   5,
            "offence":            "Illegal crossing of yellow continuous centre line",
            "image_b64":          "",
        },
    ]
    violations[dummy_plate] = dummy_data

_seed_dummy()


# ─────────────────────────────────────────────────────────────────
# EMAIL HELPER
# ─────────────────────────────────────────────────────────────────
def send_driver_email(violation):
    """Send violation notice to the driver. Runs in a background thread."""
    try:
        fine_ref    = violation["fine_ref"]
        plate       = violation["vehicle_plate"]
        driver_email = violation["driver_email"]
        date_s      = violation["date"]
        time_s      = violation["time"]
        total_v     = violation["total_violations"]
        image_b64   = violation.get("image_b64", "")

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

Photographic evidence of the violation is attached to this email.

Please ensure compliance with all road markings and traffic regulations.
Repeated violations may result in licence suspension.

NTSA Traffic Monitoring Division
"""

        msg = MIMEMultipart()
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = driver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Attach snapshot if available
        if image_b64:
            img_bytes = base64.b64decode(image_b64)
            img_part  = MIMEImage(img_bytes, name=f"evidence_{fine_ref}.jpg")
            msg.attach(img_part)

        with smtplib.SMTP("smtp.gmail.com", 587) as srv:
            srv.starttls()
            srv.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            srv.sendmail(GMAIL_ADDRESS, driver_email, msg.as_string())

        print(f"[EMAIL] Sent to {driver_email} for {fine_ref}")

    except Exception as e:
        print(f"[EMAIL] Failed: {e}")


# ─────────────────────────────────────────────────────────────────
# API ENDPOINT  –  Pi posts here on every fine (session_violations >= 3)
# ─────────────────────────────────────────────────────────────────
@app.route("/api/violation", methods=["POST"])
def receive_violation():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no data"}), 400

    plate = data.get("vehicle_plate", "UNKNOWN").upper().replace(" ", "")

    with store_lock:
        if plate not in violations:
            violations[plate] = []
        violations[plate].append(data)

    print(f"[SERVER] Violation received: {data.get('fine_ref')} – {plate}")

    # Send driver email in background
    threading.Thread(target=send_driver_email, args=(data,), daemon=True).start()

    return jsonify({"status": "ok"}), 200


# ─────────────────────────────────────────────────────────────────
# DASHBOARD  –  auto-refreshes every 5 seconds
# ─────────────────────────────────────────────────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="5">
  <title>NTSA Live Violation Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Segoe UI', Arial, sans-serif;
      background: #0d1117;
      color: #e6edf3;
      min-height: 100vh;
    }

    /* ── Header ── */
    header {
      background: linear-gradient(135deg, #1a3a5c 0%, #0d2137 100%);
      border-bottom: 2px solid #1f6feb;
      padding: 18px 32px;
      display: flex;
      align-items: center;
      gap: 18px;
    }
    header img {
      height: 48px;
      filter: brightness(0) invert(1);
    }
    header .titles h1 {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 1px;
      color: #58a6ff;
    }
    header .titles p {
      font-size: 12px;
      color: #8b949e;
      margin-top: 2px;
    }
    .live-badge {
      margin-left: auto;
      background: #238636;
      color: #fff;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 20px;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.6; }
    }

    /* ── Layout ── */
    main { padding: 28px 32px; max-width: 1400px; margin: 0 auto; }

    /* ── Stat cards ── */
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }
    .stat-card {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 10px;
      padding: 20px;
      text-align: center;
    }
    .stat-card .value {
      font-size: 36px;
      font-weight: 700;
      color: #58a6ff;
    }
    .stat-card .label {
      font-size: 12px;
      color: #8b949e;
      margin-top: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .stat-card.danger .value { color: #f85149; }
    .stat-card.warn   .value { color: #e3b341; }
    .stat-card.ok     .value { color: #3fb950; }

    /* ── Grid: chart + map ── */
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 28px;
    }
    @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }

    .card {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 10px;
      padding: 20px;
    }
    .card h2 {
      font-size: 14px;
      font-weight: 600;
      color: #8b949e;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin-bottom: 16px;
      border-bottom: 1px solid #30363d;
      padding-bottom: 10px;
    }

    /* ── Map placeholder ── */
    #map-placeholder {
      background: #0d2137;
      border-radius: 8px;
      height: 260px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 10px;
      color: #8b949e;
      font-size: 13px;
      border: 1px dashed #30363d;
    }
    #map-placeholder svg { opacity: 0.4; }

    /* ── Vehicle tabs ── */
    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    .tab {
      padding: 7px 18px;
      border-radius: 6px;
      border: 1px solid #30363d;
      background: #0d1117;
      color: #8b949e;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.2s;
    }
    .tab.active, .tab:hover {
      background: #1f6feb;
      border-color: #1f6feb;
      color: #fff;
    }

    /* ── Violation table ── */
    .table-wrap { overflow-x: auto; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    thead th {
      background: #1c2128;
      color: #8b949e;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid #30363d;
    }
    tbody tr {
      border-bottom: 1px solid #21262d;
      transition: background 0.15s;
    }
    tbody tr:hover { background: #1c2128; }
    tbody td { padding: 10px 14px; color: #c9d1d9; vertical-align: middle; }

    .badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-fine    { background: #3d1a1a; color: #f85149; border: 1px solid #f85149; }
    .badge-warning { background: #2d2008; color: #e3b341; border: 1px solid #e3b341; }

    .thumb {
      width: 72px;
      height: 48px;
      object-fit: cover;
      border-radius: 4px;
      border: 1px solid #30363d;
      cursor: pointer;
    }
    .no-img {
      width: 72px;
      height: 48px;
      background: #21262d;
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      color: #484f58;
    }

    /* ── Image modal ── */
    #modal {
      display: none;
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.85);
      z-index: 1000;
      align-items: center;
      justify-content: center;
    }
    #modal.open { display: flex; }
    #modal img {
      max-width: 90vw;
      max-height: 85vh;
      border-radius: 8px;
      border: 2px solid #30363d;
    }
    #modal-close {
      position: fixed; top: 20px; right: 28px;
      font-size: 32px; color: #fff; cursor: pointer;
    }

    footer {
      text-align: center;
      padding: 20px;
      color: #484f58;
      font-size: 12px;
      border-top: 1px solid #21262d;
      margin-top: 20px;
    }
  </style>
</head>
<body>

<header>
  <div class="titles">
    <h1>&#9678; NTSA TRAFFIC VIOLATION MONITORING SYSTEM</h1>
    <p>National Transport and Safety Authority &nbsp;|&nbsp; Real-Time Dashboard</p>
  </div>
  <span class="live-badge">&#9679; LIVE</span>
</header>

<main>

  <!-- Stat cards -->
  <div class="stats">
    <div class="stat-card danger">
      <div class="value">{{ total_fines }}</div>
      <div class="label">Total Fines Issued</div>
    </div>
    <div class="stat-card warn">
      <div class="value">{{ total_warnings }}</div>
      <div class="label">Warnings Issued</div>
    </div>
    <div class="stat-card">
      <div class="value">{{ total_vehicles }}</div>
      <div class="label">Vehicles Monitored</div>
    </div>
    <div class="stat-card ok">
      <div class="value">{{ last_updated }}</div>
      <div class="label">Last Updated</div>
    </div>
  </div>

  <!-- Chart + Map -->
  <div class="grid-2">
    <div class="card">
      <h2>Violations per Vehicle</h2>
      <canvas id="barChart" height="220"></canvas>
    </div>
    <div class="card">
      <h2>Incident Location (GPS not yet integrated)</h2>
      <div id="map-placeholder">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none"
             stroke="#58a6ff" stroke-width="1.5">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75
                   7-13c0-3.87-3.13-7-7-7z"/>
          <circle cx="12" cy="9" r="2.5"/>
        </svg>
        <span>GPS integration pending</span>
        <span style="font-size:11px">Location data will appear here once GPS module is connected</span>
      </div>
    </div>
  </div>

  <!-- Violation table with vehicle tabs -->
  <div class="card">
    <h2>Violation Log</h2>
    <div class="tabs" id="tabs">
      {% for plate in plates %}
      <div class="tab {% if loop.first %}active{% endif %}"
           onclick="showTab('{{ plate }}', this)">{{ plate }}</div>
      {% endfor %}
    </div>
    {% for plate, v_list in all_violations.items() %}
    <div class="table-wrap tab-content" id="tab-{{ plate }}"
         style="{% if not loop.first %}display:none{% endif %}">
      {% if v_list %}
      <table>
        <thead>
          <tr>
            <th>Fine Reference</th>
            <th>Date</th>
            <th>Time</th>
            <th>Offence</th>
            <th>Session #</th>
            <th>Total</th>
            <th>Type</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {% for v in v_list | reverse %}
          <tr>
            <td style="font-family:monospace;font-size:12px">{{ v.fine_ref }}</td>
            <td>{{ v.date }}</td>
            <td>{{ v.time }}</td>
            <td style="max-width:220px;white-space:normal">{{ v.offence }}</td>
            <td style="text-align:center">{{ v.session_violations }}</td>
            <td style="text-align:center">{{ v.total_violations }}</td>
            <td>
              {% if v.session_violations >= 3 %}
              <span class="badge badge-fine">FINE</span>
              {% else %}
              <span class="badge badge-warning">WARNING</span>
              {% endif %}
            </td>
            <td>
              {% if v.image_b64 %}
              <img class="thumb"
                   src="data:image/jpeg;base64,{{ v.image_b64 }}"
                   onclick="openModal(this.src)" alt="evidence">
              {% else %}
              <div class="no-img">No img</div>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}
      <p style="color:#484f58;padding:20px;text-align:center">
        No violations recorded yet for {{ plate }}
      </p>
      {% endif %}
    </div>
    {% endfor %}
  </div>

</main>

<!-- Image modal -->
<div id="modal" onclick="closeModal()">
  <span id="modal-close" onclick="closeModal()">&times;</span>
  <img id="modal-img" src="" alt="Evidence">
</div>

<footer>
  NTSA Traffic Monitoring System &nbsp;|&nbsp;
  Auto-refreshes every 5 seconds &nbsp;|&nbsp;
  &copy; {{ year }} National Transport and Safety Authority
</footer>

<script>
  // ── Bar chart ──────────────────────────────────────────────────
  const ctx = document.getElementById('barChart').getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: {{ chart_labels | tojson }},
      datasets: [
        {
          label: 'Fines',
          data: {{ chart_fines | tojson }},
          backgroundColor: 'rgba(248, 81, 73, 0.7)',
          borderColor: '#f85149',
          borderWidth: 1,
          borderRadius: 4,
        },
        {
          label: 'Warnings',
          data: {{ chart_warnings | tojson }},
          backgroundColor: 'rgba(227, 179, 65, 0.7)',
          borderColor: '#e3b341',
          borderWidth: 1,
          borderRadius: 4,
        }
      ]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: '#8b949e', font: { size: 12 } } }
      },
      scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
        y: {
          ticks: { color: '#8b949e', stepSize: 1 },
          grid: { color: '#21262d' },
          beginAtZero: true,
        }
      }
    }
  });

  // ── Tab switching ──────────────────────────────────────────────
  function showTab(plate, el) {
    document.querySelectorAll('.tab-content').forEach(d => d.style.display = 'none');
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + plate).style.display = 'block';
    el.classList.add('active');
  }

  // ── Image modal ────────────────────────────────────────────────
  function openModal(src) {
    document.getElementById('modal-img').src = src;
    document.getElementById('modal').classList.add('open');
  }
  function closeModal() {
    document.getElementById('modal').classList.remove('open');
  }
</script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    with store_lock:
        all_v = dict(violations)

    # Build chart data
    plates        = list(all_v.keys())
    chart_fines   = []
    chart_warnings = []
    total_fines   = 0
    total_warnings = 0

    for plate in plates:
        fines    = sum(1 for v in all_v[plate] if v["session_violations"] >= 3)
        warnings = sum(1 for v in all_v[plate] if v["session_violations"] < 3)
        chart_fines.append(fines)
        chart_warnings.append(warnings)
        total_fines    += fines
        total_warnings += warnings

    return render_template_string(
        DASHBOARD_HTML,
        all_violations  = all_v,
        plates          = plates,
        chart_labels    = plates,
        chart_fines     = chart_fines,
        chart_warnings  = chart_warnings,
        total_fines     = total_fines,
        total_warnings  = total_warnings,
        total_vehicles  = len(plates),
        last_updated    = datetime.datetime.now().strftime("%H:%M:%S"),
        year            = datetime.date.today().year,
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
