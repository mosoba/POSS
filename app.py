from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
import os
import traceback
import json

from config import Config

app = Flask(__name__)
application = app
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY if hasattr(Config, 'SECRET_KEY') else 'dev-secret-key'
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
# SIMPLE DATA (No Database)
# ============================================================

# Hardcoded products for testing
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
    """Load products from hardcoded list"""
    return PRODUCTS


def load_customers():
    """Load customers from hardcoded list"""
    return CUSTOMERS


# ============================================================
# PWA ROUTES
# ============================================================

@app.route('/manifest.json')
def serve_manifest():
    try:
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')
    except Exception:
        return send_from_directory('.', 'manifest.json', mimetype='application/manifest+json')


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
        return "<h1>Offline</h1><p>You are offline. Please reconnect.</p>", 503


@app.route('/pos')
def pos_page():
    """Main POS page"""
    try:
        # Check login
        if 'user' not in session:
            return redirect(url_for('user_login'))
        
        # Get data
        products = load_products()
        customers = load_customers()
        
        return render_template('pos.html', 
                             products=products, 
                             customers=customers,
                             session=session)
    except Exception as e:
        print(f'❌ Error in /pos: {e}')
        traceback.print_exc()
        # Return error page
        return render_template('pos.html', 
                             products=[], 
                             customers=[],
                             session=session)


@app.route('/favicon.ico')
def serve_favicon():
    try:
        return send_from_directory('static/icons', 'favicon.ico', mimetype='image/x-icon')
    except Exception:
        return "", 204


@app.route('/static/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory('static', filename)
    except Exception:
        return "File not found", 404


# ============================================================
# AUTH ROUTES
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
            return render_template('admin_login.html')
        
        # Simple auth - no database needed
        users = {
            'admin@pricepoint.com': {'password': 'electronics2026', 'name': 'Admin User', 'role': 'admin', 'redirect': '/admin'},
            'user@pricepoint.com': {'password': 'electronics2026', 'name': 'John Doe', 'role': 'user', 'redirect': '/pos'},
            'pos@pricepoint.com': {'password': 'electronics2026', 'name': 'POS Operator', 'role': 'pos', 'redirect': '/pos'},
            'manager@pricepoint.com': {'password': 'electronics2026', 'name': 'Store Manager', 'role': 'manager', 'redirect': '/pos'}
        }
        
        if email in users and users[email]['password'] == password:
            session['user'] = {
                'email': email,
                'name': users[email]['name'],
                'role': users[email]['role'],
                'id': 'legacy_' + email
            }
            flash('Welcome, ' + users[email]['name'] + '!', 'success')
            return redirect(users[email]['redirect'])
        else:
            flash('Invalid email or password', 'danger')
            return render_template('admin_login.html')
    
    return render_template('admin_login.html')


@app.route('/logout')
def user_logout():
    session.pop('user', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('user_login'))


# ============================================================
# TEST ROUTE
# ============================================================

@app.route('/test')
def test():
    """Test route to verify app is working"""
    return jsonify({
        'status': 'ok',
        'message': 'App is running!',
        'products_count': len(load_products()),
        'session': session.get('user', {}).get('email', 'None'),
        'routes': {
            '/pos': 'OK',
            '/sw.js': 'OK',
            '/manifest.json': 'OK',
            '/offline.html': 'OK'
        }
    })


@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'pwa_ready': True,
        'version': '1.0.0'
    })


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('📱 PRICE POINT - Premium Electronics Shop')
    print('=' * 60)
    print(f"\n📊 Products: {len(load_products())}")
    print(f"📊 Customers: {len(load_customers())}")
    print('=' * 60)
    print('\n🚀 Starting server...')
    print('📍 http://localhost:5000')
    print('🔑 Login: pos@pricepoint.com / electronics2026')
    print('=' * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
