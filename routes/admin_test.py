import os
import json
import traceback
import requests
from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for, flash
from functools import wraps
from config import Config
from utils.data import load_products, load_orders

admin_test_bp = Blueprint('admin_test', __name__)

# ============================================================
# AUTH
# ============================================================

def is_admin():
    return session.get('admin_logged_in', False)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash('Admin access required', 'danger')
            return redirect(url_for('admin_test.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_test_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if email == 'admin@pricepoint.com' and password == 'electronics2026':
            session['admin_logged_in'] = True
            session['user'] = {'email': email, 'name': 'Admin', 'role': 'admin'}
            flash('Welcome Admin!', 'success')
            return redirect('/admin-test')
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin_login.html')

@admin_test_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('admin_test.login'))

# ============================================================
# TEST ROUTES
# ============================================================

@admin_test_bp.route('/test')
def test():
    """Test if Flask is working"""
    return jsonify({
        'status': '✅ Flask is working!',
        'vercel': os.environ.get('VERCEL') == '1',
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY)
    })

@admin_test_bp.route('/test-supabase')
def test_supabase():
    """Test Supabase connection"""
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

@admin_test_bp.route('/')
@admin_required
def dashboard():
    """Simple dashboard"""
    try:
        products = load_products()
        orders = load_orders()
        
        return jsonify({
            'status': '✅ Dashboard working!',
            'products_count': len(products),
            'orders_count': len(orders),
            'sample_product': products[0] if products else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
