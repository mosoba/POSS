# ============================================================
# 1. IMPORTS
# ============================================================
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

# ============================================================
# 2. CREATE BLUEPRINT - THIS MUST COME FIRST!
# ============================================================
admin_bp = Blueprint('admin', __name__)

# ============================================================
# 3. DETECT VERCEL ENVIRONMENT
# ============================================================
IS_VERCEL = os.environ.get('VERCEL') == '1' or os.environ.get('NOW_REGION') is not None
print(f"🚀 Running on: {'Vercel' if IS_VERCEL else 'Local'}")
DATA_FILE = os.path.join('/tmp', 'data.json') if IS_VERCEL else 'data.json'

# ============================================================
# 4. HELPER FUNCTIONS
# ============================================================
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
    # ... your demo products ...

def get_default_users():
    # ... your default users ...

# ============================================================
# 5. AUTHENTICATION ROUTES
# ============================================================
@admin_bp.route('/login', methods=['GET', 'POST'])
def user_login():
    # ... your login code ...

@admin_bp.route('/logout')
def user_logout():
    # ... your logout code ...

@admin_bp.route('/admin/login')
def admin_login_redirect():
    return redirect(url_for('admin.user_login'))

@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out', 'success')
    return redirect(url_for('admin.user_login'))

# ============================================================
# 6. ADMIN DASHBOARD
# ============================================================
@admin_bp.route('/admin')
@admin_required
def admin_dashboard():
    # ... your dashboard code ...

# ============================================================
# 7. POS ROUTES
# ============================================================
@admin_bp.route('/admin/pos')
def admin_pos():
    # ... your POS code ...

@admin_bp.route('/admin/pos/place-order', methods=['POST'])
def admin_pos_place_order():
    # ... your POS order code ...

# ============================================================
# 8. API ROUTES
# ============================================================
@admin_bp.route('/admin/api/sync-queue', methods=['POST'])
def api_sync_queue():
    # ... your sync code ...

@admin_bp.route('/admin/api/process-return', methods=['POST'])
def api_process_return():
    # ... your return code ...

@admin_bp.route('/admin/api/sync-order', methods=['POST'])
def api_sync_order():
    # ... your sync order code ...

@admin_bp.route('/admin/api/unsynced-count', methods=['GET'])
def api_unsynced_count():
    # ... your unsynced count code ...

@admin_bp.route('/admin/api/offline-orders', methods=['GET'])
def api_offline_orders():
    # ... your offline orders code ...

@admin_bp.route('/admin/api/user-stats', methods=['GET'])
@login_required
def api_user_stats():
    # ... your user stats code ...

@admin_bp.route('/admin/api/analytics')
def admin_api_analytics():
    # ... your analytics code ...

@admin_bp.route('/admin/api/revenue')
def admin_api_revenue():
    # ... your revenue code ...

@admin_bp.route('/admin/api/sales-stats', methods=['GET'])
def api_sales_stats():
    # ... your sales stats code ...

# ============================================================
# 9. AJAX PAGINATION API ENDPOINTS
# ============================================================
@admin_bp.route('/admin/api/products', methods=['GET'])
@admin_required
def api_products_paginated():
    # ... your products pagination code ...

@admin_bp.route('/admin/api/orders', methods=['GET'])
@admin_required
def api_orders_paginated():
    # ... your orders pagination code ...

@admin_bp.route('/admin/api/customers', methods=['GET'])
@admin_required
def api_customers_paginated():
    # ... your customers pagination code ...

@admin_bp.route('/admin/api/order/<order_id>', methods=['GET'])
@admin_required
def api_get_order_details(order_id):
    # ... your order details code ...

@admin_bp.route('/admin/api/product/<product_id>', methods=['GET'])
@admin_required
def api_get_product_details(product_id):
    # ... your product details code ...

@admin_bp.route('/admin/api/product/<product_id>', methods=['PUT'])
@admin_required
def api_update_product(product_id):
    # ... your update product code ...

@admin_bp.route('/admin/api/product/<product_id>', methods=['DELETE'])
@admin_required
def api_delete_product(product_id):
    # ... your delete product code ...

# ============================================================
# 10. PRODUCT MANAGEMENT ROUTES
# ============================================================
@admin_bp.route('/admin/upload-image', methods=['POST'])
def upload_image():
    # ... your upload code ...

@admin_bp.route('/admin/products', methods=['POST'])
def admin_products():
    # ... your product save code ...

@admin_bp.route('/admin/products/<product_id>', methods=['DELETE'])
def admin_delete_product(product_id):
    # ... your product delete code ...

@admin_bp.route('/admin/orders/<order_id>/status', methods=['POST'])
def admin_update_order_status(order_id):
    # ... your order status code ...

@admin_bp.route('/api/products/<product_id>', methods=['GET'])
def api_get_product(product_id):
    # ... your get product code ...

@admin_bp.route('/api/orders/<order_id>', methods=['GET'])
def api_get_order(order_id):
    # ... your get order code ...

@admin_bp.route('/api/customers', methods=['GET'])
def api_customers():
    # ... your customers code ...

# ============================================================
# 11. MINIMAL TEST ROUTES - FOR VERCEL DEBUGGING
#     (PLACE THESE HERE - AFTER ALL MAIN ROUTES)
# ============================================================
@admin_bp.route('/minimal/test')
def minimal_test():
    """Simple test to verify Flask is working"""
    import os
    return jsonify({
        'status': '✅ Flask is working on Vercel!',
        'vercel': os.environ.get('VERCEL') == '1',
        'now_region': os.environ.get('NOW_REGION'),
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY)
    })

@admin_bp.route('/minimal/test-env')
def minimal_test_env():
    """Test environment variables"""
    import os
    return jsonify({
        'VERCEL': os.environ.get('VERCEL'),
        'NOW_REGION': os.environ.get('NOW_REGION'),
        'SUPABASE_URL': Config.SUPABASE_URL,
        'SUPABASE_KEY_exists': bool(Config.SUPABASE_KEY),
        'SUPABASE_KEY_preview': Config.SUPABASE_KEY[:20] + '...' if Config.SUPABASE_KEY else 'None'
    })

@admin_bp.route('/minimal/test-supabase')
def minimal_test_supabase():
    """Test Supabase connection directly"""
    import requests
    import os
    
    result = {
        'vercel': os.environ.get('VERCEL') == '1',
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

@admin_bp.route('/minimal/test-data')
def minimal_test_data():
    """Test data loading step by step"""
    import traceback
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

@admin_bp.route('/minimal/dashboard')
@admin_required
def minimal_dashboard():
    """Minimal dashboard for testing"""
    try:
        print("=" * 60)
        print("🚀 MINIMAL: Loading admin dashboard...")
        print("=" * 60)
        
        # Load data
        print("📦 Loading products...")
        products = load_products()
        print(f"✅ Loaded {len(products)} products")
        
        print("📦 Loading orders...")
        orders = load_orders()
        print(f"✅ Loaded {len(orders)} orders")
        
        # Clean products
        cleaned_products = []
        for p in products:
            clean_p = dict(p)
            if clean_p.get('stock') is None:
                clean_p['stock'] = 0
            if clean_p.get('price') is None:
                clean_p['price'] = 0
            if clean_p.get('name') is None:
                clean_p['name'] = 'Unnamed Product'
            if clean_p.get('category') is None:
                clean_p['category'] = 'Uncategorized'
            if clean_p.get('image') is None:
                clean_p['image'] = ''
            if clean_p.get('cost_price') is None:
                clean_p['cost_price'] = 0
            cleaned_products.append(clean_p)
        products = cleaned_products
        
        # Stats
        total_products = len(products)
        total_orders = len(orders)
        low_stock = len([p for p in products if p.get('stock', 0) < 10])
        total_revenue = sum(o.get('total', 0) for o in orders)
        pending_orders = len([o for o in orders if o.get('status') == 'pending'])
        
        stats = {
            'total_products': total_products,
            'total_orders': total_orders,
            'low_stock': low_stock,
            'pending_orders': pending_orders,
            'total_revenue': total_revenue,
            'today_revenue': 0,
            'today_orders': 0,
            'total_customers': 0,
            'total_profit': 0,
            'total_cost': 0,
            'total_bundles': 0,
            'total_cart_items': 0,
            'pos_orders': 0,
            'web_orders': 0,
            'total_items_sold': 0,
            'month_revenue': 0,
            'month_orders': 0,
            'yesterday_revenue': 0,
            'last_month_revenue': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'online'
        }
        
        print(f"📊 Rendering with {len(products)} products, {len(orders)} orders")
        print(f"📊 Stats: total_products={total_products}, total_orders={total_orders}")
        print("=" * 60)
        
        return render_template('admin_minimal.html',
            products=products[:10],
            orders=orders[:10],
            total_products=total_products,
            total_orders=total_orders,
            stats=stats,
            DB_CONNECTED=True
        )
        
    except Exception as e:
        print("=" * 60)
        print("❌ ERROR in minimal admin")
        print("=" * 60)
        print(f"Error: {e}")
        traceback.print_exc()
        print("=" * 60)
        
        return render_template('admin_minimal.html',
            products=[],
            orders=[],
            total_products=0,
            total_orders=0,
            stats={
                'total_products': 0,
                'total_orders': 0,
                'low_stock': 0,
                'pending_orders': 0,
                'total_revenue': 0,
                'today_revenue': 0,
                'today_orders': 0,
                'total_customers': 0,
                'total_profit': 0,
                'total_cost': 0,
                'total_bundles': 0,
                'total_cart_items': 0,
                'pos_orders': 0,
                'web_orders': 0,
                'total_items_sold': 0,
                'month_revenue': 0,
                'month_orders': 0,
                'yesterday_revenue': 0,
                'last_month_revenue': 0,
                'today_growth_pct': 0,
                'month_growth_pct': 0,
                'db_mode': 'offline'
            },
            DB_CONNECTED=False
        )

# ============================================================
# 12. PWA ROUTES - PUBLIC (AT THE VERY END)
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
