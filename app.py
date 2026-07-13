from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
import os
import traceback
import json

from config import Config
from routes.shop import shop_bp
from routes.api import api_bp
from routes.admin import admin_bp
from utils.data import load_orders, load_products, load_bundles, sync_products_from_supabase, sync_pending_data_if_possible

app = Flask(__name__)
application = app
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.permanent_session_lifetime = Config.PERMANENT_SESSION_LIFETIME
app.template_folder = 'templates'
app.static_folder = Config.STATIC_FOLDER

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


@app.template_filter('format_number')
def format_number_filter(value):
    try:
        if value is None:
            return '0'
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return '0'


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/admin/') or request.path.startswith('/api/'):
        return jsonify({'error': 'Not found', 'message': 'The requested endpoint does not exist'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    print(f'Server error: {error}')
    traceback.print_exc()
    if request.path.startswith('/admin/') or request.path.startswith('/api/'):
        return jsonify({'error': 'Server error', 'message': str(error)}), 500
    return render_template('500.html'), 500


app.register_blueprint(shop_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)


# ============================================================
# HELPERS - SAFE VERSIONS
# ============================================================

def load_customers():
    """Load customers safely - returns empty list on error"""
    try:
        # Try to import and use real function
        from utils.data import load_customers as load_customers_real
        result = load_customers_real()
        if result:
            return result
    except Exception as e:
        print(f"⚠️ Could not load real customers: {e}")
    
    # Return mock customers
    return [
        {'name': 'Walk-in Customer', 'email': 'walkin@example.com', 'phone': 'N/A'},
        {'name': 'John Doe', 'email': 'john@example.com', 'phone': '+254 700 000 000'},
        {'name': 'Jane Smith', 'email': 'jane@example.com', 'phone': '+254 711 111 111'}
    ]


# ============================================================
# PWA ROUTES
# ============================================================

@app.route('/manifest.json')
def serve_manifest():
    try:
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')
    except Exception as e:
        print(f"❌ Error serving manifest: {e}")
        return "Manifest not found", 404


@app.route('/sw.js')
def serve_sw():
    try:
        response = send_from_directory('static', 'sw.js', mimetype='application/javascript')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    except Exception as e:
        print(f"❌ Error serving sw.js: {e}")
        return "Service Worker not found", 404


@app.route('/offline.html')
def serve_offline():
    try:
        return render_template('offline.html')
    except Exception as e:
        print(f"❌ Error serving offline.html: {e}")
        return "Offline page not found", 404


@app.route('/pos')
def pos_page():
    """Main POS page"""
    try:
        # Check login
        if 'user' not in session:
            return redirect(url_for('user_login'))
        
        # Load data
        products = load_products() or []
        customers = load_customers()
        
        return render_template('pos.html', 
                             products=products, 
                             customers=customers,
                             session=session)
    except Exception as e:
        print(f'❌ Error in /pos: {e}')
        traceback.print_exc()
        # Return with empty data rather than crashing
        return render_template('pos.html', 
                             products=[], 
                             customers=[],
                             session=session)


@app.route('/favicon.ico')
def serve_favicon():
    try:
        return send_from_directory('static/icons', 'favicon.ico', mimetype='image/x-icon')
    except Exception as e:
        print(f"⚠️ Favicon not found: {e}")
        return "", 204


@app.route('/static/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory('static', filename)
    except Exception as e:
        print(f"❌ Error serving static file: {e}")
        return "File not found", 404


@app.before_request
def maybe_sync_pending_orders():
    if request.path.startswith('/static/') or request.path.startswith('/favicon.ico'):
        return None
    try:
        sync_pending_data_if_possible()
    except Exception as e:
        print(f"⚠️ Sync error (ignored): {e}")
    return None


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
        
        # ===== LEGACY AUTH - WORKS WITHOUT DATABASE =====
        users = {
            'admin@pricepoint.com': {
                'password': 'electronics2026',
                'name': 'Admin User',
                'role': 'admin',
                'redirect': '/admin'
            },
            'user@pricepoint.com': {
                'password': 'electronics2026',
                'name': 'John Doe',
                'role': 'user',
                'redirect': '/pos'
            },
            'pos@pricepoint.com': {
                'password': 'electronics2026',
                'name': 'POS Operator',
                'role': 'pos',
                'redirect': '/pos'
            },
            'manager@pricepoint.com': {
                'password': 'electronics2026',
                'name': 'Store Manager',
                'role': 'manager',
                'redirect': '/pos'
            }
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
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('user_login'))


# ============================================================
# DEBUG & HEALTH
# ============================================================

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'pwa_ready': True
    })


@app.route('/debug')
def debug():
    try:
        products = load_products()
        return jsonify({
            'products_count': len(products),
            'session': session.get('user', {}).get('email', 'None'),
            'pwa_routes': ['/pos', '/sw.js', '/manifest.json', '/offline.html']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/load-sample-data', methods=['GET', 'POST'])
def load_sample_data():
    try:
        sample_products = [
            {
                'id': 'iphone_15',
                'name': 'iPhone 15 Pro Max',
                'price': 245000.0,
                'cost_price': 180000.0,
                'category': 'Phones',
                'description': 'Latest Apple flagship with A17 Pro chip',
                'image': 'https://images.unsplash.com/photo-1592286927505-1def25e4c479?w=500',
                'stock': 15,
                'rating': 4.9,
                'reviews': 245,
                'badge': 'Best Seller',
            },
            {
                'id': 'macbook_pro',
                'name': 'MacBook Pro 16"',
                'price': 450000.0,
                'cost_price': 350000.0,
                'category': 'Laptops',
                'description': 'Professional laptop with M3 Max chip',
                'image': 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500',
                'stock': 8,
                'rating': 4.8,
                'reviews': 156,
                'badge': 'New',
            },
            {
                'id': 'airpods_pro',
                'name': 'AirPods Pro 2',
                'price': 35000.0,
                'cost_price': 22000.0,
                'category': 'Accessories',
                'description': 'Premium wireless earbuds with ANC',
                'image': 'https://images.unsplash.com/photo-1606841838e0-bf1baf2dc3e9?w=500',
                'stock': 25,
                'rating': 4.7,
                'reviews': 389,
                'badge': 'Trending',
            },
            {
                'id': 'samsung_s24',
                'name': 'Samsung Galaxy S24 Ultra',
                'price': 225000.0,
                'cost_price': 115000.0,
                'category': 'Phones',
                'description': 'Flagship Android phone with advanced camera',
                'image': 'https://images.unsplash.com/photo-1511707267537-b85faf00021e?w=500',
                'stock': 23,
                'rating': 4.6,
                'reviews': 234,
            },
            {
                'id': 'ipad_pro',
                'name': 'iPad Pro 12.9"',
                'price': 185000.0,
                'cost_price': 140000.0,
                'category': 'Tablets',
                'description': 'Powerful tablet with M2 chip',
                'image': 'https://images.unsplash.com/photo-1561070791-2526d30994b5?w=500',
                'stock': 12,
                'rating': 4.7,
                'reviews': 198,
                'badge': 'New',
            },
        ]

        import requests
        added = 0
        for product in sample_products:
            try:
                response = requests.post(
                    f"{Config.SUPABASE_URL}/rest/v1/products",
                    headers=Config.SUPABASE_HEADERS,
                    json=product,
                    timeout=5,
                )
                if response.status_code in [200, 201]:
                    added += 1
            except Exception as exc:
                print(f"Error adding {product['name']}: {exc}")
        
        if added > 0:
            sync_products_from_supabase()

        return jsonify({
            'success': True,
            'added': added,
            'total': len(sample_products),
            'message': f'Loaded {added}/{len(sample_products)} sample products'
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('📱 PRICE POINT - Premium Electronics Shop')
    print('=' * 60)
    print(f"🌍 Environment: {'Vercel' if Config.IS_VERCEL else 'Local'}")
    print(f"\n📊 Products: {len(load_products())}")
    print(f"📊 Orders: {len(load_orders())}")
    print('=' * 60)
    print('\n🚀 Starting server...')
    print('📍 http://localhost:5000')
    print('🔑 Login: admin@pricepoint.com / electronics2026')
    print('=' * 60)
    app.run(debug=not Config.IS_VERCEL, host='0.0.0.0', port=5000)
