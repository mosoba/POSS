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
# ADMIN DASHBOARD - UPDATED WITH CREDIT & SUPPLIER DATA
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
        
        # SAFELY CLEAN PRODUCTS - Fix any None values
        cleaned_products = []
        for p in all_products:
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
            if clean_p.get('description') is None:
                clean_p['description'] = ''
            if clean_p.get('cost_price') is None:
                clean_p['cost_price'] = 0
            if clean_p.get('badge') is None:
                clean_p['badge'] = ''
            cleaned_products.append(clean_p)
        
        all_products = cleaned_products
        
        print(f"📡 Loaded: {len(all_products)} products, {len(all_orders)} orders")

        if not all_products:
            all_products = seed_demo_products()
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

        # ============================================================
        # ✅ FETCH CREDIT DATA
        # ============================================================
        credit_summary = {
            'total_customers': 0,
            'active_customers': 0,
            'total_balance': 0,
            'total_purchases': 0,
            'total_payments': 0
        }
        credit_customers = []
        overdue_count = 0

        try:
            response = requests.get(
                f"{Config.SUPABASE_URL}/rest/v1/credit_customers?select=*",
                headers=Config.SUPABASE_HEADERS,
                timeout=10
            )
            
            if response.status_code == 200:
                credit_customers = response.json()
                total_cust = len(credit_customers)
                active_cust = sum(1 for c in credit_customers if c.get('account_status') == 'active')
                total_balance = sum(c.get('current_balance', 0) for c in credit_customers)
                
                # Get transactions
                tx_response = requests.get(
                    f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?select=*",
                    headers=Config.SUPABASE_HEADERS,
                    timeout=10
                )
                
                total_purchases = 0
                total_payments = 0
                if tx_response.status_code == 200:
                    transactions = tx_response.json()
                    total_purchases = sum(t.get('amount', 0) for t in transactions if t.get('transaction_type') == 'purchase')
                    total_payments = sum(t.get('amount', 0) for t in transactions if t.get('transaction_type') == 'payment')
                
                overdue_count = sum(1 for c in credit_customers if c.get('current_balance', 0) > c.get('credit_limit', 0))
                
                credit_summary = {
                    'total_customers': total_cust,
                    'active_customers': active_cust,
                    'total_balance': total_balance,
                    'total_purchases': total_purchases,
                    'total_payments': total_payments
                }
                print(f"✅ Loaded {total_cust} credit customers")
            else:
                print(f"⚠️ Credit customers fetch error: {response.status_code}")
        except Exception as e:
            print(f"❌ Error loading credit data: {e}")

        # ============================================================
        # ✅ FETCH SUPPLIER DATA
        # ============================================================
        supplier_summary = {
            'total_suppliers': 0,
            'active_suppliers': 0,
            'total_products': 0
        }
        suppliers = []
        low_stock_count = low_stock_items

        try:
            response = requests.get(
                f"{Config.SUPABASE_URL}/rest/v1/suppliers?select=*",
                headers=Config.SUPABASE_HEADERS,
                timeout=10
            )
            
            if response.status_code == 200:
                suppliers = response.json()
                total_supp = len(suppliers)
                active_supp = sum(1 for s in suppliers if s.get('status') == 'active')
                
                # Get product counts for suppliers
                prod_response = requests.get(
                    f"{Config.SUPABASE_URL}/rest/v1/products?select=supplier_id",
                    headers=Config.SUPABASE_HEADERS,
                    timeout=10
                )
                
                product_counts = {}
                if prod_response.status_code == 200:
                    products = prod_response.json()
                    for p in products:
                        sid = p.get('supplier_id')
                        if sid:
                            product_counts[sid] = product_counts.get(sid, 0) + 1
                
                for s in suppliers:
                    s['total_products'] = product_counts.get(s.get('supplier_id'), 0)
                
                supplier_summary = {
                    'total_suppliers': total_supp,
                    'active_suppliers': active_supp,
                    'total_products': sum(product_counts.values())
                }
                print(f"✅ Loaded {total_supp} suppliers")
            else:
                print(f"⚠️ Suppliers fetch error: {response.status_code}")
        except Exception as e:
            print(f"❌ Error loading supplier data: {e}")

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
            DB_CONNECTED=True,
            # ✅ CREDIT DATA
            credit_summary=credit_summary,
            credit_customers=credit_customers,
            overdue_count=overdue_count,
            # ✅ SUPPLIER DATA
            supplier_summary=supplier_summary,
            suppliers=suppliers,
            low_stock_count=low_stock_count
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
            DB_CONNECTED=False,
            # ✅ CREDIT DATA (empty)
            credit_summary={'total_customers': 0, 'active_customers': 0, 'total_balance': 0, 'total_purchases': 0, 'total_payments': 0},
            credit_customers=[],
            overdue_count=0,
            # ✅ SUPPLIER DATA (empty)
            supplier_summary={'total_suppliers': 0, 'active_suppliers': 0, 'total_products': 0},
            suppliers=[],
            low_stock_count=0
        )


# ============================================================
# SUPPLIER MANAGEMENT ROUTES
# ============================================================

@admin_bp.route('/admin/suppliers')
@admin_required
def admin_suppliers():
    """Supplier management page"""
    try:
        from utils.supplier import get_all_suppliers, get_low_stock_products, get_supplier_summary
        
        suppliers = get_all_suppliers()
        low_stock = get_low_stock_products()
        summary = get_supplier_summary()
        
        stats = {
            'total_orders': 0,
            'pending_orders': 0,
            'total_products': summary.get('total_products', 0),
            'total_customers': 0,
            'today_revenue': 0,
            'month_revenue': 0,
            'total_revenue': 0,
            'low_stock': len(low_stock),
            'total_bundles': 0,
            'total_cart_items': 0,
            'pos_orders': 0,
            'web_orders': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'online'
        }
        
        return render_template('admin_suppliers.html',
            suppliers=suppliers,
            low_stock=low_stock,
            low_stock_count=len(low_stock),
            summary=summary,
            stats=stats,
            DB_CONNECTED=True,
            IS_VERCEL=IS_VERCEL
        )
    except Exception as e:
        print(f"❌ Error loading suppliers: {e}")
        flash('Error loading suppliers', 'danger')
        
        stats = {
            'total_orders': 0,
            'pending_orders': 0,
            'total_products': 0,
            'total_customers': 0,
            'today_revenue': 0,
            'month_revenue': 0,
            'total_revenue': 0,
            'low_stock': 0,
            'total_bundles': 0,
            'total_cart_items': 0,
            'pos_orders': 0,
            'web_orders': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'offline'
        }
        
        return render_template('admin_suppliers.html',
            suppliers=[],
            low_stock=[],
            low_stock_count=0,
            summary={'total_suppliers': 0, 'active_suppliers': 0, 'inactive_suppliers': 0, 'total_products': 0},
            stats=stats,
            DB_CONNECTED=False,
            IS_VERCEL=IS_VERCEL
        )


@admin_bp.route('/admin/api/suppliers', methods=['GET'])
@admin_required
def api_get_suppliers():
    """Get all suppliers - API endpoint"""
    try:
        from utils.supplier import get_all_suppliers
        suppliers = get_all_suppliers()
        return jsonify({'success': True, 'suppliers': suppliers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/suppliers', methods=['POST'])
@admin_required
def api_add_supplier():
    """Add a new supplier - API endpoint"""
    try:
        from utils.supplier import add_supplier
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        required = ['business_name', 'phone']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        result = add_supplier(data)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/suppliers/<supplier_id>', methods=['GET'])
@admin_required
def api_get_supplier(supplier_id):
    """Get a specific supplier - API endpoint"""
    try:
        from utils.supplier import get_supplier_by_id
        
        supplier = get_supplier_by_id(supplier_id)
        if supplier:
            return jsonify({'success': True, 'supplier': supplier})
        else:
            return jsonify({'success': False, 'message': 'Supplier not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/suppliers/<supplier_id>', methods=['PUT'])
@admin_required
def api_update_supplier(supplier_id):
    """Update a supplier - API endpoint"""
    try:
        from utils.supplier import update_supplier
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        result = update_supplier(supplier_id, data)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/suppliers/<supplier_id>', methods=['DELETE'])
@admin_required
def api_delete_supplier(supplier_id):
    """Delete a supplier - API endpoint"""
    try:
        from utils.supplier import delete_supplier
        
        result = delete_supplier(supplier_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/suppliers/low-stock', methods=['GET'])
@admin_required
def api_get_low_stock():
    """Get products with low stock - API endpoint"""
    try:
        from utils.supplier import get_low_stock_products
        
        supplier_id = request.args.get('supplier_id')
        low_stock = get_low_stock_products(supplier_id)
        return jsonify({'success': True, 'low_stock': low_stock, 'count': len(low_stock)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/suppliers/summary', methods=['GET'])
@admin_required
def api_get_supplier_summary():
    """Get supplier summary statistics - API endpoint"""
    try:
        from utils.supplier import get_supplier_summary
        
        summary = get_supplier_summary()
        return jsonify({'success': True, 'summary': summary})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# CREDIT CUSTOMER MANAGEMENT ROUTES
# ============================================================

@admin_bp.route('/admin/credit')
@admin_required
def admin_credit():
    """Credit management page"""
    try:
        from utils.credit import get_all_credit_customers, get_credit_summary, get_overdue_customers
        from datetime import datetime
        
        customers = get_all_credit_customers()
        summary = get_credit_summary()
        overdue = get_overdue_customers()
        
        stats = {
            'total_orders': 0,
            'pending_orders': 0,
            'total_products': 0,
            'total_customers': summary.get('total_customers', 0),
            'today_revenue': 0,
            'month_revenue': 0,
            'total_revenue': 0,
            'low_stock': 0,
            'total_bundles': 0,
            'total_cart_items': 0,
            'pos_orders': 0,
            'web_orders': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'online'
        }
        
        return render_template('admin_credit.html',
            customers=customers,
            summary=summary,
            overdue=overdue,
            overdue_count=len(overdue),
            stats=stats,
            DB_CONNECTED=True,
            IS_VERCEL=IS_VERCEL,
            now=datetime.utcnow()
        )
    except Exception as e:
        print(f"❌ Error loading credit customers: {e}")
        flash('Error loading credit customers', 'danger')
        
        stats = {
            'total_orders': 0,
            'pending_orders': 0,
            'total_products': 0,
            'total_customers': 0,
            'today_revenue': 0,
            'month_revenue': 0,
            'total_revenue': 0,
            'low_stock': 0,
            'total_bundles': 0,
            'total_cart_items': 0,
            'pos_orders': 0,
            'web_orders': 0,
            'today_growth_pct': 0,
            'month_growth_pct': 0,
            'db_mode': 'offline'
        }
        
        return render_template('admin_credit.html',
            customers=[],
            summary={'total_customers': 0, 'active_customers': 0, 'inactive_customers': 0, 
                    'total_balance': 0, 'total_credit_limit': 0, 'total_purchases': 0, 
                    'total_payments': 0, 'average_balance': 0},
            overdue=[],
            overdue_count=0,
            stats=stats,
            DB_CONNECTED=False,
            IS_VERCEL=IS_VERCEL,
            now=datetime.utcnow()
        )


@admin_bp.route('/admin/api/credit/customers', methods=['GET'])
@admin_required
def api_get_credit_customers():
    """Get all credit customers - API endpoint"""
    try:
        from utils.credit import get_all_credit_customers
        customers = get_all_credit_customers()
        return jsonify({'success': True, 'customers': customers})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/customers', methods=['POST'])
@admin_required
def api_add_credit_customer():
    """Add a new credit customer - API endpoint"""
    try:
        from utils.credit import add_credit_customer
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        required = ['full_name', 'phone']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        result = add_credit_customer(data)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/customers/<customer_id>', methods=['GET'])
@admin_required
def api_get_credit_customer(customer_id):
    """Get a specific credit customer - API endpoint"""
    try:
        from utils.credit import get_credit_customer_by_id
        
        customer = get_credit_customer_by_id(customer_id)
        if customer:
            return jsonify({'success': True, 'customer': customer})
        else:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/customers/<customer_id>', methods=['PUT'])
@admin_required
def api_update_credit_customer(customer_id):
    """Update a credit customer - API endpoint"""
    try:
        from utils.credit import update_credit_customer
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        result = update_credit_customer(customer_id, data)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/customers/<customer_id>', methods=['DELETE'])
@admin_required
def api_delete_credit_customer(customer_id):
    """Delete a credit customer - API endpoint"""
    try:
        from utils.credit import delete_credit_customer
        
        result = delete_credit_customer(customer_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/balance/<customer_id>', methods=['GET'])
@admin_required
def api_get_credit_balance(customer_id):
    """Get customer balance - API endpoint"""
    try:
        from utils.credit import get_customer_balance
        
        balance = get_customer_balance(customer_id)
        if balance:
            return jsonify({'success': True, 'balance': balance})
        else:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/transactions/<customer_id>', methods=['GET'])
@admin_required
def api_get_credit_transactions(customer_id):
    """Get customer transactions - API endpoint"""
    try:
        from utils.credit import get_customer_transactions
        
        transactions = get_customer_transactions(customer_id)
        return jsonify({'success': True, 'transactions': transactions})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/purchase', methods=['POST'])
@admin_required
def api_record_credit_purchase():
    """Record a credit purchase - API endpoint"""
    try:
        from utils.credit import record_credit_purchase
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        required = ['customer_id', 'items', 'total_amount', 'staff_name']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        result = record_credit_purchase(
            customer_id=data['customer_id'],
            items=data['items'],
            total_amount=float(data['total_amount']),
            staff_name=data['staff_name'],
            notes=data.get('notes', '')
        )
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/payment', methods=['POST'])
@admin_required
def api_record_credit_payment():
    """Record a credit payment - API endpoint"""
    try:
        from utils.credit import record_credit_payment
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        required = ['customer_id', 'amount', 'staff_name']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        result = record_credit_payment(
            customer_id=data['customer_id'],
            amount=float(data['amount']),
            staff_name=data['staff_name'],
            notes=data.get('notes', '')
        )
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/monthly-report', methods=['GET'])
@admin_required
def api_get_monthly_credit_report():
    """Get monthly credit report - API endpoint"""
    try:
        from utils.credit import get_monthly_credit_report
        
        year = request.args.get('year', type=int)
        report = get_monthly_credit_report(year)
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/overdue', methods=['GET'])
@admin_required
def api_get_overdue_customers():
    """Get overdue customers - API endpoint"""
    try:
        from utils.credit import get_overdue_customers
        
        overdue = get_overdue_customers()
        return jsonify({'success': True, 'overdue': overdue, 'count': len(overdue)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/credit/summary', methods=['GET'])
@admin_required
def api_get_credit_summary():
    """Get credit summary statistics - API endpoint"""
    try:
        from utils.credit import get_credit_summary
        
        summary = get_credit_summary()
        return jsonify({'success': True, 'summary': summary})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# POS ROUTE - FIXED
# ============================================================

@admin_bp.route('/admin/pos')
def admin_pos():
    # ✅ Check for either admin_logged_in OR user session
    if not session.get('admin_logged_in') and not session.get('user'):
        flash('Please login first', 'danger')
        return redirect(url_for('admin.user_login'))
    
    # ✅ Set admin_logged_in for POS if user exists
    if session.get('user') and not session.get('admin_logged_in'):
        session['admin_logged_in'] = True
        print("✅ admin_logged_in set for POS user")

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
# POS ORDER ROUTE - FIXED
# ============================================================

@admin_bp.route('/admin/pos/place-order', methods=['POST'])
def admin_pos_place_order():
    # ✅ FIX: Check for either admin_logged_in OR user session
    if not session.get('admin_logged_in') and not session.get('user'):
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    # ✅ If user session exists but no admin_logged_in, set it
    if session.get('user') and not session.get('admin_logged_in'):
        session['admin_logged_in'] = True
        print("✅ admin_logged_in set for POS order")

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
        print(f"👤 User: {user_name} ({user_role})")
        
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
# SYNC QUEUED ORDERS
# ============================================================

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
        synced = 0
        failed = 0

        for order in orders_to_sync:
            try:
                order_id = order.get('order_id', f'OFF-{uuid.uuid4().hex[:8].upper()}')
                
                check_response = requests.get(
                    f"{Config.SUPABASE_URL}/rest/v1/orders?order_id=eq.{order_id}",
                    headers=Config.SUPABASE_HEADERS,
                    timeout=10
                )

                if check_response.status_code == 200 and check_response.json():
                    synced += 1
                    continue

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
                    'customer': order.get('customer', {
                        'name': order.get('customer_name', 'Walk-in Customer'),
                        'email': order.get('customer_email', 'walkin@example.com'),
                        'phone': order.get('customer_phone', 'N/A'),
                        'address': order.get('customer_address', 'In-store purchase')
                    }),
                    'user_id': order.get('user_id', 'unknown'),
                    'user_name': order.get('user_name', 'Unknown User'),
                    'user_role': order.get('user_role', 'user'),
                    'staff_name': order.get('staff_name', order.get('user_name', 'Unknown User'))
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
                    synced += 1
                else:
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
            'message': f"Synced {synced} items, {failed} failed"
        })

    except Exception as e:
        print(f"❌ Sync queue error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


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
# API ROUTES
# ============================================================

@admin_bp.route('/admin/api/analytics')
def admin_api_analytics():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    orders = load_orders()
    analytics = calculate_analytics_from_orders(orders)
    return jsonify(analytics)


@admin_bp.route('/admin/api/revenue')
def admin_api_revenue():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        orders = load_orders()
        now = datetime.utcnow()
        today = now.date()
        first_day_this_month = today.replace(day=1)

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

        today_revenue = 0
        today_orders = 0
        yesterday_revenue = 0
        month_revenue = 0
        month_orders = 0
        last_month_revenue = 0

        for order in orders:
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

        total_revenue = sum(order.get('total', 0) for order in orders if order.get('status') != 'cancelled')

        return jsonify({
            "total_revenue": total_revenue,
            "total_cost": 0,
            "total_profit": 0,
            "total_orders": len(orders),
            "total_items_sold": 0,
            "today_revenue": today_revenue,
            "today_orders": today_orders,
            "yesterday_revenue": yesterday_revenue,
            "month_revenue": month_revenue,
            "month_orders": month_orders,
            "last_month_revenue": last_month_revenue,
            "today_growth_pct": today_growth,
            "month_growth_pct": month_growth
        })

    except Exception as exc:
        print(f'❌ Revenue API error: {exc}')
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


# ============================================================
# CALCULATE ANALYTICS
# ============================================================

def calculate_analytics_from_orders(orders):
    if not orders:
        return {
            'total_revenue': 0,
            'total_cost': 0,
            'total_profit': 0,
            'total_orders': 0,
            'total_items_sold': 0,
            'pos_orders_count': 0,
            'web_orders_count': 0,
            'product_sales': {},
            'category_sales': {},
            'monthly_data': {}
        }

    products = load_products()
    product_lookup = {str(p.get('id')): p for p in products if p and p.get('id')}

    total_revenue = 0
    total_cost = 0
    total_profit = 0
    total_items_sold = 0
    pos_orders_count = 0
    web_orders_count = 0
    product_sales = {}
    category_sales = {}
    monthly_data = {}

    for order in orders:
        if order.get('status') == 'cancelled':
            continue

        if order.get('source') == 'pos':
            pos_orders_count += 1
        else:
            web_orders_count += 1

        created_at = order.get('created_at', '')
        month_key = 'Unknown'
        if created_at:
            try:
                if isinstance(created_at, str):
                    if 'T' in created_at:
                        clean = created_at.replace('Z', '').replace('+00:00', '')
                        if '.' in clean:
                            dt = datetime.fromisoformat(clean)
                        else:
                            dt = datetime.strptime(clean[:10], '%Y-%m-%d')
                    elif ' ' in created_at:
                        dt = datetime.strptime(created_at[:10], '%Y-%m-%d')
                    else:
                        dt = datetime.strptime(created_at[:10], '%Y-%m-%d')
                elif isinstance(created_at, datetime):
                    dt = created_at
                else:
                    dt = datetime.utcnow()
                month_key = dt.strftime('%b %Y')
            except:
                month_key = 'Unknown'

        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'orders': 0,
                'items': 0,
                'revenue': 0,
                'cost': 0,
                'profit': 0,
                'margin': 0
            }
        monthly_data[month_key]['orders'] += 1

        order_total = 0
        order_cost = 0
        order_items = 0

        for item in order.get('items', []):
            quantity = item.get('quantity', 1)
            price = float(item.get('price', 0) or 0)
            total_items_sold += quantity
            order_items += quantity

            item_total = price * quantity
            order_total += item_total
            total_revenue += item_total

            cost_price = 0

            if 'cost_price' in item:
                try:
                    cost_price = float(item.get('cost_price', 0) or 0)
                except (ValueError, TypeError):
                    cost_price = 0

            if cost_price == 0:
                product_id = item.get('product_id', '')
                if product_id:
                    product = product_lookup.get(product_id, {})
                    if product:
                        cost_price = float(product.get('cost_price', 0) or 0)

            if cost_price == 0 and price > 0:
                cost_price = price * 0.7

            item_cost = cost_price * quantity
            order_cost += item_cost
            total_cost += item_cost
            total_profit += (item_total - item_cost)

            product_id = item.get('product_id', '')
            category = 'Uncategorized'
            if product_id:
                product = product_lookup.get(product_id, {})
                if product and product.get('category'):
                    category = product.get('category')

            product_name = item.get('name', 'Unknown Product')
            if product_name not in product_sales:
                product_sales[product_name] = {
                    'quantity': 0,
                    'revenue': 0,
                    'cost': 0,
                    'profit': 0,
                    'margin': 0
                }
            product_sales[product_name]['quantity'] += quantity
            product_sales[product_name]['revenue'] += item_total
            product_sales[product_name]['cost'] += item_cost
            product_sales[product_name]['profit'] += (item_total - item_cost)

            if category not in category_sales:
                category_sales[category] = {
                    'quantity': 0,
                    'revenue': 0,
                    'cost': 0,
                    'profit': 0,
                    'margin': 0
                }
            category_sales[category]['quantity'] += quantity
            category_sales[category]['revenue'] += item_total
            category_sales[category]['cost'] += item_cost
            category_sales[category]['profit'] += (item_total - item_cost)

        monthly_data[month_key]['items'] += order_items
        monthly_data[month_key]['revenue'] += order_total
        monthly_data[month_key]['cost'] += order_cost
        monthly_data[month_key]['profit'] += (order_total - order_cost)

    for product in product_sales.values():
        if product['revenue'] > 0:
            product['margin'] = round((product['profit'] / product['revenue']) * 100, 1)

    for category in category_sales.values():
        if category['revenue'] > 0:
            category['margin'] = round((category['profit'] / category['revenue']) * 100, 1)

    for month in monthly_data.values():
        if month['revenue'] > 0:
            month['margin'] = round((month['profit'] / month['revenue']) * 100, 1)

    sorted_products = sorted(
        product_sales.items(),
        key=lambda x: x[1]['profit'],
        reverse=True
    )
    product_sales = dict(sorted_products)

    return {
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'total_orders': len(orders),
        'total_items_sold': total_items_sold,
        'pos_orders_count': pos_orders_count,
        'web_orders_count': web_orders_count,
        'product_sales': product_sales,
        'category_sales': category_sales,
        'monthly_data': monthly_data
    }


# ============================================================
# AJAX PAGINATION API ENDPOINTS
# ============================================================

@admin_bp.route('/admin/api/products', methods=['GET'])
@admin_required
def api_products_paginated():
    """Get paginated products for AJAX"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        all_products = load_products()
        
        total = len(all_products)
        start = (page - 1) * per_page
        end = start + per_page
        products = all_products[start:end]
        
        return jsonify({
            'success': True,
            'products': products,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'start': start + 1 if products else 0,
            'end': min(end, total)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/orders', methods=['GET'])
@admin_required
def api_orders_paginated():
    """Get paginated orders for AJAX"""
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


@admin_bp.route('/admin/api/customers', methods=['GET'])
@admin_required
def api_customers_paginated():
    """Get paginated customers for AJAX"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        all_orders = load_orders()
        
        customer_dict = {}
        for order in all_orders:
            if order.get('status') == 'cancelled':
                continue
                
            name = order.get('customer_name')
            if not name:
                customer = order.get('customer', {})
                if isinstance(customer, dict):
                    name = customer.get('name')
                elif isinstance(customer, str):
                    try:
                        name = json.loads(customer).get('name')
                    except:
                        pass
            
            if not name or name in ['Walk-in Customer', 'Web Customer', 'Customer', 'Unknown', '']:
                continue
            
            if name not in customer_dict:
                customer_dict[name] = {
                    'name': name,
                    'email': order.get('customer_email', 'N/A'),
                    'phone': order.get('customer_phone', 'N/A'),
                    'orders': 0,
                    'total_spent': 0
                }
            customer_dict[name]['orders'] += 1
            customer_dict[name]['total_spent'] += order.get('total', 0)
        
        customers = list(customer_dict.values())
        customers.sort(key=lambda x: x['orders'], reverse=True)
        
        total = len(customers)
        start = (page - 1) * per_page
        end = start + per_page
        paginated = customers[start:end]
        
        return jsonify({
            'success': True,
            'customers': paginated,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'start': start + 1 if paginated else 0,
            'end': min(end, total)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/order/<order_id>', methods=['GET'])
@admin_required
def api_get_order_details(order_id):
    """Get single order details for modal"""
    try:
        all_orders = load_orders()
        
        for order in all_orders:
            if str(order.get('order_id')) == str(order_id):
                items = order.get('items', [])
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except:
                        items = []
                
                customer = order.get('customer', {})
                if isinstance(customer, str):
                    try:
                        customer = json.loads(customer)
                    except:
                        customer = {}
                
                return jsonify({
                    'success': True,
                    'order': {
                        'order_id': order.get('order_id'),
                        'items': items,
                        'subtotal': order.get('subtotal', 0),
                        'shipping': order.get('shipping', 0),
                        'total': order.get('total', 0),
                        'status': order.get('status', 'pending'),
                        'source': order.get('source', 'web'),
                        'created_at': order.get('created_at', ''),
                        'customer_name': order.get('customer_name', 'Customer'),
                        'customer_email': order.get('customer_email', ''),
                        'customer_phone': order.get('customer_phone', ''),
                        'customer_address': order.get('customer_address', ''),
                        'customer': customer
                    }
                })
        
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/product/<product_id>', methods=['GET'])
@admin_required
def api_get_product_details(product_id):
    """Get single product details for editing"""
    try:
        all_products = load_products()
        
        for product in all_products:
            if str(product.get('id')) == str(product_id):
                return jsonify({'success': True, 'product': product})
        
        return jsonify({'success': False, 'error': 'Product not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/admin/api/product/<product_id>', methods=['PUT'])
@admin_required
def api_update_product(product_id):
    """Update a product"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        try:
            requests.get(
                f"{Config.SUPABASE_URL}/rest/v1/",
                headers=Config.SUPABASE_HEADERS,
                timeout=3
            )
        except:
            return jsonify({
                'success': False, 
                'message': 'You are offline. Please connect to the internet to update products.',
                'offline': True
            }), 503
        
        response = requests.patch(
            f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
            headers=Config.SUPABASE_HEADERS,
            json=data,
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            import utils.data
            utils.data.products_cache = []
            return jsonify({'success': True, 'message': 'Product updated successfully'})
        else:
            return jsonify({'success': False, 'message': f'Failed to update: {response.status_code}'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False, 
            'message': 'You are offline. Please connect to the internet to update products.',
            'offline': True
        }), 503
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/admin/api/product/<product_id>', methods=['DELETE'])
@admin_required
def api_delete_product(product_id):
    """Delete a product"""
    try:
        try:
            requests.get(
                f"{Config.SUPABASE_URL}/rest/v1/",
                headers=Config.SUPABASE_HEADERS,
                timeout=3
            )
        except:
            return jsonify({
                'success': False, 
                'message': 'You are offline. Please connect to the internet to delete products.',
                'offline': True
            }), 503
        
        response = requests.delete(
            f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
            headers=Config.SUPABASE_HEADERS,
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            import utils.data
            utils.data.products_cache = []
            return jsonify({'success': True, 'message': 'Product deleted successfully'})
        else:
            return jsonify({'success': False, 'message': f'Failed to delete: {response.status_code}'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False, 
            'message': 'You are offline. Please connect to the internet to delete products.',
            'offline': True
        }), 503
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# API ROUTES - LEGACY SUPPORT
# ============================================================

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

        total_products = len(products)

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


# ============================================================
# PRODUCT MANAGEMENT - LEGACY
# ============================================================

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
