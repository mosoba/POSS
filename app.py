from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
import os
import traceback

app = Flask(__name__)
application = app

# ============================================================
# CONFIGURATION
# ============================================================

app.secret_key = 'pricepoint-pos-secret-key-2026'
app.permanent_session_lifetime = timedelta(days=30)
app.template_folder = 'templates'
app.static_folder = 'static'

# Create directories if they don't exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static/icons', exist_ok=True)


# ============================================================
# DATA - Hardcoded
# ============================================================

PRODUCTS = [
    {'id': '1', 'name': 'iPhone 15 Pro Max', 'price': 245000, 'stock': 15, 'category': 'Phones', 
     'image': 'https://images.unsplash.com/photo-1592286927505-1def25e4c479?w=500', 'barcode': 'IP15PM001'},
    {'id': '2', 'name': 'MacBook Pro 16"', 'price': 450000, 'stock': 8, 'category': 'Laptops', 
     'image': 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500', 'barcode': 'MBP16M3'},
    {'id': '3', 'name': 'AirPods Pro 2', 'price': 35000, 'stock': 25, 'category': 'Accessories', 
     'image': 'https://images.unsplash.com/photo-1606841838e0-bf1baf2dc3e9?w=500', 'barcode': 'APP2'},
    {'id': '4', 'name': 'Samsung Galaxy S24 Ultra', 'price': 225000, 'stock': 23, 'category': 'Phones', 
     'image': 'https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=500', 'barcode': 'SGS24U'},
    {'id': '5', 'name': 'iPad Pro 12.9"', 'price': 185000, 'stock': 12, 'category': 'Tablets', 
     'image': 'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=500', 'barcode': 'IP129'},
    {'id': '6', 'name': 'HP Spectre x360', 'price': 125000, 'stock': 18, 'category': 'Laptops', 
     'image': 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500', 'barcode': 'HPSX360'},
    {'id': '7', 'name': 'Apple Watch Series 9', 'price': 62000, 'stock': 26, 'category': 'Wearables', 
     'image': 'https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=500', 'barcode': 'AW9'},
    {'id': '8', 'name': 'USB-C Fast Cable', 'price': 1200, 'stock': 98, 'category': 'Accessories', 
     'image': 'https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500', 'barcode': 'USBCF'}
]

CUSTOMERS = [
    {'name': 'Walk-in Customer', 'email': 'walkin@example.com', 'phone': 'N/A'},
    {'name': 'John Doe', 'email': 'john@example.com', 'phone': '+254 700 000 000'},
    {'name': 'Jane Smith', 'email': 'jane@example.com', 'phone': '+254 711 111 111'}
]


def load_products():
    return PRODUCTS


def load_customers():
    return CUSTOMERS


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def home():
    if 'user' in session:
        if session['user'].get('role') == 'admin':
            return redirect('/admin')
        return redirect('/pos')
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return render_template('login.html')
        
        # Simple users
        users = {
            'admin@pricepoint.com': {'password': 'electronics2026', 'name': 'Admin User', 'role': 'admin'},
            'user@pricepoint.com': {'password': 'electronics2026', 'name': 'John Doe', 'role': 'user'},
            'pos@pricepoint.com': {'password': 'electronics2026', 'name': 'POS Operator', 'role': 'pos'},
            'manager@pricepoint.com': {'password': 'electronics2026', 'name': 'Store Manager', 'role': 'manager'}
        }
        
        if email in users and users[email]['password'] == password:
            session['user'] = {
                'email': email,
                'name': users[email]['name'],
                'role': users[email]['role'],
                'id': 'legacy_' + email
            }
            flash('Welcome, ' + users[email]['name'] + '!', 'success')
            
            if users[email]['role'] == 'admin':
                return redirect('/admin')
            return redirect('/pos')
        else:
            flash('Invalid email or password', 'danger')
            return render_template('login.html')
    
    return render_template('login.html')


@app.route('/logout')
def user_logout():
    session.pop('user', None)
    flash('Logged out successfully', 'success')
    return redirect('/login')


@app.route('/pos')
def pos_page():
    try:
        if 'user' not in session:
            return redirect('/login')
        
        products = load_products()
        customers = load_customers()
        
        return render_template('pos.html', 
                             products=products, 
                             customers=customers,
                             session=session)
    except Exception as e:
        print(f'Error: {e}')
        traceback.print_exc()
        return render_template('pos.html', products=[], customers=[], session=session)


@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['user'].get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect('/pos')
    
    return f"""
    <html>
    <head><title>Admin</title></head>
    <body style="font-family: system-ui; padding: 40px; max-width: 800px; margin: 0 auto;">
        <h1>📊 Admin Dashboard</h1>
        <p>Welcome, {session['user']['name']}!</p>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <a href="/pos" style="padding: 10px 20px; background: #059669; color: white; text-decoration: none; border-radius: 8px;">🛒 POS</a>
            <a href="/logout" style="padding: 10px 20px; background: #ef4444; color: white; text-decoration: none; border-radius: 8px;">🚪 Logout</a>
        </div>
        <hr>
        <h3>📈 Stats</h3>
        <p>Products: {len(load_products())}</p>
        <p>Customers: {len(load_customers())}</p>
    </body>
    </html>
    """


# ============================================================
# PWA ROUTES
# ============================================================

@app.route('/manifest.json')
def serve_manifest():
    try:
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')
    except Exception:
        return {"error": "manifest not found"}, 404


@app.route('/sw.js')
def serve_sw():
    try:
        response = send_from_directory('static', 'sw.js', mimetype='application/javascript')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    except Exception:
        return "Service Worker not found", 404


@app.route('/offline.html')
def serve_offline():
    try:
        return render_template('offline.html')
    except Exception:
        return "<h1>Offline</h1><p>Please connect to the internet.</p>", 503


@app.route('/static/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory('static', filename)
    except Exception:
        return "File not found", 404


@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'products': len(load_products()),
        'customers': len(load_customers())
    })


@app.route('/test')
def test():
    return jsonify({
        'status': 'ok',
        'message': 'App is running!',
        'products': len(load_products()),
        'session': session.get('user', {}).get('email', 'None')
    })


# ============================================================
# TEMPLATE FALLBACK - Create login.html if missing
# ============================================================

@app.route('/create-templates')
def create_templates():
    """Emergency: Create missing templates"""
    try:
        # Create login.html
        with open('templates/login.html', 'w') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Login - PricePoint POS</title>
    <style>
        body { font-family: system-ui; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #0f172a; margin: 0; }
        .card { background: white; padding: 40px; border-radius: 16px; width: 100%; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        h1 { font-size: 1.5rem; color: #0f172a; text-align: center; }
        .form-group { margin-bottom: 16px; }
        label { display: block; font-size: 0.8rem; font-weight: 600; color: #475569; margin-bottom: 4px; }
        input { width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; }
        input:focus { outline: none; border-color: #059669; }
        button { width: 100%; padding: 12px; background: #059669; color: white; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; }
        button:hover { background: #047857; }
        .flash { padding: 10px; border-radius: 8px; margin-bottom: 16px; }
        .flash.danger { background: #fef2f2; color: #dc2626; border: 1px solid #fca5a5; }
        .flash.success { background: #ecfdf5; color: #059669; border: 1px solid #6ee7b7; }
        .footer { text-align: center; font-size: 0.8rem; color: #94a3b8; margin-top: 16px; }
        .demo-users { background: #f8fafc; padding: 12px; border-radius: 8px; margin-top: 16px; font-size: 0.8rem; }
    </style>
</head>
<body>
    <div class="card">
        <h1>💰 PricePoint POS</h1>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST">
            <div class="form-group">
                <label>Email</label>
                <input type="email" name="email" placeholder="admin@pricepoint.com" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" placeholder="••••••••" required>
            </div>
            <button type="submit">🔐 Login</button>
        </form>
        <div class="demo-users">
            <strong>Demo Accounts:</strong><br>
            pos@pricepoint.com / electronics2026 (POS User)<br>
            admin@pricepoint.com / electronics2026 (Admin)
        </div>
        <div class="footer">PricePoint POS v1.0</div>
    </div>
</body>
</html>
            """)
        return "✅ Templates created! <a href='/login'>Go to Login</a>"
    except Exception as e:
        return f"Error: {e}"

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('📱 PRICE POINT POS')
    print('=' * 60)
    print(f'📊 Products: {len(load_products())}')
    print(f'📊 Customers: {len(load_customers())}')
    print('=' * 60)
    print('\n🚀 Starting...')
    print('📍 http://localhost:5000')
    print('🔑 pos@pricepoint.com / electronics2026')
    print('=' * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
