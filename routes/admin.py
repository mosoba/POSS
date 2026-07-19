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

# ============================================================
# AUTH FUNCTIONS
# ============================================================

def is_admin():
    user = session.get('user', {})
    return user.get('role') == 'admin' or session.get('admin_logged_in')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash('Admin access required', 'danger')
            return redirect(url_for('admin.user_login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# AUTH ROUTES
# ============================================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if email == 'admin@pricepoint.com' and password == 'electronics2026':
            session['admin_logged_in'] = True
            session['user'] = {'email': email, 'name': 'Admin', 'role': 'admin'}
            flash('Welcome Admin!', 'success')
            return redirect('/admin')
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin_login.html')


@admin_bp.route('/logout')
def user_logout():
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('admin.user_login'))


# ============================================================
# ============================================================
# TEST ROUTES - THESE MUST BE IN YOUR DEPLOYED CODE!
# ============================================================
# ============================================================

@admin_bp.route('/test')
def test():
    """Simple test to verify Flask is working on Vercel"""
    return jsonify({
        'status': '✅ Flask is working on Vercel!',
        'vercel': os.environ.get('VERCEL') == '1',
        'now_region': os.environ.get('NOW_REGION'),
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY),
        'key_preview': Config.SUPABASE_KEY[:20] + '...' if Config.SUPABASE_KEY else 'None'
    })


@admin_bp.route('/test-env')
def test_env():
    """Test environment variables"""
    return jsonify({
        'VERCEL': os.environ.get('VERCEL'),
        'NOW_REGION': os.environ.get('NOW_REGION'),
        'SUPABASE_URL_from_os': os.environ.get('SUPABASE_URL'),
        'SUPABASE_KEY_from_os': os.environ.get('SUPABASE_KEY')[:20] + '...' if os.environ.get('SUPABASE_KEY') else 'None',
        'SUPABASE_URL_from_config': Config.SUPABASE_URL,
        'SUPABASE_KEY_from_config': Config.SUPABASE_KEY[:20] + '...' if Config.SUPABASE_KEY else 'None',
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
    """Test data loading"""
    result = {}
    try:
        from utils.data import load_products, load_orders
        products = load_products()
        orders = load_orders()
        result['products'] = len(products)
        result['orders'] = len(orders)
        if products and len(products) > 0:
            result['sample_product'] = {
                'id': products[0].get('id'),
                'name': products[0].get('name'),
                'price': products[0].get('price'),
                'stock': products[0].get('stock')
            }
        result['success'] = True
    except Exception as e:
        result['error'] = str(e)
        result['traceback'] = traceback.format_exc()
        result['success'] = False
    return jsonify(result)


# ============================================================
# MINIMAL DASHBOARD
# ============================================================

@admin_bp.route('/')
@admin_required
def minimal_dashboard():
    try:
        products = load_products()
        orders = load_orders()
        
        # Clean products
        for p in products:
            if p.get('stock') is None:
                p['stock'] = 0
            if p.get('price') is None:
                p['price'] = 0
            if p.get('name') is None:
                p['name'] = 'Unnamed'
        
        stats = {
            'total_products': len(products),
            'total_orders': len(orders),
            'low_stock': len([p for p in products if p.get('stock', 0) < 10]),
            'total_revenue': sum(o.get('total', 0) for o in orders),
            'pending_orders': len([o for o in orders if o.get('status') == 'pending']),
        }
        
        return jsonify({
            'status': '✅ Dashboard is working!',
            'stats': stats,
            'sample_products': products[:3] if products else [],
            'sample_orders': orders[:3] if orders else [],
            'DB_CONNECTED': True
        })
        
    except Exception as e:
        return jsonify({
            'status': '❌ Error',
            'error': str(e),
            'traceback': traceback.format_exc()
        })


# ============================================================
# PWA ROUTES - PUBLIC
# ============================================================

@admin_bp.route('/offline.html')
def offline_page():
    try:
        return render_template('offline.html')
    except Exception:
        return "Offline page not found", 404


@admin_bp.route('/sw.js')
def service_worker():
    try:
        return send_from_directory('static', 'sw.js', mimetype='application/javascript')
    except Exception:
        return "Service Worker not found", 404


@admin_bp.route('/manifest.json')
def manifest():
    try:
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')
    except Exception:
        return "Manifest not found", 404


@admin_bp.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory('static/icons', 'favicon.ico', mimetype='image/x-icon')
    except Exception:
        return "", 204


@admin_bp.route('/static/<path:filename>')
def static_files(filename):
    try:
        return send_from_directory('static', filename)
    except Exception:
        return "File not found", 404
