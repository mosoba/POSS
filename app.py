# app.py - Complete with all routes

from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime
import os
import traceback

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
# PWA ROUTES - FIXED
# ============================================================

@app.route('/manifest.json')
def serve_manifest():
    """Serves the manifest explicitly from the static folder"""
    static_dir = os.path.join(app.root_path, 'static')
    try:
        return send_from_directory(static_dir, 'manifest.json', mimetype='application/manifest+json')
    except Exception as e:
        print(f"❌ Error serving manifest.json: {e}")
        return "Manifest not found", 404


@app.route('/sw.js')
def serve_sw():
    """Serves the service worker explicitly from the static folder"""
    static_dir = os.path.join(app.root_path, 'static')
    try:
        return send_from_directory(static_dir, 'sw.js', mimetype='application/javascript')
    except Exception as e:
        print(f"❌ Error serving sw.js: {e}")
        return "Service Worker not found", 404


@app.route('/offline.html')
def serve_offline():
    """Serves your fallback offline page"""
    try:
        return render_template('offline.html')
    except Exception as e:
        print(f"❌ Error serving offline.html: {e}")
        return "Offline page not found", 404


@app.route('/pos')
def pos_page():
    """Main POS page - Entry point for PWA"""
    try:
        # Check if user is logged in
        if 'user' not in session:
            return redirect(url_for('user_login'))
        
        # Load products
        products = load_products()
        
        # Mock customers for POS
        customers = [
            {'name': 'Walk-in Customer', 'email': 'walkin@example.com', 'phone': 'N/A'},
            {'name': 'John Doe', 'email': 'john@example.com', 'phone': '+254 700 000 000'},
            {'name': 'Jane Smith', 'email': 'jane@example.com', 'phone': '+254 711 111 111'}
        ]
        
        if not products:
            products = []
            
        return render_template('pos.html', 
                             products=products, 
                             customers=customers,
                             session=session)
    except Exception as e:
        print(f'❌ Error in /pos: {e}')
        traceback.print_exc()
        return render_template('pos.html', 
                             products=[], 
                             customers=[],
                             session=session)


@app.route('/favicon.ico')
def serve_favicon():
    """Serves favicon"""
    static_dir = os.path.join(app.root_path, 'static', 'icons')
    try:
        return send_from_directory(static_dir, 'favicon.ico', mimetype='image/x-icon')
    except Exception as e:
        print(f"⚠️ Favicon not found: {e}")
        return "", 204


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serves static files"""
    static_dir = os.path.join(app.root_path, 'static')
    try:
        return send_from_directory(static_dir, filename)
    except Exception as e:
        print(f"❌ Error serving static file: {e}")
        return "File not found", 404


# ============================================================
# END PWA ROUTES
# ============================================================


@app.before_request
def maybe_sync_pending_orders():
    if request.path.startswith('/static/') or request.path.startswith('/favicon.ico'):
        return None
    sync_pending_data_if_possible()
    return None


# ============================================================
# HOME & LOGIN ROUTES
# ============================================================

@app.route('/')
def home():
    """Redirect to login or dashboard"""
    if 'user' in session:
        if session['user'].get('role') == 'admin':
            return redirect('/admin')
        return redirect('/pos')  # ← Changed from /admin/pos to /pos
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """Unified login with database authentication"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return render_template('admin_login.html')
        
        # Database authentication
        try:
            from models.user import User
            user, error = User.authenticate(email, password)
            
            if user:
                session['user'] = {
                    'id': user.id,
                    'email': user.email,
                    'name': user.full_name,
                    'role': user.role
                }
                
                if user.role == 'admin':
                    flash('Welcome back, ' + user.full_name + '!', 'success')
                    return redirect('/admin')
                else:
                    flash('Welcome, ' + user.full_name + '!', 'success')
                    return redirect('/pos')
        except Exception as e:
            print(f"DB auth error: {e}")
        
        # Legacy authentication
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
    """Logout user"""
    session.pop('user', None)
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('user_login'))


# ============================================================
# HEALTH & DEBUG ROUTES
# ============================================================

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'message': 'Server is running', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/debug')
def debug():
    try:
        orders = load_orders()
        products = load_products()
        bundles = load_bundles()
        return jsonify({
            'orders_count': len(orders),
            'products_count': len(products),
            'bundles_count': len(bundles),
            'sample_order': orders[0] if orders else None,
            'sample_product': products[0] if products else None,
            'is_vercel': Config.IS_VERCEL,
        })
    except Exception as exc:
        return jsonify({'error': str(exc)})


@app.route('/load-sample-data', methods=['GET', 'POST'])
def load_sample_data():
    # ... your existing code ...
    pass


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
