from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from groq import Groq
import json, os, hashlib, re
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'reco-ai-secret-key-change-in-prod')
CORS(app)

DATA_DIR = 'data'
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
os.makedirs(DATA_DIR, exist_ok=True)

GROQ_MODELS = [
    'llama-3.3-70b-versatile',
    'llama-3.1-70b-versatile',
    'llama-3.1-8b-instant',
    'mixtral-8x7b-32768',
    'gemma2-9b-it',
]

def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

DEFAULT_CONFIG = {
    'groq_api_key': os.environ.get('GROQ_API_KEY', ''),
    'model': 'llama-3.3-70b-versatile',
    'max_results': 4,
    'temperature': 0.7,
    'system_prompt': 'You are an expert AI recommendation engine. Generate highly personalized, specific, and creative recommendations based on user interests and mood. Be concise but compelling.',
    'categories': [
        'Technology', 'Books & Literature', 'Music', 'Fitness & Health',
        'Travel', 'Film & Cinema', 'Cooking & Food', 'Philosophy',
        'Business & Finance', 'Art & Design', 'Gaming', 'Science'
    ],
    'moods': ['Relaxed', 'Motivated', 'Curious', 'Creative', 'Social', 'Reflective'],
    'admin_username': 'admin',
    'admin_password_hash': hash_pw('admin123'),
    'total_requests': 0,
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

def require_admin(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapped

# ── Page Routes ───────────────────────────────────────────────────

@app.route('/')
def index():
    cfg = load_config()
    return render_template('index.html', categories=cfg['categories'], moods=cfg['moods'])

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    error = None
    if request.method == 'POST':
        cfg = load_config()
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        if u == cfg['admin_username'] and hash_pw(p) == cfg['admin_password_hash']:
            session['admin_logged_in'] = True
            session['admin_user'] = u
            return redirect(url_for('admin_dashboard'))
        error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@app.route('/admin')
@app.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    cfg = load_config()
    key = cfg.get('groq_api_key', '')
    return render_template('admin.html',
        cfg=cfg,
        models=GROQ_MODELS,
        key_set=bool(key),
        key_preview=f"{key[:12]}...{key[-4:]}" if len(key) > 16 else ('(set)' if key else ''),
        admin_user=session.get('admin_user', 'admin'),
    )

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ── API Routes ────────────────────────────────────────────────────

@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    data = request.get_json() or {}
    interests = data.get('interests', [])
    mood = data.get('mood', '')

    cfg = load_config()
    api_key = cfg.get('groq_api_key', '')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured. Ask your admin to set it up.'}), 400

    count = max(2, min(8, int(cfg.get('max_results', 4))))

    prompt = f"""Generate exactly {count} personalized recommendations.

User Interests: {', '.join(interests) if interests else 'General/Open'}
User Mood: {mood if mood else 'Not specified'}

IMPORTANT: Return ONLY a valid JSON array. No explanation, no markdown, just the array.
Each item must have exactly these fields:
{{
  "category": "Book" | "Movie" | "Course" | "Podcast" | "Tool" | "Article" | "Video" | "Music",
  "title": "specific title here",
  "description": "1-2 sentences: what it is and why it fits this user",
  "tags": ["tag1", "tag2"],
  "matchScore": 78-99
}}"""

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=cfg.get('model', 'llama-3.3-70b-versatile'),
            messages=[
                {'role': 'system', 'content': cfg.get('system_prompt', '')},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=1500,
            temperature=float(cfg.get('temperature', 0.7)),
        )
        text = resp.choices[0].message.content.strip()
        m = re.search(r'\[[\s\S]*\]', text)
        if not m:
            return jsonify({'error': 'AI returned an unexpected format. Try again.'}), 500
        recs = json.loads(m.group())

        # Track requests
        cfg['total_requests'] = int(cfg.get('total_requests', 0)) + 1
        save_config(cfg)

        return jsonify({'recommendations': recs, 'model': cfg.get('model')})
    except json.JSONDecodeError:
        return jsonify({'error': 'Could not parse AI response. Try again.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/config', methods=['POST'])
@require_admin
def update_config():
    data = request.get_json() or {}
    cfg = load_config()
    allowed = ['groq_api_key', 'model', 'max_results', 'temperature', 'system_prompt', 'categories', 'moods']
    for k in allowed:
        if k in data:
            cfg[k] = data[k]
    save_config(cfg)
    return jsonify({'success': True, 'message': 'Configuration saved.'})

@app.route('/api/admin/change-password', methods=['POST'])
@require_admin
def change_password():
    data = request.get_json() or {}
    cfg = load_config()
    current = data.get('current_password', '')
    new_u = data.get('new_username', '').strip()
    new_p = data.get('new_password', '')
    if hash_pw(current) != cfg['admin_password_hash']:
        return jsonify({'error': 'Current password is incorrect.'}), 400
    if not new_u:
        return jsonify({'error': 'Username cannot be empty.'}), 400
    if len(new_p) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400
    cfg['admin_username'] = new_u
    cfg['admin_password_hash'] = hash_pw(new_p)
    save_config(cfg)
    session.clear()
    return jsonify({'success': True, 'message': 'Credentials updated. Please log in again.'})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
