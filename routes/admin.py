# ============================================================
# MINIMAL TEST ROUTES - ADD TO YOUR EXISTING admin.py
# ============================================================

@admin_bp.route('/minimal/test-supabase')
def minimal_test_supabase():
    """Test Supabase connection - Minimal version"""
    import requests
    import os
    
    result = {
        'vercel': os.environ.get('VERCEL') == '1',
        'supabase_url': Config.SUPABASE_URL,
        'has_key': bool(Config.SUPABASE_KEY),
        'key_preview': Config.SUPABASE_KEY[:20] + '...' if Config.SUPABASE_KEY else 'None',
        'headers': {
            'apikey': 'present' if Config.SUPABASE_KEY else 'missing',
            'authorization': 'present' if Config.SUPABASE_KEY else 'missing'
        }
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


@admin_bp.route('/minimal')
@admin_required
def minimal_dashboard():
    """Minimal dashboard for testing - uses same template"""
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
        
        # ============================================================
        # CLEAN PRODUCTS
        # ============================================================
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
