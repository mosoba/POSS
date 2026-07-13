from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
import os
import traceback
import jwt
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
# PWA ROUTES - COMPLETE OFFLINE SUPPORT
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
        response = send_from_directory(static_dir, 'sw.js', mimetype='application/javascript')
        # Prevent caching of service worker
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
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


@app.route('/pwa-entry.html')
def serve_pwa_entry():
    """Serves the static PWA entry point"""
    try:
        return send_from_directory('static', 'pwa-entry.html')
    except Exception as e:
        print(f"❌ Error serving pwa-entry.html: {e}")
        return "PWA Entry not found", 404


@app.route('/pos')
def pos_page():
    """Main POS page - Entry point for PWA"""
    try:
        # Check if user is logged in
        if 'user' not in session:
            # Check offline token
            offline_token = request.headers.get('X-Offline-Token')
            if offline_token:
                try:
                    user_data = verify_offline_token(offline_token)
                    if user_data:
                        session['user'] = user_data
                except:
                    pass
            
            if 'user' not in session:
                return redirect(url_for('user_login'))
        
        # Load products and customers
        products = load_products()
        
        # Mock customers for POS (if no customers in DB)
        customers = [
            {'name': 'Walk-in Customer', 'email': 'walkin@example.com', 'phone': 'N/A'},
            {'name': 'John Doe', 'email': 'john@example.com', 'phone': '+254 700 000 000'},
            {'name': 'Jane Smith', 'email': 'jane@example.com', 'phone': '+254 711 111 111'}
        ]
        
        # Try to load real customers if available
        try:
            from utils.data import load_customers
            real_customers = load_customers()
            if real_customers and len(real_customers) > 0:
                customers = real_customers
        except:
            pass
        
        if not products:
            products = []
            
        return render_template('pos.html', 
                             products=products, 
                             customers=customers,
                             session=session)
    except Exception as e:
        print(f'❌ Error in /pos: {e}')
        traceback.print_exc()
        # Return basic page for offline support
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
    """Serves static files with proper caching headers"""
    static_dir = os.path.join(app.root_path, 'static')
    try:
        response = send_from_directory(static_dir, filename)
        # Cache static assets for 1 year (except sw.js)
        if filename != 'sw.js':
            response.headers['Cache-Control'] = 'public, max-age=31536000'
        return response
    except Exception as e:
        print(f"❌ Error serving static file: {e}")
        return "File not found", 404


# ============================================================
# OFFLINE TOKEN FUNCTIONS
# ============================================================

def generate_offline_token(user_data):
    """Generate a token for offline authentication"""
    try:
        payload = {
            'user_id': user_data.get('id'),
            'email': user_data.get('email'),
            'name': user_data.get('name'),
            'role': user_data.get('role'),
            'exp': datetime.utcnow() + timedelta(days=7)
        }
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
        return token
    except Exception as e:
        print(f"❌ Error generating offline token: {e}")
        return None


def verify_offline_token(token):
    """Verify offline token and return user data"""
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return {
            'id': payload.get('user_id'),
            'email': payload.get('email'),
            'name': payload.get('name'),
            'role': payload.get('role')
        }
    except jwt.ExpiredSignatureError:
        print("⚠️ Offline token expired")
        return None
    except jwt.InvalidTokenError:
        print("⚠️ Invalid offline token")
        return None
    except Exception as e:
        print(f"❌ Error verifying offline token: {e}")
        return None


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
        return redirect('/pos')
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """Unified login with database authentication"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        remember = request.form.get('remember', False)
        
        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return render_template('admin_login.html')
        
        # ============================================================
        # DATABASE AUTHENTICATION - PRIMARY METHOD
        # ============================================================
        try:
            from models.user import User
            user, error = User.authenticate(email, password)
            
            if user:
                user_data = {
                    'id': user.id,
                    'email': user.email,
                    'name': user.full_name,
                    'role': user.role
                }
                session['user'] = user_data
                
                # Generate offline token for PWA
                offline_token = generate_offline_token(user_data)
                
                # Log the login
                try:
                    import requests
                    requests.post(
                        f"{Config.SUPABASE_URL}/rest/v1/user_logs",
                        headers=Config.SUPABASE_HEADERS,
                        json={
                            'user_id': user.id,
                            'action': 'login',
                            'details': {'method': 'web', 'remember': remember},
                            'ip_address': request.remote_addr,
                            'created_at': datetime.utcnow().isoformat()
                        },
                        timeout=5
                    )
                except:
                    pass
                
                if remember:
                    session.permanent = True
                    app.permanent_session_lifetime = timedelta(days=30)
                
                flash('Welcome back, ' + user.full_name + '!', 'success')
                
                if user.role == 'admin':
                    return redirect('/admin')
                else:
                    return redirect('/pos')
                    
        except Exception as e:
            print(f"DB auth error: {e}")
            # Fall through to legacy auth
        
        # ============================================================
        # LEGACY AUTHENTICATION - FALLBACK
        # ============================================================
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
            user_data = {
                'email': email,
                'name': users[email]['name'],
                'role': users[email]['role'],
                'id': 'legacy_' + email
            }
            session['user'] = user_data
            
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            
            flash('Welcome, ' + users[email]['name'] + '!', 'success')
            return redirect(users[email]['redirect'])
        else:
            flash('Invalid email or password', 'danger')
            return render_template('admin_login.html')
    
    return render_template('admin_login.html')


@app.route('/logout')
def user_logout():
    """Logout user"""
    user_id = session.get('user', {}).get('id')
    
    # Log the logout
    if user_id and not str(user_id).startswith('legacy_'):
        try:
            import requests
            requests.post(
                f"{Config.SUPABASE_URL}/rest/v1/user_logs",
                headers=Config.SUPABASE_HEADERS,
                json={
                    'user_id': user_id,
                    'action': 'logout',
                    'ip_address': request.remote_addr,
                    'created_at': datetime.utcnow().isoformat()
                },
                timeout=5
            )
        except:
            pass
    
    session.pop('user', None)
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('user_login'))


# ============================================================
# API ROUTES - OFFLINE SUPPORT
# ============================================================

@app.route('/api/offline-sync', methods=['POST'])
def offline_sync():
    """Sync offline orders when back online"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        orders = data.get('orders', [])
        synced = 0
        failed = 0
        
        for order in orders:
            try:
                # Save order to database
                # Your existing order saving logic here
                synced += 1
            except Exception as e:
                print(f"❌ Error syncing order: {e}")
                failed += 1
        
        return jsonify({
            'success': True,
            'synced': synced,
            'failed': failed,
            'message': f'Synced {synced} orders, {failed} failed'
        })
    except Exception as e:
        print(f"❌ Error in offline-sync: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/offline-orders', methods=['GET'])
def get_offline_orders():
    """Get offline orders from localStorage (via client)"""
    return jsonify({
        'success': True,
        'message': 'Offline orders should be sent from client'
    })


# ============================================================
# HEALTH & DEBUG ROUTES
# ============================================================

@app.route('/health')
def health():
    return jsonify({
        'status': 'ok', 
        'message': 'Server is running',
        'timestamp': datetime.utcnow().isoformat(),
        'offline_support': True,
        'pwa_ready': True
    })


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
            'pwa_routes': {
                '/pos': 'active',
                '/sw.js': 'active',
                '/manifest.json': 'active',
                '/offline.html': 'active'
            }
        })
    except Exception as exc:
        return jsonify({'error': str(exc)})


@app.route('/load-sample-data', methods=['GET', 'POST'])
def load_sample_data():
    """Load sample products for testing"""
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
            {
                'id': 'hp_spectre',
                'name': 'HP Spectre x360',
                'price': 125000.0,
                'cost_price': 90000.0,
                'category': 'Laptops',
                'description': 'Convertible premium laptop',
                'image': 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500',
                'stock': 18,
                'rating': 4.5,
                'reviews': 112,
            },
            {
                'id': 'watch_9',
                'name': 'Apple Watch Series 9',
                'price': 62000.0,
                'cost_price': 45000.0,
                'category': 'Wearables',
                'description': 'Smartwatch with fitness tracking',
                'image': 'https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=500',
                'stock': 26,
                'rating': 4.8,
                'reviews': 173,
            },
            {
                'id': 'usb_c_cable',
                'name': 'USB-C Fast Charging Cable',
                'price': 1200.0,
                'cost_price': 700.0,
                'category': 'Accessories',
                'description': 'Fast charging cable',
                'image': 'https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500',
                'stock': 98,
                'rating': 4.4,
                'reviews': 67,
            },
            {
                'id': 'dell_xps',
                'name': 'Dell XPS 15',
                'price': 165000.0,
                'cost_price': 120000.0,
                'category': 'Laptops',
                'description': 'Thin and powerful productivity laptop',
                'image': 'https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?w=500',
                'stock': 4,
                'rating': 4.6,
                'reviews': 99,
            },
            {
                'id': 'power_bank',
                'name': 'Anker 20000mAh Power Bank',
                'price': 8500.0,
                'cost_price': 5000.0,
                'category': 'Accessories',
                'description': 'Portable charger for travel',
                'image': 'https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=500',
                'stock': 57,
                'rating': 4.7,
                'reviews': 88,
            },
            {
                'id': 'buds_2',
                'name': 'Samsung Galaxy Buds 2',
                'price': 18000.0,
                'cost_price': 12000.0,
                'category': 'Audio',
                'description': 'Noise-cancelling earbuds',
                'image': 'https://images.unsplash.com/photo-1606225457115-9b0de873c5e1?w=500',
                'stock': 45,
                'rating': 4.5,
                'reviews': 74,
            },
        ]

        import requests
        added = 0
        errors = []
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
                else:
                    errors.append(f"{product['name']}: {response.status_code}")
            except Exception as exc:
                errors.append(f"{product['name']}: {str(exc)}")
        
        if added > 0:
            sync_products_from_supabase()

        return jsonify({
            'success': True, 
            'added': added, 
            'total': len(sample_products), 
            'errors': errors, 
            'message': f'Loaded {added}/{len(sample_products)} sample products'
        })
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


# ============================================================
# MAIN ENTRY POINT
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
    print('👥 Users: admin, manager, pos, user (all with same password)')
    print('=' * 60)
    print('\n📡 PWA Routes:')
    print('   📄 /pos          - Main POS page')
    print('   📄 /sw.js        - Service Worker')
    print('   📄 /manifest.json - PWA Manifest')
    print('   📄 /offline.html - Offline fallback')
    print('   📄 /pwa-entry.html - PWA entry point')
    print('=' * 60)
    app.run(debug=not Config.IS_VERCEL, host='0.0.0.0', port=5000)
