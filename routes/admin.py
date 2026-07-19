import sys
import os
import json

# Add the project root to Python path so config can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# On Vercel, we can only write to /tmp
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
        {'id': 'PROD_1', 'name': 'Wireless Headphones', 'price': 2999, 'stock': 45, 'category': 'Electronics', 'image': '', 'description': 'Premium wireless headphones'},
        {'id': 'PROD_2', 'name': 'USB-C Cable', 'price': 499, 'stock': 120, 'category': 'Accessories', 'image': ''},
        {'id': 'PROD_3', 'name': 'Bluetooth Speaker', 'price': 1499, 'stock': 30, 'category': 'Electronics', 'image': ''},
        {'id': 'PROD_4', 'name': 'Laptop Stand', 'price': 899, 'stock': 25, 'category': 'Furniture', 'image': ''},
        {'id': 'PROD_5', 'name': 'Wireless Mouse', 'price': 699, 'stock': 60, 'category': 'Accessories', 'image': ''},
        {'id': 'PROD_6', 'name': 'Mechanical Keyboard', 'price': 2499, 'stock': 15, 'category': 'Electronics', 'image': ''},
        {'id': 'PROD_7', 'name': 'HDMI Cable', 'price': 299, 'stock': 80, 'category': 'Accessories', 'image': ''},
        {'id': 'PROD_8', 'name': 'USB Hub', 'price': 1299, 'stock': 20, 'category': 'Accessories', 'image': ''},
        {'id': 'PROD_9', 'name': 'Monitor 24"', 'price': 14999, 'stock': 8, 'category': 'Electronics', 'image': ''},
        {'id': 'PROD_10', 'name': 'Desk Lamp', 'price': 599, 'stock': 35, 'category': 'Furniture', 'image': ''},
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

        user = session.get('user', {})
        user_name = user.get('name', 'Admin User')
        user_role = user.get('role', 'admin')

        all_products = load_products()
        all_orders = load_orders()
        
        # ============================================================
        # SAFELY CLEAN PRODUCTS - Fix any None values
        # ============================================================
        cleaned_products = []
        for p in all_products:
            clean_p = dict(p)
            # Fix stock
            if clean_p.get('stock') is None:
                clean_p['stock'] = 0
            # Fix price
            if clean_p.get('price') is None:
                clean_p['price'] = 0
            # Fix name
            if clean_p.get('name') is None:
                clean_p['name'] = 'Unnamed Product'
            # Fix category
            if clean_p.get('category') is None:
                clean_p['category'] = 'Uncategorized'
            # Fix image
            if clean_p.get('image') is None:
                clean_p['image'] = ''
            # Fix description
            if clean_p.get('description') is None:
                clean_p['description'] = ''
            # Fix cost_price
            if clean_p.get('cost_price') is None:
                clean_p['cost_price'] = 0
            # Fix badge
            if clean_p.get('badge') is None:
                clean_p['badge'] = ''
            cleaned_products.append(clean_p)
        
        all_products = cleaned_products
        
        print(f"📡 Loaded: {len(all_products)} products, {len(all_orders)} orders")

        if not all_products:
            all_products = seed_demo_products()
            # Clean demo products too
            for p in all_products:
                if p.get('stock') is None:
                    p['stock'] = 0
                if p.get('price') is None:
                    p['price'] = 0
                if p.get('name') is None:
                    p['name'] = 'Unnamed Product'
                if p.get('category') is None:
                    p['category'] = 'Uncategorized'
            try:
                for product in all_products:
                    requests.post(
                        f"{Config.SUPABASE_URL}/rest/v1/products",
                        headers=Config.SUPABASE_HEADERS,
                        json=product,
                        timeout=10
                    )
                print("🌱 Demo products seeded to Supabase")
            except Exception as e:
                print(f"⚠️ Could not seed demo products: {e}")

        bundles = load_bundles()
        cart = get_cart()
        analytics = get_sales_analytics()

        per_page = 10

        products_page = request.args.get('products_page', 1, type=int)
        orders_page = request.args.get('orders_page', 1, type=int)
        customers_page = request.args.get('customers_page', 1, type=int)

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
        total_revenue = sum(o.get('total', 0) for o in all_orders if o.get('status') != 'cancelled')
        pending_orders = len([o for o in all_orders if o.get('status') == 'pending'])
        
        # Safe low stock calculation
        low_stock_items = 0
        for p in all_products:
            stock = p.get('stock', 0)
            if stock is None:
                stock = 0
            if stock < 10:
                low_stock_items += 1

        now = datetime.utcnow()
        today = now.date()
        first_day_this_month = today.replace(day=1)

        today_revenue = 0
        today_orders = 0
        yesterday_revenue = 0
        month_revenue = 0
        month_orders = 0
        last_month_revenue = 0

        if today.month == 1:
            last_month_year = today.year - 1
            last_month_month = 12
        else:
            last_month_year = today.year
            last_month_month = today.month - 1

        first_day_last_month = datetime(last_month_year, last_month_month, 1).date()
        if today.month == 1:
            last_day_last_month = datetime(last_month_year, 12, 31).date()
        else:
            last_day_last_month = datetime(today.year, today.month, 1).date() - timedelta(days=1)

        for order in all_orders:
            total = order.get('total', 0)
            if isinstance(total, str):
                try:
                    total = float(total.replace(',', ''))
                except:
                    total = 0
            total = float(total or 0)

            if order.get('status') == 'cancelled':
                continue

            created_at = order.get('created_at', '')
            if not created_at:
                continue

            try:
                if isinstance(created_at, datetime):
                    order_date = created_at.date()
                elif isinstance(created_at, str):
                    if 'T' in created_at:
                        clean = created_at.replace('Z', '').replace('+00:00', '')
                        if '.' in clean:
                            order_date = datetime.fromisoformat(clean).date()
                        else:
                            order_date = datetime.strptime(clean[:10], '%Y-%m-%d').date()
                    elif ' ' in created_at:
                        order_date = datetime.strptime(created_at[:10], '%Y-%m-%d').date()
                    else:
                        order_date = datetime.strptime(created_at[:10], '%Y-%m-%d').date()
                else:
                    continue
            except Exception as e:
                print(f"Date parse error: {e}")
                continue

            if order_date == today:
                today_revenue += total
                today_orders += 1

            if order_date == today - timedelta(days=1):
                yesterday_revenue += total

            if order_date >= first_day_this_month:
                month_revenue += total
                month_orders += 1

            if first_day_last_month <= order_date <= last_day_last_month:
                last_month_revenue += total

        if yesterday_revenue > 0:
            today_growth = round(((today_revenue - yesterday_revenue) / yesterday_revenue) * 100, 1)
        else:
            today_growth = 100.0 if today_revenue > 0 else 0

        if last_month_revenue > 0:
            month_growth = round(((month_revenue - last_month_revenue) / last_month_revenue) * 100, 1)
        else:
            month_growth = 100.0 if month_revenue > 0 else 0

        total_customer_pages = (total_customers + per_page - 1) // per_page if total_customers > 0 else 1
        if customers_page < 1:
            customers_page = 1
        elif customers_page > total_customer_pages and total_customer_pages > 0:
            customers_page = total_customer_pages

        customers_start = (customers_page - 1) * per_page
        customers_end = customers_start + per_page
        paginated_customers = customers[customers_start:customers_end] if customers else []

        total_products = len(all_products)
        total_product_pages = (total_products + per_page - 1) // per_page if total_products > 0 else 1
        if products_page < 1:
            products_page = 1
        elif products_page > total_product_pages and total_product_pages > 0:
            products_page = total_product_pages

        products_start = (products_page - 1) * per_page
        products_end = products_start + per_page
        paginated_products = all_products[products_start:products_end] if all_products else []

        sorted_orders = sorted(all_orders, key=lambda x: x.get('created_at', ''), reverse=True)
        total_order_pages = (total_orders + per_page - 1) // per_page if total_orders > 0 else 1
        if orders_page < 1:
            orders_page = 1
        elif orders_page > total_order_pages and total_order_pages > 0:
            orders_page = total_order_pages

        orders_start = (orders_page - 1) * per_page
        orders_end = orders_start + per_page
        paginated_orders = sorted_orders[orders_start:orders_end] if sorted_orders else []

        recent_orders = sorted_orders[:3] if sorted_orders else []

        stats = {
            'total_products': total_products,
            'total_bundles': len(bundles),
            'total_cart_items': sum(cart.values()) if cart else 0,
            'low_stock': low_stock_items,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'pos_orders': pos_count,
            'web_orders': web_count,
            'total_revenue': total_revenue,
            'total_cost': analytics.get('total_cost', 0),
            'total_profit': analytics.get('total_profit', 0),
            'total_items_sold': analytics.get('total_items_sold', 0),
            'total_customers': total_customers,
            'today_revenue': today_revenue,
            'today_orders': today_orders,
            'yesterday_revenue': yesterday_revenue,
            'month_revenue': month_revenue,
            'month_orders': month_orders,
            'last_month_revenue': last_month_revenue,
            'today_growth_pct': today_growth,
            'month_growth_pct': month_growth,
            'db_mode': 'online',
        }

        return render_template('admin.html',
            products=paginated_products,
            all_products=all_products,
            total_products=total_products,
            product_page=products_page,
            total_product_pages=total_product_pages,
            orders=paginated_orders,
            recent_orders=recent_orders,
            total_orders=total_orders,
            orders_page=orders_page,
            total_order_pages=total_order_pages,
            customers=paginated_customers,
            total_customers=total_customers,
            customers_page=customers_page,
            total_customer_pages=total_customer_pages,
            per_page=per_page,
            bundles=bundles,
            stats=stats,
            pos_count=pos_count,
            analytics=analytics,
            DB_CONNECTED=True
        )

    except Exception as exc:
        print(f'Admin dashboard error: {exc}')
        traceback.print_exc()
        flash('Error loading admin dashboard', 'danger')
        return render_template('admin.html',
            products=[],
            bundles=[],
            orders=[],
            customers=[],
            pos_count=0,
            analytics={},
            stats={
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
            },
            total_products=0,
            total_product_pages=1,
            product_page=1,
            total_orders=0,
            total_order_pages=1,
            orders_page=1,
            total_customers=0,
            total_customer_pages=1,
            customers_page=1,
            per_page=10,
            recent_orders=[],
            DB_CONNECTED=False
        )


# ============================================================
# ============================================================
# TEST ROUTES - FOR VERCEL DEBUGGING
# ============================================================
# ============================================================

@admin_bp.route('/test')
def test():
    return jsonify({
        'status': '✅ Flask is working on Vercel!',
        'vercel': os.environ.get('VERCEL') == '1',
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY)
    })

@admin_bp.route('/test-supabase')
def test_supabase():
    result = {
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY),
    }
    try:
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
    except Exception as e:
        result['error'] = str(e)
    return jsonify(result)

@admin_bp.route('/test-data')
def test_data():
    try:
        products = load_products()
        orders = load_orders()
        return jsonify({
            'products': len(products),
            'orders': len(orders),
            'sample_product': products[0] if products else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/test-env')
def test_env():
    import os
    return jsonify({
        'VERCEL': os.environ.get('VERCEL'),
        'NOW_REGION': os.environ.get('NOW_REGION'),
        'SUPABASE_URL': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY)
    })


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
# POS ORDER ROUTE
# ============================================================

@admin_bp.route('/admin/pos/place-order', methods=['POST'])
def admin_pos_place_order():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        if not data or not data.get('items'):
            return jsonify({'success': False, 'message': 'No items in order'}), 400

        user = session.get('user', {})
        user_id = user.get('id', 'unknown')
        user_name = user.get('name', 'Unknown User')
        user_role = user.get('role', 'user')

        order_id = data.get('order_id', f'POS-{uuid.uuid4().hex[:8].upper()}')
        items = data.get('items', [])
        
        print(f"📦 Received order: {order_id}")
        print(f"📦 Items: {len(items)}")
        
        for item in items:
            print(f"  - {item.get('name')} x{item.get('quantity')}")

        print("📦 DEDUCTING STOCK...")
        
        stock_updated = []
        stock_failed = []
        
        for item in items:
            product_id = item.get('product_id')
            quantity = int(item.get('quantity', 1))
            
            if not product_id:
                print(f"⚠️ No product_id for item: {item.get('name')}")
                stock_failed.append({'name': item.get('name'), 'reason': 'No product_id'})
                continue
            
            try:
                print(f"🔍 Fetching product: {product_id}")
                response = requests.get(
                    f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                    headers=Config.SUPABASE_HEADERS,
                    timeout=10
                )
                
                if response.status_code == 200:
                    products = response.json()
                    if products and len(products) > 0:
                        product = products[0]
                        current_stock = product.get('stock', 0)
                        new_stock = max(0, current_stock - quantity)
                        
                        print(f"📦 {product.get('name')}: {current_stock} → {new_stock}")
                        
                        update_response = requests.patch(
                            f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                            headers=Config.SUPABASE_HEADERS,
                            json={'stock': new_stock},
                            timeout=10
                        )
                        
                        if update_response.status_code in [200, 204]:
                            print(f"✅ Stock updated: {product.get('name')}")
                            stock_updated.append({
                                'name': product.get('name'),
                                'old_stock': current_stock,
                                'new_stock': new_stock
                            })
                        else:
                            print(f"❌ Failed to update stock: {update_response.status_code}")
                            stock_failed.append({
                                'name': product.get('name'),
                                'reason': f'HTTP {update_response.status_code}'
                            })
                    else:
                        print(f"⚠️ Product not found: {product_id}")
                        stock_failed.append({
                            'name': item.get('name'),
                            'reason': 'Product not found'
                        })
                else:
                    print(f"❌ Failed to fetch product: {response.status_code}")
                    stock_failed.append({
                        'name': item.get('name'),
                        'reason': f'Fetch error: {response.status_code}'
                    })
                    
            except Exception as e:
                print(f"❌ Stock deduction error for {product_id}: {e}")
                stock_failed.append({
                    'name': item.get('name'),
                    'reason': str(e)
                })

        print(f"📊 Stock updated: {len(stock_updated)} items")
        for s in stock_updated:
            print(f"  ✅ {s['name']}: {s['old_stock']} → {s['new_stock']}")
        
        if stock_failed:
            print(f"❌ Stock failed: {len(stock_failed)} items")
            for s in stock_failed:
                print(f"  ❌ {s['name']}: {s['reason']}")

        subtotal = float(data.get('subtotal', 0))
        shipping = float(data.get('shipping', 0))
        total = float(data.get('total', subtotal + shipping))

        customer_name = data.get('customer_name', 'Walk-in Customer')
        customer_email = data.get('customer_email', 'walkin@example.com')
        customer_phone = data.get('customer_phone', 'N/A')
        customer_address = data.get('customer_address', 'In-store purchase')

        order_data = {
            'order_id': order_id,
            'items': items,
            'subtotal': subtotal,
            'shipping': shipping,
            'total': total,
            'status': 'confirmed',
            'source': 'pos',
            'created_at': datetime.utcnow().isoformat(),
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'customer_address': customer_address,
            'customer': {
                'name': customer_name,
                'email': customer_email,
                'phone': customer_phone,
                'address': customer_address,
            },
            'user_id': str(user_id),
            'user_name': user_name,
            'user_role': user_role,
            'staff_name': user_name
        }

        print(f"💰 Total: KSh {total}")

        try:
            response = requests.post(
                f"{Config.SUPABASE_URL}/rest/v1/orders",
                headers=Config.SUPABASE_HEADERS,
                json=order_data,
                timeout=15
            )

            if response.status_code in [200, 201]:
                print(f"✅ Order saved to Supabase: {order_id}")
                
                import utils.data
                utils.data.orders_cache = []
                utils.data.products_cache = []

                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'order': order_data,
                    'synced': True,
                    'stock_updated': stock_updated,
                    'stock_failed': stock_failed,
                    'message': f'✅ Order #{order_id} placed! Stock deducted: {len(stock_updated)} items.',
                    'total': total
                })
            else:
                print(f"❌ Failed to save order: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                
                return jsonify({
                    'success': False,
                    'message': f'Failed to save order: {response.status_code}',
                    'supabase_error': response.text[:500]
                }), 500
                
        except Exception as e:
            print(f"❌ Order save error: {e}")
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'Error saving order: {str(e)}'
            }), 500

    except Exception as exc:
        print(f'❌ POS Order error: {exc}')
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': f'Error: {str(exc)[:100]}'
        }), 500


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
