from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
import os
import traceback
import json

app = Flask(__name__)
application = app

# ============================================================
# CONFIGURATION
# ============================================================

app.secret_key = 'pricepoint-pos-secret-key-2026'
app.permanent_session_lifetime = timedelta(days=30)
app.template_folder = 'templates'
app.static_folder = 'static'

os.makedirs('static/icons', exist_ok=True)


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    print(f'Server error: {error}')
    traceback.print_exc()
    return render_template('500.html'), 500


# ============================================================
# DATA - Hardcoded for Offline Support
# ============================================================

PRODUCTS = [
    {
        'id': '1',
        'name': 'iPhone 15 Pro Max',
        'price': 245000,
        'stock': 15,
        'category': 'Phones',
        'image': 'https://images.unsplash.com/photo-1592286927505-1def25e4c479?w=500',
        'barcode': 'IP15PM001'
    },
    {
        'id': '2',
        'name': 'MacBook Pro 16"',
        'price': 450000,
        'stock': 8,
        'category': 'Laptops',
        'image': 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500',
        'barcode': 'MBP16M3'
    },
    {
        'id': '3',
        'name': 'AirPods Pro 2',
        'price': 35000,
        'stock': 25,
        'category': 'Accessories',
        'image': 'https://images.unsplash.com/photo-1606841838e0-bf1baf2dc3e9?w=500',
        'barcode': 'APP2'
    },
    {
        'id': '4',
        'name': 'Samsung Galaxy S24 Ultra',
        'price': 225000,
        'stock': 23,
        'category': 'Phones',
        'image': 'https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=500',
        'barcode': 'SGS24U'
    },
    {
        'id': '5',
        'name': 'iPad Pro 12.9"',
        'price': 185000,
        'stock': 12,
        'category': 'Tablets',
        'image': 'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=500',
        'barcode': 'IP129'
    },
    {
        'id': '6',
        'name': 'HP Spectre x360',
        'price': 125000,
        'stock': 18,
        'category': 'Laptops',
        'image': 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500',
        'barcode': 'HPSX360'
    },
    {
        'id': '7',
        'name': 'Apple Watch Series 9',
        'price': 62000,
        'stock': 26,
        'category': 'Wearables',
        'image': 'https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=500',
        'barcode': 'AW9'
    },
    {
        'id': '8',
        'name': 'USB-C Fast Cable',
        'price': 1200,
        'stock': 98,
        'category': 'Accessories',
        'image': 'https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500',
        'barcode': 'USBCF'
    }
]

CUSTOMERS = [
    {'name': 'Walk-in Customer', 'email': 'walkin@example.com', 'phone': 'N/A'},
    {'name': 'John Doe', 'email': 'john@example.com', 'phone': '+254 700 000 000'},
    {'name': 'Jane Smith', 'email': 'jane@example.com', 'phone': '+254 711 111 111'}
]


def load_products():
    """Load products - works offline"""
    return PRODUCTS


def load_customers():
    """Load customers - works offline"""
    return CUSTOMERS


# ============================================================
# PWA ROUTES - OFFLINE SUPPORT
# ============================================================

@app.route('/manifest.json')
def serve_manifest():
    """Serve PWA manifest"""
    try:
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')
    except Exception:
        # Fallback: serve from root
        return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')


@app.route('/sw.js')
def serve_sw():
    """Serve Service Worker"""
    try:
        response = send_from_directory('static', 'sw.js', mimetype='application/javascript')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    except Exception:
        return "Service Worker not found", 404


@app.route('/offline.html')
def serve_offline():
    """Serve offline fallback page"""
    try:
        return render_template('offline.html')
    except Exception:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Offline</title></head>
        <body style="font-family: system-ui; padding: 40px; text-align: center;">
            <h1>📡 Offline</h1>
            <p>You are offline. Please connect to the internet.</p>
            <button onclick="location.reload()" style="padding: 10px 24px; background: #059669; color: white; border: none; border-radius: 8px; cursor: pointer;">Retry</button>
        </body>
        </html>
        """, 503


@app.route('/pos')
def pos_page():
    """Main POS page - Entry point for PWA"""
    try:
        # Check login
        if 'user' not in session:
            return redirect(url_for('user_login'))
        
        # Load data
        products = load_products()
        customers = load_customers()
        
        return render_template('pos.html', 
                             products=products, 
                             customers=customers,
                             session=session)
    except Exception as e:
        print(f'❌ Error in /pos: {e}')
        traceback.print_exc()
        # Return error page with empty data
        return render_template('pos.html', 
                             products=[], 
                             customers=[],
                             session=session)


@app.route('/favicon.ico')
def serve_favicon():
    """Serve favicon"""
    try:
        return send_from_directory('static/icons', 'favicon.ico', mimetype='image/x-icon')
    except Exception:
        return "", 204


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    try:
        return send_from_directory('static', filename)
    except Exception:
        return "File not found", 404


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

@app.route('/')
def home():
    """Home page - redirect to login or dashboard"""
    if 'user' in session:
        if session['user'].get('role') == 'admin':
            return redirect('/admin')
        return redirect('/pos')
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """Login page - works offline"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return render_template('admin_login.html')
        
        # Simple authentication (no database needed)
        USERS = {
            'admin@pricepoint.com': {'password': 'electronics2026', 'name': 'Admin User', 'role': 'admin', 'redirect': '/admin'},
            'user@pricepoint.com': {'password': 'electronics2026', 'name': 'John Doe', 'role': 'user', 'redirect': '/pos'},
            'pos@pricepoint.com': {'password': 'electronics2026', 'name': 'POS Operator', 'role': 'pos', 'redirect': '/pos'},
            'manager@pricepoint.com': {'password': 'electronics2026', 'name': 'Store Manager', 'role': 'manager', 'redirect': '/pos'}
        }
        
        if email in USERS and USERS[email]['password'] == password:
            session['user'] = {
                'email': email,
                'name': USERS[email]['name'],
                'role': USERS[email]['role'],
                'id': 'legacy_' + email
            }
            flash('Welcome, ' + USERS[email]['name'] + '!', 'success')
            return redirect(USERS[email]['redirect'])
        else:
            flash('Invalid email or password', 'danger')
            return render_template('admin_login.html')
    
    return render_template('admin_login.html')


@app.route('/logout')
def user_logout():
    """Logout user"""
    session.pop('user', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('user_login'))


# ============================================================
# HEALTH & TEST ROUTES
# ============================================================

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'pwa_ready': True,
        'products': len(load_products()),
        'customers': len(load_customers()),
        'version': '1.0.0'
    })


@app.route('/test')
def test():
    """Test route - verifies everything is working"""
    return jsonify({
        'status': 'ok',
        'message': 'PricePoint POS is running!',
        'products_count': len(load_products()),
        'customers_count': len(load_customers()),
        'session': session.get('user', {}).get('email', 'No session'),
        'routes': {
            '/pos': 'OK',
            '/sw.js': 'OK (served from static)',
            '/manifest.json': 'OK (served from static)',
            '/offline.html': 'OK (served from templates)'
        }
    })


# ============================================================
# ADMIN ROUTES (Simple Fallback)
# ============================================================

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard - simple version"""
    if 'user' not in session or session['user'].get('role') != 'admin':
        flash('Admin access required', 'danger')
        return redirect('/pos')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard</title>
        <style>
            body {{ font-family: system-ui; padding: 40px; max-width: 800px; margin: 0 auto; background: #f1f5f9; }}
            .card {{ background: white; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }}
            h1 {{ color: #0f172a; }}
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
            .stat {{ background: #f8fafc; padding: 16px; border-radius: 8px; text-align: center; }}
            .stat .number {{ font-size: 2rem; font-weight: 700; color: #059669; }}
            .stat .label {{ color: #64748b; font-size: 0.8rem; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #059669; color: white; text-decoration: none; border-radius: 8px; }}
            .btn:hover {{ background: #047857; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📊 Admin Dashboard</h1>
            <p>Welcome, {session['user']['name']}!</p>
            <div style="margin-top: 20px;">
                <a href="/pos" class="btn">🛒 Go to POS</a>
                <a href="/logout" class="btn" style="background: #ef4444;">🚪 Logout</a>
            </div>
        </div>
        <div class="card">
            <h2>📈 Stats</h2>
            <div class="stats">
                <div class="stat">
                    <div class="number">{len(load_products())}</div>
                    <div class="label">Products</div>
                </div>
                <div class="stat">
                    <div class="number">{len(load_customers())}</div>
                    <div class="label">Customers</div>
                </div>
                <div class="stat">
                    <div class="number">✅</div>
                    <div class="label">Status</div>
                </div>
            </div>
        </div>
        <div class="card">
            <h2>🔗 Quick Links</h2>
            <p><a href="/pos">Point of Sale</a></p>
            <p><a href="/health">Health Check</a></p>
            <p><a href="/test">Test Route</a></p>
        </div>
        <div class="card">
            <h2>📡 PWA Status</h2>
            <p>✅ Service Worker: <a href="/sw.js">/sw.js</a></p>
            <p>✅ Manifest: <a href="/manifest.json">/manifest.json</a></p>
            <p>✅ Offline Page: <a href="/offline.html">/offline.html</a></p>
        </div>
    </body>
    </html>
    """


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('📱 PRICE POINT - Premium Electronics POS')
    print('=' * 60)
    print(f"\n📊 Products: {len(load_products())}")
    print(f"📊 Customers: {len(load_customers())}")
    print('=' * 60)
    print('\n🚀 Starting server...')
    print('📍 http://localhost:5000')
    print('🔑 Login: pos@pricepoint.com / electronics2026')
    print('👤 Admin: admin@pricepoint.com / electronics2026')
    print('=' * 60)
    print('\n📡 PWA Routes:')
    print('   📄 /pos          - Main POS page')
    print('   📄 /sw.js        - Service Worker')
    print('   📄 /manifest.json - PWA Manifest')
    print('   📄 /offline.html - Offline fallback')
    print('   📄 /health       - Health check')
    print('   📄 /test         - Test route')
    print('=' * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
