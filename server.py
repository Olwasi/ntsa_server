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
      background: linear-gradient(135deg, #0a0e1a 0%, #0f1622 100%);
      color: #ffffff;
      min-height: 100vh;
    }

    /* Professional Header with Road Theme */
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

    /* Stats Cards - Colorful */
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

    /* Layout */
    main { padding: 30px 40px; max-width: 1600px; margin: 0 auto; }

    /* Cards */
    .card {
      background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 20px;
      padding: 24px;
      backdrop-filter: blur(10px);
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

    /* Map Placeholder */
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

    /* Tabs */
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

    /* Table Styles */
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

    /* Modal */
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
  <div class="logo">
    <span>🚦</span>
  </div>
  <div class="titles">
    <h1>NTSA TRAFFIC VIOLATION MONITORING SYSTEM</h1>
    <p>National Transport and Safety Authority | Real-Time Enforcement Dashboard</p>
  </div>
  <span class="live-badge">
    <span>🟢</span> LIVE MONITORING
  </span>
</header>

<main>

  <div class="stats">
    <div class="stat-card danger">
      <div class="value">{{ total_fines }}</div>
      <div class="label">🚨 FINES ISSUED</div>
    </div>
    <div class="stat-card warn">
      <div class="value">{{ total_warnings }}</div>
      <div class="label">⚠️ WARNINGS</div>
    </div>
    <div class="stat-card info">
      <div class="value">{{ total_vehicles }}</div>
      <div class="label">🚗 VEHICLES MONITORED</div>
    </div>
    <div class="stat-card success">
      <div class="value">{{ last_updated }}</div>
      <div class="label">🕐 LAST UPDATED</div>
    </div>
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
          <tr><th>🔖 Fine Reference</th><th>📅 Date</th><th>⏰ Time</th><th>📝 Offence</th><th>🎯 Session</th><th>📈 Total</th><th>🏷️ Type</th><th>📸 Evidence</th><tr>
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
        {
          label: '🔴 Fines',
          data: {{ chart_fines | tojson }},
          backgroundColor: 'rgba(255, 65, 108, 0.8)',
          borderColor: '#ff416c',
          borderWidth: 2,
          borderRadius: 8,
          barPercentage: 0.6
        },
        {
          label: '🟠 Warnings',
          data: {{ chart_warnings | tojson }},
          backgroundColor: 'rgba(247, 183, 51, 0.8)',
          borderColor: '#f7b733',
          borderWidth: 2,
          borderRadius: 8,
          barPercentage: 0.6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { labels: { color: '#e0e6f0', font: { size: 12, weight: 'bold' } } }
      },
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
