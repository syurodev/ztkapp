#!/usr/bin/env python3
"""
Simple web interface to view SQLite database
Run: python3 db_web_viewer.py
Then open: http://localhost:8080
"""

from flask import Flask, render_template_string, jsonify, request
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('zkteco_app.db')
    conn.row_factory = sqlite3.Row
    return conn

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ZKTeco Database Viewer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        h2 { color: #666; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; font-weight: bold; }
        tr:hover { background-color: #f5f5f5; }
        .status-active { color: #28a745; font-weight: bold; }
        .status-inactive { color: #dc3545; font-weight: bold; }
        .btn { padding: 8px 16px; margin: 5px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; border: none; cursor: pointer; }
        .btn:hover { background: #0056b3; }
        .stats { display: flex; justify-content: space-around; }
        .stat-card { text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; }
        .stat-number { font-size: 2em; font-weight: bold; }
        .query-box { width: 100%; height: 100px; font-family: monospace; }
        .json-data { background: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 ZKTeco Database Viewer</h1>
        
        <!-- Statistics -->
        <div class="card">
            <h2>📊 Database Statistics</h2>
            <div class="stats" id="stats">
                Loading...
            </div>
        </div>
        
        <!-- Devices -->
        <div class="card">
            <h2>📱 Devices</h2>
            <div id="devices">Loading...</div>
        </div>
        
        <!-- Users -->
        <div class="card">
            <h2>👥 Users</h2>
            <div id="users">Loading...</div>
        </div>
        
        <!-- Settings -->
        <div class="card">
            <h2>⚙️ App Settings</h2>
            <div id="settings">Loading...</div>
        </div>
        
        <!-- Recent Logs -->
        <div class="card">
            <h2>📋 Recent Attendance Logs</h2>
            <div id="logs">Loading...</div>
        </div>
        
        <!-- Custom Query -->
        <div class="card">
            <h2>🔍 Custom Query</h2>
            <textarea class="query-box" id="queryBox" placeholder="SELECT * FROM devices;"></textarea><br>
            <button class="btn" onclick="executeQuery()">Execute Query</button>
            <div id="queryResult"></div>
        </div>
    </div>

    <script>
        // Load data when page loads
        window.onload = function() {
            loadStats();
            loadDevices();
            loadUsers();
            loadSettings();
            loadLogs();
        };
        
        function loadStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('stats').innerHTML = `
                        <div class="stat-card">
                            <div class="stat-number">${data.devices}</div>
                            <div>Devices</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.users}</div>
                            <div>Users</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.logs}</div>
                            <div>Logs</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.settings}</div>
                            <div>Settings</div>
                        </div>
                    `;
                });
        }
        
        function loadDevices() {
            fetch('/api/devices')
                .then(response => response.json())
                .then(data => {
                    let html = '<table><tr><th>Name</th><th>IP:Port</th><th>Status</th><th>Device Info</th></tr>';
                    data.forEach(device => {
                        const status = device.is_active ? '<span class="status-active">🟢 Active</span>' : '<span class="status-inactive">🔴 Inactive</span>';
                        const deviceInfo = device.device_info ? `<div class="json-data">${JSON.stringify(device.device_info, null, 2)}</div>` : 'N/A';
                        html += `<tr>
                            <td>${device.name}</td>
                            <td>${device.ip}:${device.port}</td>
                            <td>${status}</td>
                            <td>${deviceInfo}</td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('devices').innerHTML = html;
                });
        }
        
        function loadUsers() {
            fetch('/api/users')
                .then(response => response.json())
                .then(data => {
                    if (data.length === 0) {
                        document.getElementById('users').innerHTML = '<p>No users found.</p>';
                        return;
                    }
                    let html = '<table><tr><th>User ID</th><th>Name</th><th>Device</th><th>Sync Status</th></tr>';
                    data.forEach(user => {
                        const syncStatus = user.is_synced ? '✅ Synced' : '⏳ Not synced';
                        html += `<tr>
                            <td>${user.user_id}</td>
                            <td>${user.name}</td>
                            <td>${user.device_id || 'N/A'}</td>
                            <td>${syncStatus}</td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('users').innerHTML = html;
                });
        }
        
        function loadSettings() {
            fetch('/api/settings')
                .then(response => response.json())
                .then(data => {
                    let html = '<table><tr><th>Key</th><th>Value</th><th>Description</th></tr>';
                    data.forEach(setting => {
                        html += `<tr>
                            <td><strong>${setting.key}</strong></td>
                            <td>${setting.value}</td>
                            <td>${setting.description || 'N/A'}</td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('settings').innerHTML = html;
                });
        }
        
        function loadLogs() {
            fetch('/api/logs')
                .then(response => response.json())
                .then(data => {
                    if (data.length === 0) {
                        document.getElementById('logs').innerHTML = '<p>No attendance logs found.</p>';
                        return;
                    }
                    let html = '<table><tr><th>User ID</th><th>Device</th><th>Time</th><th>Method</th><th>Action</th></tr>';
                    data.forEach(log => {
                        const methods = {1: 'Fingerprint', 4: 'Card'};
                        const actions = {0: 'Check In', 1: 'Check Out', 2: 'OT Start', 3: 'OT End', 4: 'Unspecified'};
                        html += `<tr>
                            <td>${log.user_id}</td>
                            <td>${log.device_id || 'N/A'}</td>
                            <td>${log.timestamp}</td>
                            <td>${methods[log.method] || 'Unknown'}</td>
                            <td>${actions[log.action] || 'Unknown'}</td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('logs').innerHTML = html;
                });
        }
        
        function executeQuery() {
            const query = document.getElementById('queryBox').value;
            if (!query.trim()) return;
            
            fetch('/api/query', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({sql: query})
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('queryResult').innerHTML = `<div style="color: red;">Error: ${data.error}</div>`;
                    return;
                }
                
                if (data.length === 0) {
                    document.getElementById('queryResult').innerHTML = '<p>No results.</p>';
                    return;
                }
                
                let html = '<table><tr>';
                Object.keys(data[0]).forEach(key => {
                    html += `<th>${key}</th>`;
                });
                html += '</tr>';
                
                data.forEach(row => {
                    html += '<tr>';
                    Object.values(row).forEach(value => {
                        html += `<td>${value}</td>`;
                    });
                    html += '</tr>';
                });
                html += '</table>';
                document.getElementById('queryResult').innerHTML = html;
            });
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def api_stats():
    with get_db_connection() as conn:
        stats = {}
        stats['devices'] = conn.execute('SELECT COUNT(*) as count FROM devices').fetchone()['count']
        stats['users'] = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']  
        stats['logs'] = conn.execute('SELECT COUNT(*) as count FROM attendance_logs').fetchone()['count']
        stats['settings'] = conn.execute('SELECT COUNT(*) as count FROM app_settings').fetchone()['count']
    return jsonify(stats)

@app.route('/api/devices')
def api_devices():
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM devices ORDER BY created_at DESC')
        devices = []
        for row in cursor.fetchall():
            device = dict(row)
            if device['device_info']:
                device['device_info'] = json.loads(device['device_info'])
            devices.append(device)
    return jsonify(devices)

@app.route('/api/users')
def api_users():
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM users ORDER BY created_at DESC')
        users = [dict(row) for row in cursor.fetchall()]
    return jsonify(users)

@app.route('/api/settings')
def api_settings():
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM app_settings ORDER BY updated_at DESC')
        settings = [dict(row) for row in cursor.fetchall()]
    return jsonify(settings)

@app.route('/api/logs')
def api_logs():
    with get_db_connection() as conn:
        cursor = conn.execute('SELECT * FROM attendance_logs ORDER BY timestamp DESC LIMIT 20')
        logs = [dict(row) for row in cursor.fetchall()]
    return jsonify(logs)

@app.route('/api/query', methods=['POST'])
def api_query():
    try:
        sql = request.json.get('sql', '')
        with get_db_connection() as conn:
            cursor = conn.execute(sql)
            results = [dict(row) for row in cursor.fetchall()]
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("🚀 Starting ZKTeco Database Web Viewer...")
    print("📊 Open: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)