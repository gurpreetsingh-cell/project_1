from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
from datetime import datetime

app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'escalation-hub-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins="*")

# Data file paths
DATA_FILE = 'data.json'
USERS_FILE = 'users.json'
ACTIVITY_FILE = 'activity.json'

# Helper functions to load/save JSON files
def load_json(filename):
    """Load data from JSON file"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return [] if filename != USERS_FILE else get_default_users()
    return [] if filename != USERS_FILE else get_default_users()

def save_json(filename, data):
    """Save data to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False

def get_default_users():
    """Return default users if none exist"""
    return [
        {'id': 'u1', 'name': 'Admin', 'username': 'admin', 'password': 'admin123', 'role': 'admin'},
        {'id': 'u2', 'name': 'User', 'username': 'user', 'password': 'user123', 'role': 'user'}
    ]

# ═══════════════ ROUTES ═══════════════

@app.route('/')
def index():
    return render_template('escalation-matrix-hub.html')

# Auth endpoints
@app.route('/api/login', methods=['POST'])
def login():
    """Login user"""
    credentials = request.json
    username = credentials.get('username', '').strip()
    password = credentials.get('password', '')
    
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['username'] == username and u['password'] == password), None)
    
    if not user:
        return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401
    
    return jsonify({'status': 'success', 'user': user})

# Escalation API endpoints
@app.route('/api/escalations', methods=['GET'])
def get_escalations():
    """Fetch all escalations"""
    data = load_json(DATA_FILE)
    return jsonify(data)

@app.route('/api/escalations', methods=['POST'])
def create_escalation():
    """Create new escalation"""
    escalation = request.json
    data = load_json(DATA_FILE)
    data.insert(0, escalation)  # Add to beginning like original
    save_json(DATA_FILE, data)
    
    # Notify all connected clients
    socketio.emit('escalation_added', escalation, broadcast=True)
    return jsonify({'status': 'success', 'data': escalation}), 201

@app.route('/api/escalations/<esc_id>', methods=['PUT'])
def update_escalation(esc_id):
    """Update escalation"""
    update_data = request.json
    data = load_json(DATA_FILE)
    
    for i, esc in enumerate(data):
        if esc['id'] == esc_id:
            data[i].update(update_data)
            save_json(DATA_FILE, data)
            
            # Notify all connected clients
            socketio.emit('escalation_updated', data[i], broadcast=True)
            return jsonify({'status': 'success', 'data': data[i]})
    
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.route('/api/escalations/<esc_id>', methods=['DELETE'])
def delete_escalation(esc_id):
    """Delete escalation"""
    data = load_json(DATA_FILE)
    data = [e for e in data if e['id'] != esc_id]
    save_json(DATA_FILE, data)
    
    # Notify all connected clients
    socketio.emit('escalation_deleted', {'id': esc_id}, broadcast=True)
    return jsonify({'status': 'success'})

@app.route('/api/users', methods=['GET'])
def get_users():
    """Fetch all users"""
    users = load_json(USERS_FILE)
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create new user"""
    user = request.json
    users = load_json(USERS_FILE)
    
    # Check if username already exists
    if any(u['username'] == user['username'] for u in users):
        return jsonify({'status': 'error', 'message': 'Username already exists'}), 400
    
    users.append(user)
    save_json(USERS_FILE, users)
    
    socketio.emit('user_created', user, broadcast=True)
    return jsonify({'status': 'success', 'data': user}), 201

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete user"""
    if user_id == 'u1':
        return jsonify({'status': 'error', 'message': 'Cannot delete default admin user'}), 400
    
    users = load_json(USERS_FILE)
    users = [u for u in users if u['id'] != user_id]
    save_json(USERS_FILE, users)
    
    socketio.emit('user_deleted', {'id': user_id}, broadcast=True)
    return jsonify({'status': 'success'})

# Activity API endpoints
@app.route('/api/activity', methods=['GET'])
def get_activity():
    """Fetch activity log"""
    activity = load_json(ACTIVITY_FILE)
    return jsonify(activity)

@app.route('/api/activity', methods=['POST'])
def log_activity():
    """Log activity"""
    entry = request.json
    activity = load_json(ACTIVITY_FILE)
    activity.insert(0, entry)
    if len(activity) > 500:
        activity = activity[:500]
    save_json(ACTIVITY_FILE, activity)
    
    socketio.emit('activity_logged', entry, broadcast=True)
    return jsonify({'status': 'success'}), 201

# ═══════════════ WEBSOCKET EVENTS ═══════════════

@socketio.on('connect')
def handle_connect():
    """Client connected"""
    print(f"Client connected: {request.sid}")
    emit('connect_response', {'data': 'Connected to sync server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    print(f"Client disconnected: {request.sid}")

@socketio.on('request_sync')
def handle_sync_request():
    """Send full data to requesting client"""
    data = {
        'escalations': load_json(DATA_FILE),
        'users': load_json(USERS_FILE),
        'activity': load_json(ACTIVITY_FILE)
    }
    emit('sync_data', data)

if __name__ == '__main__':
    # use host 0.0.0.0 so the server listens on all interfaces
    socketio.run(app)