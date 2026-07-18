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
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for, send_from_directory, make_response
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
# ✅ ADMIN DASHBOARD - COMPLETE WORKING VERSION
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

        print("=" * 60)
        print("📊 ADMIN DASHBOARD LOADING...")
        print("=" * 60)

        # ============================================================
        # LOAD DATA
        # ============================================================
        all_products = load_products() or []
        all_orders = load_orders() or []
        
        print(f"📡 Products loaded: {len(all_products)}")
        print(f"📡 Orders loaded: {len(all_orders)}")

        # If no products, seed demo products
        if not all_products:
            all_products = seed_demo_products()
            print(f"🌱 Seeded {len(all_products)} demo products")

        # ============================================================
        # CALCULATE STATS DIRECTLY
        # ============================================================
        total_orders = 0
        total_revenue = 0
        today_revenue = 0
        today_orders = 0
        pending_orders = 0
        low_stock_items = 0
        total_products = len(all_products) if all_products else 0

        today = datetime.utcnow().date()

        # Process orders
        if all_orders:
            for order in all_orders:
                # Skip cancelled orders
                if order.get('status') == 'cancelled':
                    continue
                
                total_orders += 1
                total_revenue += float(order.get('total', 0))
                
                if order.get('status') == 'pending':
                    pending_orders += 1
                
                # Check if order is from today
                created_at = order.get('created_at', '')
                if created_at:
                    try:
                        if isinstance(created_at, str):
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
                        elif isinstance(created_at, datetime):
                            order_date = created_at.date()
                        else:
                            continue
                        
                        if order_date == today:
                            today_revenue += float(order.get('total', 0))
                            today_orders += 1
                    except Exception as e:
                        print(f"Date parse error: {e}")
                        continue

        # Calculate low stock
        if all_products:
            low_stock_items = len([p for p in all_products if p.get('stock', 0) < 10])

        # ============================================================
        # BUILD STATS OBJECT
        # ============================================================
        stats = {
            'total_products': total_products,
            'total_bundles': 0,
            'total_cart_items': 0,
            'low_stock': low_stock_items,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'pos_orders': total_orders,
            'web_orders': 0,
            'total_revenue': total_revenue,
            'total_cost': 0,
            'total_profit': total_revenue,
            'total_items_sold': 0,
            'total_customers': 0,
            'today_revenue': today_revenue,
            'today_orders': today_orders,
            'yesterday_revenue': 0,
            'month_revenue': total_revenue,
            'month_orders': total_orders,
            'last_month_revenue': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'online',
        }

        # ============================================================
        # LOG THE STATS FOR DEBUGGING
        # ============================================================
        print("=" * 60)
        print("📊 ADMIN STATS CALCULATED:")
        print(f"  Total Products: {stats['total_products']}")
        print(f"  Total Orders: {stats['total_orders']}")
        print(f"  Total Revenue: KSh {stats['total_revenue']:,.2f}")
        print(f"  Today Revenue: KSh {stats['today_revenue']:,.2f}")
        print(f"  Today Orders: {stats['today_orders']}")
        print("=" * 60)

        # ============================================================
        # RENDER TEMPLATE
        # ============================================================
        response = make_response(render_template(
            'admin.html',
            # Products
            products=all_products[:20] if all_products else [],
            all_products=all_products or [],
            total_products=total_products,
            product_page=1,
            total_product_pages=1,
            per_page=20,
            # Orders
            orders=all_orders[:20] if all_orders else [],
            recent_orders=all_orders[:3] if all_orders else [],
            total_orders=total_orders,
            orders_page=1,
            total_order_pages=1,
            # Customers
            customers=[],
            total_customers=0,
            customers_page=1,
            total_customer_pages=1,
            # Stats & Analytics
            stats=stats,
            analytics={
                'today_revenue': today_revenue,
                'today_orders': today_orders,
                'total_revenue': total_revenue,
                'total_orders': total_orders,
                'monthly_data': {},
                'category_sales': {}
            },
            pos_count=total_orders,
            bundles=[],
            DB_CONNECTED=True,
            total_products_count=total_products,
            total_orders_count=total_orders,
            total_customers_count=0
        ))
        
        # FORCE NO-CACHE HEADERS
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response

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
        
        response = make_response(render_template('admin.html',
            products=[],
            all_products=[],
            total_products=0,
            product_page=1,
            total_product_pages=1,
            per_page=20,
            orders=[],
            recent_orders=[],
            total_orders=0,
            orders_page=1,
            total_order_pages=1,
            customers=[],
            total_customers=0,
            customers_page=1,
            total_customer_pages=1,
            bundles=[],
            pos_count=0,
            analytics={},
            stats=stats,
            DB_CONNECTED=False,
            total_products_count=0,
            total_orders_count=0,
            total_customers_count=0
        ))
        
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response


# ============================================================
# ✅ POS ROUTE - FIXED WITH FALLBACK
# ============================================================

@admin_bp.route('/admin/pos')
def admin_pos():
    if not session.get('admin_logged_in'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin.user_login'))

    try:
        # Try to load products from Supabase
        all_products = load_products()
        print(f"📡 POS - Products from load_products(): {len(all_products) if all_products else 0}")
        
        # If no products, use demo products
        if not all_products or len(all_products) == 0:
            print("⚠️ No products found, using demo products for POS")
            all_products = seed_demo_products()
            
    except Exception as e:
        print(f"❌ Error loading products for POS: {e}")
        all_products = seed_demo_products()
        print(f"📡 Using {len(all_products)} demo products")

    # Ensure each product has required fields
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

    # Debug: Print first few products
    if all_products:
        print(f"📋 First product: {all_products[0] if all_products else 'None'}")
        print(f"📦 Total products for POS: {len(all_products)}")

    return render_template('pos.html',
        products=all_products,
        customers=customers,
        DB_CONNECTED=True
    )


# ============================================================
# DEBUG ENDPOINT - Check Products
# ============================================================

@admin_bp.route('/admin/debug-products')
@admin_required
def debug_products():
    try:
        products = load_products()
        return jsonify({
            'success': True,
            'count': len(products) if products else 0,
            'sample': products[:3] if products else [],
            'full': products if products else []
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


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
# API ENDPOINTS
# ============================================================

@admin_bp.route('/admin/api/analytics')
def admin_api_analytics():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        orders = load_orders()
        
        total_revenue = 0
        total_orders = 0
        today_revenue = 0
        today_orders = 0
        today = datetime.utcnow().date()
        
        for order in orders:
            if order.get('status') == 'cancelled':
                continue
            
            total_orders += 1
            total_revenue += float(order.get('total', 0))
            
            created_at = order.get('created_at', '')
            if created_at:
                try:
                    if isinstance(created_at, str):
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
                    elif isinstance(created_at, datetime):
                        order_date = created_at.date()
                    else:
                        continue
                    
                    if order_date == today:
                        today_revenue += float(order.get('total', 0))
                        today_orders += 1
                except:
                    pass
        
        return jsonify({
            'success': True,
            'total_revenue': total_revenue,
            'total_orders': total_orders,
            'today_revenue': today_revenue,
            'today_orders': today_orders
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/sales-stats', methods=['GET'])
def api_sales_stats():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        orders = load_orders()
        products = load_products()
        today = datetime.utcnow().date()

        today_revenue = 0
        today_orders = 0
        today_returns = 0
        today_return_amount = 0
        all_customers = set()

        for order in orders:
            created_at = order.get('created_at', '')
            if not created_at:
                continue

            try:
                order_date = None
                if isinstance(created_at, str):
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
                elif isinstance(created_at, datetime):
                    order_date = created_at.date()
                else:
                    continue

                customer = order.get('customer', {})
                customer_name = None
                if isinstance(customer, dict):
                    customer_name = customer.get('name', '')
                elif isinstance(customer, str):
                    try:
                        c = json.loads(customer)
                        customer_name = c.get('name', '')
                    except:
                        pass

                if customer_name and customer_name not in ['Walk-in Customer', 'Web Customer', '']:
                    all_customers.add(customer_name)

                if order_date == today:
                    status = order.get('status', '')
                    total = float(order.get('total', 0))

                    if status == 'returned':
                        today_returns += 1
                        today_return_amount += abs(total)
                        today_revenue += total
                    elif status != 'cancelled':
                        today_revenue += total
                        today_orders += 1

            except Exception as e:
                print(f"Error processing order: {e}")
                continue

        total_products = len(products) if products else 0

        return jsonify({
            'success': True,
            'today_revenue': today_revenue,
            'today_orders': today_orders,
            'today_returns': today_returns,
            'today_return_amount': today_return_amount,
            'total_customers': len(all_customers),
            'total_products': total_products
        })
    except Exception as e:
        print(f"❌ Sales stats error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/sync-queue', methods=['POST'])
def api_sync_queue():
    try:
        data = request.get_json()
        if not data or not data.get('orders'):
            return jsonify({
                'success': True,
                'synced': 0,
                'failed': 0,
                'message': 'No orders provided to sync'
            })

        orders_to_sync = data.get('orders', [])
        print(f"🔄 Received {len(orders_to_sync)} orders to sync")

        synced = 0
        failed = 0

        for order in orders_to_sync:
            try:
                order_id = order.get('order_id', f'OFF-{uuid.uuid4().hex[:8].upper()}')
                
                # Check if order already exists
                check_response = requests.get(
                    f"{Config.SUPABASE_URL}/rest/v1/orders?order_id=eq.{order_id}",
                    headers=Config.SUPABASE_HEADERS,
                    timeout=10
                )

                if check_response.status_code == 200 and check_response.json():
                    print(f"⏭️ Order {order_id} already exists")
                    synced += 1
                    continue

                # Build order data
                order_data = {
                    'order_id': order_id,
                    'items': order.get('items', []),
                    'subtotal': float(order.get('subtotal', 0)),
                    'shipping': float(order.get('shipping', 0)),
                    'total': float(order.get('total', 0)),
                    'status': order.get('status', 'confirmed'),
                    'source': order.get('source', 'pos'),
                    'created_at': order.get('created_at', datetime.utcnow().isoformat()),
                    'customer_name': order.get('customer_name', 'Walk-in Customer'),
                    'customer_email': order.get('customer_email', 'walkin@example.com'),
                    'customer_phone': order.get('customer_phone', 'N/A'),
                    'customer_address': order.get('customer_address', 'In-store purchase'),
                    'customer': order.get('customer', {}),
                    'user_id': order.get('user_id', 'unknown'),
                    'user_name': order.get('user_name', 'Unknown User'),
                    'user_role': order.get('user_role', 'user'),
                    'staff_name': order.get('staff_name', order.get('user_name', 'Unknown User'))
                }

                # Ensure items is a list
                if not isinstance(order_data['items'], list):
                    order_data['items'] = []

                for item in order_data['items']:
                    if not isinstance(item, dict):
                        continue
                    if 'product_id' not in item:
                        item['product_id'] = str(uuid.uuid4())
                    if 'quantity' not in item:
                        item['quantity'] = 1
                    if 'price' not in item:
                        item['price'] = 0
                    if 'name' not in item:
                        item['name'] = 'Unknown Product'
                    if 'total' not in item:
                        item['total'] = float(item.get('price', 0)) * float(item.get('quantity', 1))

                # Save to Supabase
                response = requests.post(
                    f"{Config.SUPABASE_URL}/rest/v1/orders",
                    headers=Config.SUPABASE_HEADERS,
                    json=order_data,
                    timeout=15
                )

                if response.status_code in [200, 201]:
                    print(f"✅ Synced: {order_id}")
                    synced += 1
                else:
                    print(f"❌ Failed to sync: {order_id} - {response.status_code}")
                    failed += 1

            except Exception as e:
                failed += 1
                print(f"❌ Sync error for {order.get('order_id', 'unknown')}: {e}")

        if synced > 0:
            import utils.data
            utils.data.orders_cache = []

        return jsonify({
            'success': True,
            'synced': synced,
            'failed': failed,
            'message': f"Synced {synced} orders, {failed} failed"
        })

    except Exception as e:
        print(f"❌ Sync queue error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/sync-order', methods=['POST'])
def api_sync_order():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        if not data or not data.get('order_id'):
            return jsonify({'success': False, 'message': 'No order data provided'}), 400

        order_id = data.get('order_id')
        print(f"🔄 Syncing order: {order_id}")

        # Check if order already exists
        check_response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/orders?order_id=eq.{order_id}",
            headers=Config.SUPABASE_HEADERS,
            timeout=10
        )

        if check_response.status_code == 200 and check_response.json():
            return jsonify({'success': True, 'message': 'Order already exists'})

        order_data = {
            'order_id': data.get('order_id'),
            'items': data.get('items', []),
            'subtotal': float(data.get('subtotal', 0)),
            'shipping': float(data.get('shipping', 0)),
            'total': float(data.get('total', 0)),
            'status': data.get('status', 'confirmed'),
            'source': data.get('source', 'pos'),
            'created_at': data.get('created_at', datetime.utcnow().isoformat()),
            'customer_name': data.get('customer_name', 'Walk-in Customer'),
            'customer_email': data.get('customer_email', 'walkin@example.com'),
            'customer_phone': data.get('customer_phone', 'N/A'),
            'customer_address': data.get('customer_address', 'In-store purchase'),
            'customer': data.get('customer', {}),
            'user_id': data.get('user_id', 'unknown'),
            'user_name': data.get('user_name', 'Unknown User'),
            'user_role': data.get('user_role', 'user'),
            'staff_name': data.get('staff_name', data.get('user_name', 'Unknown User'))
        }

        if not isinstance(order_data['items'], list):
            order_data['items'] = []

        for item in order_data['items']:
            if not isinstance(item, dict):
                continue
            if 'product_id' not in item:
                item['product_id'] = str(uuid.uuid4())
            if 'quantity' not in item:
                item['quantity'] = 1
            if 'price' not in item:
                item['price'] = 0
            if 'name' not in item:
                item['name'] = 'Unknown Product'
            if 'total' not in item:
                item['total'] = float(item.get('price', 0)) * float(item.get('quantity', 1))

        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/orders",
            headers=Config.SUPABASE_HEADERS,
            json=order_data,
            timeout=15
        )

        if response.status_code in [200, 201]:
            print(f"✅ Order synced: {order_id}")
            import utils.data
            utils.data.orders_cache = []
            return jsonify({'success': True, 'message': 'Order synced successfully'})
        else:
            print(f"❌ Sync failed: {response.status_code}")
            return jsonify({'success': False, 'message': f'Sync failed: {response.status_code}'}), 500

    except Exception as e:
        print(f'❌ Sync order error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# PROCESS RETURN
# ============================================================

@admin_bp.route('/admin/api/process-return', methods=['POST'])
def api_process_return():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        items_to_return = data.get('items', [])
        refund_total = data.get('refund_total', 0)
        customer_name = data.get('customer_name', 'Customer')
        reason = data.get('reason', 'Customer return')

        if not items_to_return:
            return jsonify({'success': False, 'message': 'No items to return'}), 400

        return_items = []
        for item in items_to_return:
            item_price = float(item.get('price', 0))
            item_qty = int(item.get('quantity', 1))
            return_items.append({
                'product_id': str(item.get('id', '')),
                'name': item.get('name', 'Product'),
                'price': item_price,
                'quantity': item_qty,
                'total': item_price * item_qty,
                'type': 'return'
            })

        return_order_id = data.get('return_order_id', f'RET-{uuid.uuid4().hex[:8].upper()}')

        return_order_data = {
            'order_id': return_order_id,
            'items': return_items,
            'subtotal': refund_total,
            'shipping': 0,
            'total': -refund_total,
            'status': 'returned',
            'source': 'pos',
            'created_at': datetime.utcnow().isoformat(),
            'customer': {
                'name': customer_name,
                'email': 'return@example.com',
                'phone': 'N/A',
                'address': 'Return'
            },
            'customer_name': customer_name,
            'customer_email': 'return@example.com',
            'customer_phone': 'N/A',
            'customer_address': 'Return',
            'return_reason': reason,
            'return_amount': refund_total,
            'is_return': True
        }

        # Restock products
        for item in items_to_return:
            product_id = str(item.get('id', ''))
            quantity = int(item.get('quantity', 1))
            if product_id:
                try:
                    products = load_products()
                    for p in products:
                        if str(p.get('id')) == product_id:
                            current_stock = int(p.get('stock', 0))
                            new_stock = current_stock + quantity
                            requests.patch(
                                f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                                headers=Config.SUPABASE_HEADERS,
                                json={'stock': new_stock},
                                timeout=10
                            )
                            break
                except Exception as e:
                    print(f"⚠️ Error restocking product {product_id}: {e}")

        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/orders",
            headers=Config.SUPABASE_HEADERS,
            json=return_order_data,
            timeout=10,
        )

        if response.status_code in [200, 201]:
            import utils.data
            utils.data.orders_cache = []
            utils.data.products_cache = []

            return jsonify({
                'success': True,
                'order_id': return_order_id,
                'message': f'Return processed! Refund: KSh {refund_total:,.2f}',
                'refund_total': refund_total,
                'revenue_deducted': refund_total
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to process return: {response.status_code}'
            }), 500

    except Exception as e:
        print(f'❌ Return error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# ADMIN ROUTES
# ============================================================

@admin_bp.route('/admin/upload-image', methods=['POST'])
def upload_image():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    if file and allowed_file(file.filename):
        filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        image_url = f"/static/uploads/{filename}"
        return jsonify({'success': True, 'url': image_url, 'message': 'Image uploaded successfully!'})
    return jsonify({'success': False, 'message': 'Invalid file type'}), 400


@admin_bp.route('/admin/products', methods=['POST'])
def admin_products():
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = {
                'id': request.form.get('id', '').strip(),
                'name': request.form.get('name', '').strip(),
                'price': float(request.form.get('price', 0) or 0),
                'cost_price': float(request.form.get('cost_price', 0) or 0),
                'image': request.form.get('image', '').strip(),
                'category': request.form.get('category', '').strip(),
                'description': request.form.get('description', '').strip(),
                'rating': float(request.form.get('rating', 4.0) or 4.0),
                'reviews': int(request.form.get('reviews', 0) or 0),
                'badge': request.form.get('badge', '').strip(),
                'stock': int(request.form.get('stock', 0) or 0),
                'original_price': float(request.form.get('original_price', 0) or 0) or None,
                'specs': [s.strip() for s in request.form.get('specs', '').split(',') if s.strip()]
            }

        product_id = data.get('id', '').strip()
        if not product_id:
            return jsonify({'success': False, 'message': 'Product ID is required'}), 400

        existing_products = load_products()
        product_exists = False
        for p in existing_products:
            if p.get('id') == product_id:
                product_exists = True
                break

        if product_exists:
            response = requests.patch(
                f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
                headers=Config.SUPABASE_HEADERS,
                json=data,
                timeout=10,
            )
            if response.status_code in [200, 204]:
                import utils.data
                utils.data.products_cache = []
                return jsonify({'success': True, 'message': 'Product updated successfully!', 'product': data})
            else:
                return jsonify({'success': False, 'message': f'Error updating product: {response.status_code}'}), 500

        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/products",
            headers=Config.SUPABASE_HEADERS,
            json=data,
            timeout=10,
        )

        if response.status_code in [200, 201]:
            import utils.data
            utils.data.products_cache = []
            return jsonify({'success': True, 'message': 'Product saved successfully!', 'product': data})
        else:
            return jsonify({'success': False, 'message': f'Error saving product: {response.status_code}'}), 500

    except Exception as exc:
        print(f'Product save error: {exc}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(exc)}), 500


@admin_bp.route('/admin/products/<product_id>', methods=['DELETE'])
def admin_delete_product(product_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        response = requests.delete(
            f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
            headers=Config.SUPABASE_HEADERS,
            timeout=5,
        )
        if response.status_code in [200, 204]:
            import utils.data
            utils.data.products_cache = []
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Failed to delete'})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)})


@admin_bp.route('/admin/orders/<order_id>/status', methods=['POST'])
def admin_update_order_status(order_id):
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    try:
        new_status = request.json.get('status')
        if not new_status:
            return jsonify({'success': False, 'message': 'Status required'}), 400
        response = requests.patch(
            f"{Config.SUPABASE_URL}/rest/v1/orders?order_id=eq.{order_id}",
            headers=Config.SUPABASE_HEADERS,
            json={'status': new_status},
            timeout=5,
        )
        if response.status_code in [200, 204]:
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Failed to update status'})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500


@admin_bp.route('/api/products/<product_id>', methods=['GET'])
def api_get_product(product_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        products = load_products()
        for product in products:
            if str(product.get('id')) == str(product_id):
                return jsonify(product)
        return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/orders/<order_id>', methods=['GET'])
def api_get_order(order_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        orders = load_orders()

        for order in orders:
            if str(order.get('order_id')) == str(order_id):
                customer = order.get('customer', {})
                if isinstance(customer, str):
                    try:
                        customer = json.loads(customer) if customer else {}
                    except:
                        customer = {}
                if isinstance(customer, list):
                    customer = customer[0] if customer else {}
                if not isinstance(customer, dict):
                    customer = {}

                items = order.get('items', [])
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except:
                        items = []
                if not isinstance(items, list):
                    items = []

                formatted_items = []
                for item in items:
                    if isinstance(item, dict):
                        formatted_items.append({
                            'name': item.get('name', 'Product'),
                            'quantity': item.get('quantity', 1),
                            'price': item.get('price', 0),
                            'total': item.get('total', item.get('price', 0) * item.get('quantity', 1))
                        })

                return jsonify({
                    'order_id': order.get('order_id', 'N/A'),
                    'customer': {
                        'name': customer.get('name', order.get('customer_name', 'Customer')),
                        'email': customer.get('email', order.get('customer_email', 'N/A')),
                        'phone': customer.get('phone', order.get('customer_phone', 'N/A')),
                        'address': customer.get('address', order.get('customer_address', 'N/A')),
                    },
                    'items': formatted_items,
                    'subtotal': order.get('subtotal', 0),
                    'shipping': order.get('shipping', 0),
                    'total': order.get('total', 0),
                    'status': order.get('status', 'pending'),
                    'created_at': order.get('created_at', ''),
                    'source': order.get('source', 'web'),
                })
        return jsonify({'error': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/api/orders', methods=['GET'])
@admin_required
def api_orders_paginated():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        all_orders = load_orders()
        all_orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        total = len(all_orders)
        start = (page - 1) * per_page
        end = start + per_page
        orders = all_orders[start:end]
        
        return jsonify({
            'success': True,
            'orders': orders,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'start': start + 1 if orders else 0,
            'end': min(end, total)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/customers', methods=['GET'])
def api_customers():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/customers",
            headers=Config.SUPABASE_HEADERS,
            timeout=10,
        )

        if response.status_code == 200:
            customers_from_db = response.json()
            if customers_from_db:
                result = []
                for c in customers_from_db:
                    result.append({
                        'name': c.get('name', ''),
                        'email': c.get('email', 'N/A'),
                        'phone': c.get('phone', 'N/A'),
                        'orders': 0,
                        'total_spent': 0
                    })
                return jsonify(result)

        orders = load_orders()
        customer_dict = {}

        for order in orders:
            name = None

            if order.get('customer_name'):
                name = order.get('customer_name')

            if not name:
                customer = order.get('customer', {})
                if isinstance(customer, dict):
                    name = customer.get('name')
                elif isinstance(customer, str):
                    try:
                        customer_obj = json.loads(customer)
                        name = customer_obj.get('name')
                    except:
                        pass

            if not name or name in ['Walk-in Customer', 'Web Customer', 'Customer', '']:
                continue

            email = order.get('customer_email', 'N/A')
            phone = order.get('customer_phone', 'N/A')

            if name not in customer_dict:
                customer_dict[name] = {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'orders': 0,
                    'total_spent': 0
                }
            customer_dict[name]['orders'] += 1
            customer_dict[name]['total_spent'] += order.get('total', 0)

        return jsonify(list(customer_dict.values()))

    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
