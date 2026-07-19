import sys
import os
import json
import traceback
import uuid
from datetime import datetime, timedelta
from functools import wraps

import requests
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for, send_from_directory
from werkzeug.utils import secure_filename

from config import Config
from utils.data import get_cart, get_sales_analytics, load_bundles, load_orders, load_products, update_product_stock

admin_bp = Blueprint('admin', __name__)

# ============================================================
# DETECT VERCEL ENVIRONMENT
# ============================================================
IS_VERCEL = os.environ.get('VERCEL') == '1' or os.environ.get('NOW_REGION') is not None
print(f"🚀 Running on: {'Vercel' if IS_VERCEL else 'Local'}")
DATA_FILE = os.path.join('/tmp', 'data.json') if IS_VERCEL else 'data.json'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def is_admin():
    user = session.get('user', {})
    return user.get('role') == 'admin' or session.get('admin_logged_in')


def is_logged_in():
    return 'user' in session or session.get('admin_logged_in')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash('Admin access required', 'danger')
            return redirect(url_for('admin.user_login'))
        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash('Please login first', 'danger')
            return redirect(url_for('admin.user_login'))
        return f(*args, **kwargs)
    return decorated_function


def seed_demo_products():
    demo_products = [
        {'id': 'PROD_1', 'name': 'Wireless Headphones', 'price': 2999, 'stock': 45, 'category': 'Electronics', 'image': '', 'description': 'Premium wireless headphones', 'cost_price': 1500},
        {'id': 'PROD_2', 'name': 'USB-C Cable', 'price': 499, 'stock': 120, 'category': 'Accessories', 'image': '', 'cost_price': 200},
        {'id': 'PROD_3', 'name': 'Bluetooth Speaker', 'price': 1499, 'stock': 30, 'category': 'Electronics', 'image': '', 'cost_price': 800},
        {'id': 'PROD_4', 'name': 'Laptop Stand', 'price': 899, 'stock': 25, 'category': 'Furniture', 'image': '', 'cost_price': 400},
        {'id': 'PROD_5', 'name': 'Wireless Mouse', 'price': 699, 'stock': 60, 'category': 'Accessories', 'image': '', 'cost_price': 300},
        {'id': 'PROD_6', 'name': 'Mechanical Keyboard', 'price': 2499, 'stock': 15, 'category': 'Electronics', 'image': '', 'cost_price': 1200},
        {'id': 'PROD_7', 'name': 'HDMI Cable', 'price': 299, 'stock': 80, 'category': 'Accessories', 'image': '', 'cost_price': 100},
        {'id': 'PROD_8', 'name': 'USB Hub', 'price': 1299, 'stock': 20, 'category': 'Accessories', 'image': '', 'cost_price': 600},
        {'id': 'PROD_9', 'name': 'Monitor 24"', 'price': 14999, 'stock': 8, 'category': 'Electronics', 'image': '', 'cost_price': 10000},
        {'id': 'PROD_10', 'name': 'Desk Lamp', 'price': 599, 'stock': 35, 'category': 'Furniture', 'image': '', 'cost_price': 300},
    ]
    return demo_products


def get_default_users():
    return [
        {'id': 'admin_1', 'email': 'admin@pricepoint.com', 'password': 'electronics2026', 'name': 'Admin User', 'role': 'admin'},
        {'id': 'manager_1', 'email': 'manager@pricepoint.com', 'password': 'electronics2026', 'name': 'Store Manager', 'role': 'manager'},
        {'id': 'pos_1', 'email': 'pos@pricepoint.com', 'password': 'electronics2026', 'name': 'POS Operator', 'role': 'pos'},
        {'id': 'user_1', 'email': 'user@pricepoint.com', 'password': 'electronics2026', 'name': 'Regular User', 'role': 'user'}
    ]


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Please enter both email and password', 'danger')
            return render_template('admin_login.html')

        users_legacy = {
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
                'redirect': '/admin/pos'
            },
            'pos@pricepoint.com': {
                'password': 'electronics2026',
                'name': 'POS Operator',
                'role': 'pos',
                'redirect': '/admin/pos'
            },
            'manager@pricepoint.com': {
                'password': 'electronics2026',
                'name': 'Store Manager',
                'role': 'manager',
                'redirect': '/admin/pos'
            }
        }

        username = request.form.get('username', '').strip()
        if username == 'admin' and password == 'electronics2026':
            session['admin_logged_in'] = True
            session['user'] = {
                'email': 'admin@pricepoint.com',
                'name': 'Admin User',
                'role': 'admin',
                'id': 'legacy_admin'
            }
            flash('Welcome back, Admin!', 'success')
            return redirect('/admin')

        if email in users_legacy and users_legacy[email]['password'] == password:
            session['user'] = {
                'email': email,
                'name': users_legacy[email]['name'],
                'role': users_legacy[email]['role'],
                'id': 'legacy_' + email
            }
            session['admin_logged_in'] = True
            flash('Welcome, ' + users_legacy[email]['name'] + '!', 'success')
            return redirect(users_legacy[email]['redirect'])
        else:
            flash('Invalid email or password', 'danger')
            return render_template('admin_login.html')

    return render_template('admin_login.html')


@admin_bp.route('/logout')
def user_logout():
    session.pop('user', None)
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin.user_login'))


@admin_bp.route('/admin/login')
def admin_login_redirect():
    return redirect(url_for('admin.user_login'))


@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out', 'success')
    return redirect(url_for('admin.user_login'))


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@admin_bp.route('/admin')
@admin_required
def admin_dashboard():
    if not is_admin():
        flash('Admin access required', 'danger')
        return redirect(url_for('admin.user_login'))

    try:
        import utils.data
        utils.data.orders_cache = []

        all_products = load_products()
        all_orders = load_orders()
        
        bundles = load_bundles()
        cart = get_cart()
        analytics = get_sales_analytics()

        per_page = 20
        products_page = request.args.get('products_page', 1, type=int)
        orders_page = request.args.get('orders_page', 1, type=int)
        customers_page = request.args.get('customers_page', 1, type=int)

        # BUILD CUSTOMER LIST
        customer_dict = {}
        pos_count = 0
        web_count = 0

        for order in all_orders:
            name = None
            email = None
            phone = None

            if order.get('customer_name'):
                name = order.get('customer_name')

            if not name:
                customer = order.get('customer', {})
                if isinstance(customer, dict):
                    name = customer.get('name')
                    if not email:
                        email = customer.get('email')
                    if not phone:
                        phone = customer.get('phone')
                elif isinstance(customer, str):
                    try:
                        customer_obj = json.loads(customer)
                        name = customer_obj.get('name')
                        if not email:
                            email = customer_obj.get('email')
                        if not phone:
                            phone = customer_obj.get('phone')
                    except:
                        pass

            if not name:
                email = order.get('customer_email', '')
                if email and '@' in email:
                    name = email.split('@')[0].replace('.', ' ').title()

            if not name or name in ['Walk-in Customer', 'Web Customer', 'Customer', 'Unknown', '']:
                continue

            if not email or email == 'N/A':
                email = order.get('customer_email', 'N/A')
                if (not email or email == 'N/A') and isinstance(order.get('customer'), dict):
                    email = order.get('customer', {}).get('email', 'N/A')

            if not phone or phone == 'N/A':
                phone = order.get('customer_phone', 'N/A')
                if (not phone or phone == 'N/A') and isinstance(order.get('customer'), dict):
                    phone = order.get('customer', {}).get('phone', 'N/A')

            if order.get('source') == 'pos':
                pos_count += 1
            else:
                web_count += 1

            if name not in customer_dict:
                customer_dict[name] = {
                    'name': name,
                    'email': email if email else 'N/A',
                    'phone': phone if phone else 'N/A',
                    'orders': 0,
                    'total_spent': 0
                }
            customer_dict[name]['orders'] += 1
            customer_dict[name]['total_spent'] += order.get('total', 0)

        customers = list(customer_dict.values())
        customers.sort(key=lambda x: x['orders'], reverse=True)
        total_customers = len(customers)

        total_orders = len([o for o in all_orders if o.get('status') != 'cancelled'])
        total_revenue = sum(float(o.get('total', 0) or 0) for o in all_orders if o.get('status') != 'cancelled')
        pending_orders = len([o for o in all_orders if o.get('status') == 'pending'])
        
        low_stock_items = 0
        for p in all_products:
            stock = p.get('stock')
            if stock is None:
                stock = 0
            try:
                if int(stock) < 10:
                    low_stock_items += 1
            except (ValueError, TypeError):
                pass

        total_products = len(all_products)

        stats = {
            'total_products': total_products or 0,
            'total_bundles': len(bundles) if bundles else 0,
            'total_cart_items': sum(cart.values()) if cart else 0,
            'low_stock': low_stock_items or 0,
            'total_orders': total_orders or 0,
            'pending_orders': pending_orders or 0,
            'pos_orders': pos_count or 0,
            'web_orders': web_count or 0,
            'total_revenue': total_revenue or 0,
            'total_cost': analytics.get('total_cost', 0) or 0,
            'total_profit': analytics.get('total_profit', 0) or 0,
            'total_items_sold': analytics.get('total_items_sold', 0) or 0,
            'total_customers': total_customers or 0,
            'today_revenue': 0,
            'today_orders': 0,
            'yesterday_revenue': 0,
            'month_revenue': 0,
            'month_orders': 0,
            'last_month_revenue': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'online',
        }

        return render_template('admin.html',
            products=all_products[:20],
            all_products=all_products,
            total_products=total_products,
            product_page=1,
            total_product_pages=1,
            orders=all_orders[:20],
            recent_orders=all_orders[:3] if all_orders else [],
            total_orders=total_orders,
            orders_page=1,
            total_order_pages=1,
            customers=customers[:20],
            total_customers=total_customers,
            customers_page=1,
            total_customer_pages=1,
            per_page=20,
            bundles=bundles,
            stats=stats,
            pos_count=pos_count,
            analytics=analytics,
            DB_CONNECTED=True,
            now=datetime.utcnow()
        )

    except Exception as exc:
        print(f'❌ Admin dashboard error: {exc}')
        traceback.print_exc()
        flash('Error loading admin dashboard', 'danger')
        
        stats = {
            'total_products': 0,
            'total_bundles': 0,
            'total_cart_items': 0,
            'low_stock': 0,
            'total_orders': 0,
            'pending_orders': 0,
            'pos_orders': 0,
            'web_orders': 0,
            'total_revenue': 0,
            'total_cost': 0,
            'total_profit': 0,
            'total_items_sold': 0,
            'total_customers': 0,
            'today_revenue': 0,
            'today_orders': 0,
            'yesterday_revenue': 0,
            'month_revenue': 0,
            'month_orders': 0,
            'last_month_revenue': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'offline',
        }
        
        return render_template('admin.html',
            products=[],
            all_products=[],
            total_products=0,
            product_page=1,
            total_product_pages=1,
            orders=[],
            recent_orders=[],
            total_orders=0,
            orders_page=1,
            total_order_pages=1,
            customers=[],
            total_customers=0,
            customers_page=1,
            total_customer_pages=1,
            per_page=20,
            bundles=[],
            pos_count=0,
            analytics={},
            stats=stats,
            DB_CONNECTED=False,
            now=datetime.utcnow()
        )


# ============================================================
# POS ROUTE
# ============================================================

@admin_bp.route('/admin/pos')
def admin_pos():
    if not session.get('admin_logged_in'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin.user_login'))

    all_products = load_products()
    for product in all_products:
        if 'price' not in product or product['price'] is None:
            product['price'] = 0
        if 'stock' not in product or product['stock'] is None:
            product['stock'] = 0
        if 'image' not in product:
            product['image'] = ''
        if 'name' not in product:
            product['name'] = 'Product'
        if 'id' not in product:
            product['id'] = str(uuid.uuid4())

    customers = []
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/customers",
            headers=Config.SUPABASE_HEADERS,
            timeout=10,
        )
        if response.status_code == 200:
            customers_from_db = response.json()
            for c in customers_from_db:
                customers.append({
                    'name': c.get('name', ''),
                    'email': c.get('email', ''),
                    'phone': c.get('phone', ''),
                    'orders': 0,
                    'total_spent': 0
                })
    except Exception as e:
        print(f"⚠️ Error loading customers: {e}")

    customers.sort(key=lambda x: x['name'])

    return render_template('pos.html',
        products=all_products,
        customers=customers,
        DB_CONNECTED=True
    )


# ============================================================
# API ROUTES
# ============================================================

@admin_bp.route('/admin/api/analytics')
def admin_api_analytics():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    orders = load_orders()
    analytics = get_sales_analytics()
    return jsonify(analytics)


# ============================================================
# TEST ROUTES - FOR VERCEL DEBUGGING
# ============================================================

@admin_bp.route('/test')
def test():
    """Simple test to verify Flask is working"""
    return jsonify({
        'status': '✅ Flask is working on Vercel!',
        'vercel': os.environ.get('VERCEL') == '1',
        'now_region': os.environ.get('NOW_REGION'),
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY)
    })


@admin_bp.route('/test-supabase')
def test_supabase():
    """Test Supabase connection directly"""
    result = {
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY),
        'key_preview': Config.SUPABASE_KEY[:20] + '...' if Config.SUPABASE_KEY else 'None'
    }
    
    try:
        print("🔗 Testing Supabase connection...")
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/products?limit=1",
            headers=Config.SUPABASE_HEADERS,
            timeout=5
        )
        result['status_code'] = response.status_code
        result['success'] = response.status_code == 200
        if response.status_code == 200:
            data = response.json()
            result['count'] = len(data)
            print(f"✅ Connected! Found {len(data)} products")
        else:
            result['error'] = response.text[:200]
            print(f"❌ Failed with status {response.status_code}")
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Error: {e}")
    
    return jsonify(result)


@admin_bp.route('/test-data')
def test_data():
    """Test data loading step by step"""
    result = {
        'steps': {},
        'error': None
    }
    
    # Step 1: Test imports
    try:
        from utils.data import load_products, load_orders
        result['steps']['imports'] = '✅ OK'
    except Exception as e:
        result['steps']['imports'] = f'❌ {str(e)}'
        return jsonify(result)
    
    # Step 2: Test load_products
    try:
        print("📦 Testing load_products...")
        products = load_products()
        result['steps']['load_products'] = f'✅ Loaded {len(products)} products'
        if products and len(products) > 0:
            result['sample_product'] = {
                'id': products[0].get('id'),
                'name': products[0].get('name'),
                'price': products[0].get('price'),
                'stock': products[0].get('stock')
            }
        print(f"✅ load_products: {len(products)} products")
    except Exception as e:
        result['steps']['load_products'] = f'❌ {str(e)}'
        result['traceback'] = traceback.format_exc()
        print(f"❌ load_products error: {e}")
    
    # Step 3: Test load_orders
    try:
        print("📦 Testing load_orders...")
        orders = load_orders()
        result['steps']['load_orders'] = f'✅ Loaded {len(orders)} orders'
        print(f"✅ load_orders: {len(orders)} orders")
    except Exception as e:
        result['steps']['load_orders'] = f'❌ {str(e)}'
        print(f"❌ load_orders error: {e}")
    
    return jsonify(result)


# ============================================================
# PWA ROUTES - PUBLIC
# ============================================================

@admin_bp.route('/offline.html')
def offline_page():
    try:
        return render_template('offline.html')
    except Exception as e:
        print(f"❌ Error serving offline.html: {e}")
        return "Offline page not found", 404


@admin_bp.route('/sw.js')
def service_worker():
    try:
        return send_from_directory('static', 'sw.js', mimetype='application/javascript')
    except Exception as e:
        print(f"❌ Error serving sw.js: {e}")
        return "Service Worker not found", 404


@admin_bp.route('/manifest.json')
def manifest():
    try:
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')
    except Exception as e:
        print(f"❌ Error serving manifest.json: {e}")
        return "Manifest not found", 404


@admin_bp.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory('static/icons', 'favicon.ico', mimetype='image/x-icon')
    except Exception as e:
        print(f"⚠️ Favicon not found: {e}")
        return "", 204


@admin_bp.route('/static/<path:filename>')
def static_files(filename):
    try:
        return send_from_directory('static', filename)
    except Exception as e:
        print(f"❌ Error serving static file: {e}")
        return "File not found", 404
