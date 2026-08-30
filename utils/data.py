import json
import traceback
import uuid
from datetime import datetime, timedelta

import requests
from flask import session

from config import Config
from utils.storage import load_json_data, save_json_data

products_cache = []
orders_cache = []


def has_internet():
    """Check if we can reach Supabase"""
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/",
            headers=Config.SUPABASE_HEADERS,
            timeout=3
        )
        return response.status_code < 500
    except Exception as e:
        print(f"Internet check failed: {e}")
        return False


# ============================================================
# ⚠️ SAMPLE PRODUCTS - NEVER USED ANYMORE
# Kept only for reference, but NEVER called
# ============================================================

def get_sample_products():
    """⚠️ DEPRECATED - NEVER USED - Kept for reference only"""
    return []


# ============================================================
# LOAD ORDERS - WITH OFFLINE SUPPORT
# ============================================================

def load_orders():
    """Load orders - try Supabase first, fallback to local for offline"""
    global orders_cache
    
    # Force refresh - clear cache
    orders_cache = []
    
    # First, try to load from local cache (for offline)
    json_data = load_json_data()
    local_orders = json_data.get('orders', [])
    
    try:
        print("🔄 Attempting to load orders from Supabase...")
        
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/orders?select=*&order=created_at.desc",
            headers=Config.SUPABASE_HEADERS,
            timeout=10,
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Successfully loaded {len(data)} orders from Supabase")
            
            if isinstance(data, list):
                processed_orders = []
                for order in data:
                    if isinstance(order.get('customer'), dict):
                        pass
                    elif isinstance(order.get('customer'), str):
                        try:
                            order['customer'] = json.loads(order['customer'])
                        except:
                            order['customer'] = {}
                    elif isinstance(order.get('customer'), list):
                        order['customer'] = order['customer'][0] if order['customer'] else {}
                    else:
                        order['customer'] = {}
                    
                    if not order['customer']:
                        order['customer'] = {
                            'name': order.get('customer_name', 'Customer'),
                            'email': order.get('customer_email', 'N/A'),
                            'phone': order.get('customer_phone', 'N/A'),
                            'address': order.get('customer_address', 'N/A')
                        }
                    
                    if isinstance(order.get('items'), str):
                        try:
                            order['items'] = json.loads(order['items'])
                        except:
                            order['items'] = []
                    elif not isinstance(order.get('items'), list):
                        order['items'] = []
                    
                    for field in ['total', 'subtotal', 'shipping']:
                        if field in order:
                            try:
                                order[field] = float(order[field] or 0)
                            except:
                                order[field] = 0
                    
                    if 'order_id' in order:
                        order['order_id'] = str(order['order_id'])
                    
                    processed_orders.append(order)
                
                orders_cache = processed_orders
                
                # Update local cache with latest orders
                try:
                    json_data['orders'] = processed_orders
                    save_json_data(json_data)
                except Exception as e:
                    print(f"⚠️ Could not update local cache: {e}")
                
                return processed_orders
            else:
                print(f"⚠️ Response is not a list: {type(data)}")
        else:
            print(f"⚠️ Failed to load from Supabase: {response.status_code}")
            print(f"Response: {response.text[:200]}")
        
        # If we get here, Supabase failed - use local cache
        print(f"📂 Using local cache: {len(local_orders)} orders")
        orders_cache = local_orders
        return local_orders
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error loading orders: {e}")
        print(f"📂 Using local cache: {len(local_orders)} orders (offline mode)")
        orders_cache = local_orders
        return local_orders
    except Exception as exc:
        print(f'❌ Error loading orders: {exc}')
        traceback.print_exc()
        print(f"📂 Using local cache: {len(local_orders)} orders (fallback)")
        orders_cache = local_orders
        return local_orders


# ============================================================
# LOAD PRODUCTS - ONLY FROM SUPABASE, NEVER SAMPLES
# ============================================================

def load_products():
    """Load products - ONLY from Supabase, NEVER use samples"""
    global products_cache
    
    # Clear cache to force fresh load
    products_cache = []
    
    try:
        print("🔄 Loading products from Supabase...")
        
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/products?select=*&order=name.asc",
            headers=Config.SUPABASE_HEADERS,
            timeout=10,
        )
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                # Ensure required fields exist
                for product in data:
                    if 'barcode' not in product:
                        product['barcode'] = ''
                    if 'cost_price' not in product:
                        product['cost_price'] = 0
                    if 'image' not in product:
                        product['image'] = ''
                    if 'description' not in product:
                        product['description'] = ''
                
                products_cache = data
                print(f"✅ Loaded {len(data)} products from Supabase")
                return data
            else:
                print(f"⚠️ Response is not a list: {type(data)}")
        else:
            print(f"⚠️ Failed to load from Supabase: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
    except Exception as exc:
        print(f'❌ Error loading products: {exc}')
        traceback.print_exc()
    
    # ⚠️ CRITICAL: Return EMPTY list - NEVER use sample products
    # This ensures ONLY database products are shown
    print("⚠️ Returning EMPTY list - no products loaded (database unavailable)")
    return []


# ============================================================
# SAVE ORDER - WITH OFFLINE SUPPORT
# ============================================================

def save_order_to_supabase(order_data):
    """Save order - try Supabase, fallback to local for offline"""
    try:
        print(f"💾 Saving order: {order_data.get('order_id')}")
        
        # Always save locally first
        json_data = load_json_data()
        json_data.setdefault('orders', [])
        
        existing_order = None
        for order in json_data['orders']:
            if order.get('order_id') == order_data.get('order_id'):
                existing_order = order
                break
        
        if existing_order:
            for key, value in order_data.items():
                existing_order[key] = value
        else:
            json_data['orders'].append(order_data)
        
        save_json_data(json_data)
        
        # Clear cache so orders reload fresh
        global orders_cache
        orders_cache = []
        
        # Try to save to Supabase
        try:
            supabase_order = {
                'order_id': order_data.get('order_id'),
                'items': order_data.get('items', []),
                'subtotal': float(order_data.get('subtotal', 0)),
                'shipping': float(order_data.get('shipping', 0)),
                'total': float(order_data.get('total', 0)),
                'status': order_data.get('status', 'pending'),
                'source': order_data.get('source', 'web'),
                'created_at': order_data.get('created_at', datetime.utcnow().isoformat()),
                'customer': order_data.get('customer', {}),
                'customer_name': order_data.get('customer_name', ''),
                'customer_email': order_data.get('customer_email', ''),
                'customer_phone': order_data.get('customer_phone', ''),
                'customer_address': order_data.get('customer_address', '')
            }
            
            response = requests.post(
                f"{Config.SUPABASE_URL}/rest/v1/orders",
                headers=Config.SUPABASE_HEADERS,
                json=supabase_order,
                timeout=10,
            )
            
            if response.status_code in [200, 201, 204]:
                print(f"✅ Order saved to Supabase: {order_data.get('order_id')}")
                # Mark as synced
                json_data = load_json_data()
                for order in json_data.get('orders', []):
                    if order.get('order_id') == order_data.get('order_id'):
                        order['synced'] = True
                        order['synced_at'] = datetime.utcnow().isoformat()
                save_json_data(json_data)
                return {'success': True, 'synced': True, 'queued': False, 'message': 'Order saved successfully.'}
            else:
                print(f"⚠️ Supabase save failed: {response.status_code}")
                # Queue for later sync
                queue = json_data.get('order_queue', [])
                if order_data.get('order_id') not in [q.get('order_id') for q in queue]:
                    queue.append({**order_data, 'queued_at': datetime.utcnow().isoformat()})
                    json_data['order_queue'] = queue
                    save_json_data(json_data)
                return {'success': True, 'synced': False, 'queued': True, 'message': 'Order saved locally. Will sync when internet returns.'}
                
        except Exception as e:
            print(f"❌ Error saving to Supabase: {e}")
            # Queue for later sync
            queue = json_data.get('order_queue', [])
            if order_data.get('order_id') not in [q.get('order_id') for q in queue]:
                queue.append({**order_data, 'queued_at': datetime.utcnow().isoformat()})
                json_data['order_queue'] = queue
                save_json_data(json_data)
            return {'success': True, 'synced': False, 'queued': True, 'message': 'Order saved locally. Will sync when internet returns.'}
        
    except Exception as exc:
        print(f'Error saving order: {exc}')
        traceback.print_exc()
        return {'success': False, 'synced': False, 'queued': False, 'message': str(exc)}


# ============================================================
# SYNC QUEUED ORDERS
# ============================================================

def sync_queued_orders():
    """Sync queued orders when internet is back"""
    try:
        if not has_internet():
            print("⚠️ No internet, cannot sync orders")
            return False
        
        print("🔄 Syncing queued orders...")
        json_data = load_json_data()
        queue = json_data.get('order_queue', [])
        if not queue:
            print("✅ No orders to sync")
            return True
        
        synced = []
        for order in queue:
            try:
                supabase_order = {
                    'order_id': order.get('order_id'),
                    'items': order.get('items', []),
                    'subtotal': float(order.get('subtotal', 0)),
                    'shipping': float(order.get('shipping', 0)),
                    'total': float(order.get('total', 0)),
                    'status': order.get('status', 'pending'),
                    'source': order.get('source', 'web'),
                    'created_at': order.get('created_at', datetime.utcnow().isoformat()),
                    'customer': order.get('customer', {}),
                    'customer_name': order.get('customer_name', ''),
                    'customer_email': order.get('customer_email', ''),
                    'customer_phone': order.get('customer_phone', ''),
                    'customer_address': order.get('customer_address', '')
                }
                
                response = requests.post(
                    f"{Config.SUPABASE_URL}/rest/v1/orders",
                    headers=Config.SUPABASE_HEADERS,
                    json=supabase_order,
                    timeout=10,
                )
                if response.status_code in [200, 201, 204]:
                    synced.append(order.get('order_id'))
                    print(f"✅ Synced order: {order.get('order_id')}")
                else:
                    print(f"⚠️ Failed to sync order: {order.get('order_id')} - {response.status_code}")
            except Exception as exc:
                print(f'Failed to sync order: {exc}')
        
        if synced:
            json_data['order_queue'] = [o for o in queue if o.get('order_id') not in synced]
            save_json_data(json_data)
            global orders_cache
            orders_cache = []
        
        return True
    except Exception as exc:
        print(f'Queue sync error: {exc}')
        return False


def sync_pending_data_if_possible():
    """Sync pending data if internet is available"""
    if has_internet():
        return sync_queued_orders()
    return False


# ============================================================
# REST OF YOUR FUNCTIONS (keep everything else the same)
# ============================================================

def load_bundles():
    try:
        if has_internet():
            response = requests.get(
                f"{Config.SUPABASE_URL}/rest/v1/bundles?select=*",
                headers=Config.SUPABASE_HEADERS,
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
        return []
    except Exception:
        return []


def sync_products_from_supabase():
    return load_products()


def update_product_stock(product_id, new_stock):
    """Update product stock in Supabase"""
    try:
        print(f"🔄 Updating stock for product {product_id} to {new_stock}")
        
        response = requests.patch(
            f"{Config.SUPABASE_URL}/rest/v1/products?id=eq.{product_id}",
            headers=Config.SUPABASE_HEADERS,
            json={'stock': new_stock},
            timeout=5,
        )
        
        if response.status_code in [200, 204]:
            print(f"✅ Stock updated for {product_id}")
            global products_cache
            products_cache = []
            return True
        else:
            print(f"❌ Error updating stock: {response.status_code}")
            return False
    except Exception as exc:
        print(f'Error updating stock: {exc}')
        return False


def get_cart():
    try:
        cart = session.get('cart', {})
        if isinstance(cart, list):
            new_cart = {}
            for item_id in cart:
                new_cart[item_id] = new_cart.get(item_id, 0) + 1
            session['cart'] = new_cart
            session.modified = True
            return new_cart
        if not isinstance(cart, dict):
            session['cart'] = {}
            session.modified = True
            return {}
        return cart
    except Exception as exc:
        print(f'Error getting cart: {exc}')
        return {}


def get_sales_analytics():
    """Get sales analytics with proper revenue and profit calculation"""
    try:
        orders = load_orders()
        products = load_products()
        
        if not orders:
            return {
                'total_revenue': 0,
                'total_cost': 0,
                'total_profit': 0,
                'total_orders': 0,
                'total_items_sold': 0,
                'pos_orders_count': 0,
                'web_orders_count': 0,
                'total_customers': 0,
                'monthly_data': {},
                'product_sales': {},
                'category_sales': {},
                'customer_data': {}
            }

        product_lookup = {str(p.get('id')): p for p in products if p and p.get('id')}

        total_revenue = 0
        total_cost = 0
        total_profit = 0
        total_orders = len(orders)
        total_items_sold = 0
        pos_orders_count = 0
        web_orders_count = 0
        customer_data = {}
        monthly_data = {}
        product_sales = {}
        category_sales = {}

        for order in orders:
            if order.get('status') == 'cancelled':
                continue
                
            customer = order.get('customer', {})
            if isinstance(customer, str):
                try:
                    customer = json.loads(customer)
                except Exception:
                    customer = {}
            if isinstance(customer, list):
                customer = customer[0] if customer else {}
            if not isinstance(customer, dict):
                customer = {}

            items = order.get('items', [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception:
                    items = []
            if not isinstance(items, list):
                items = []

            source = order.get('source', 'web')
            if source == 'pos':
                pos_orders_count += 1
            else:
                web_orders_count += 1

            customer_name = customer.get('name', 'Unknown') if isinstance(customer, dict) else 'Unknown'
            if customer_name != 'Unknown' and customer_name not in customer_data:
                customer_data[customer_name] = {
                    'name': customer_name,
                    'email': customer.get('email', ''),
                    'phone': customer.get('phone', ''),
                    'orders': 0,
                    'total_spent': 0,
                }
            if customer_name in customer_data:
                customer_data[customer_name]['orders'] += 1
                customer_data[customer_name]['total_spent'] += float(order.get('total', 0) or 0)

            created_at = order.get('created_at') or order.get('createdAt') or order.get('date') or datetime.utcnow().isoformat()
            try:
                created_dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
            except Exception:
                created_dt = datetime.utcnow()
            month_key = created_dt.strftime('%b %Y')
            month_entry = monthly_data.setdefault(month_key, {
                'orders': 0,
                'items': 0,
                'revenue': 0.0,
                'cost': 0.0,
                'profit': 0.0,
            })
            month_entry['orders'] += 1

            order_total = float(order.get('total', 0) or 0)
            order_cost = 0.0
            order_items_count = 0

            for item in items:
                product_id = str(item.get('product_id', item.get('id', '')))
                quantity = int(item.get('quantity', 1) or 1)
                price = float(item.get('price', 0) or 0)
                item_total = float(item.get('total', price * quantity) or 0)
                
                cost_price = 0
                
                if 'cost_price' in item:
                    try:
                        cost_price = float(item.get('cost_price', 0) or 0)
                    except (ValueError, TypeError):
                        cost_price = 0
                
                if cost_price == 0 and product_id:
                    product = product_lookup.get(product_id, {})
                    if product and 'cost_price' in product:
                        try:
                            cost_price = float(product.get('cost_price', 0) or 0)
                        except (ValueError, TypeError):
                            cost_price = 0
                
                if cost_price == 0 and price > 0:
                    cost_price = price * 0.7
                
                if cost_price is None or cost_price == '' or cost_price != cost_price:
                    cost_price = 0
                
                item_cost = cost_price * quantity
                order_cost += item_cost
                order_items_count += quantity
                total_revenue += item_total
                total_cost += item_cost
                total_profit += (item_total - item_cost)
                total_items_sold += quantity

                product_name = product_lookup.get(product_id, {}).get('name') or item.get('name') or f'Product {product_id}'
                sale_entry = product_sales.setdefault(product_name, {
                    'product_id': product_id,
                    'quantity': 0,
                    'revenue': 0.0,
                    'cost': 0.0,
                    'profit': 0.0,
                })
                sale_entry['quantity'] += quantity
                sale_entry['revenue'] += item_total
                sale_entry['cost'] += item_cost
                sale_entry['profit'] += (item_total - item_cost)

                category_name = product_lookup.get(product_id, {}).get('category') or item.get('category') or 'Uncategorized'
                category_entry = category_sales.setdefault(category_name, {
                    'quantity': 0,
                    'revenue': 0.0,
                    'cost': 0.0,
                    'profit': 0.0,
                })
                category_entry['quantity'] += quantity
                category_entry['revenue'] += item_total
                category_entry['cost'] += item_cost
                category_entry['profit'] += (item_total - item_cost)

            month_entry['items'] += order_items_count
            month_entry['revenue'] += order_total
            month_entry['cost'] += order_cost
            month_entry['profit'] += (order_total - order_cost)

        sorted_product_sales = dict(sorted(product_sales.items(), key=lambda item: item[1].get('profit', 0), reverse=True))
        sorted_category_sales = dict(sorted(category_sales.items(), key=lambda item: item[1].get('revenue', 0), reverse=True))

        return {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_profit': total_profit,
            'total_orders': total_orders,
            'total_items_sold': total_items_sold,
            'pos_orders_count': pos_orders_count,
            'web_orders_count': web_orders_count,
            'total_customers': len(customer_data),
            'monthly_data': monthly_data,
            'product_sales': sorted_product_sales,
            'all_product_sales': sorted_product_sales,
            'category_sales': sorted_category_sales,
            'customer_data': customer_data,
        }
    except Exception as exc:
        print(f'Error in analytics: {exc}')
        traceback.print_exc()
        return {
            'total_revenue': 0,
            'total_cost': 0,
            'total_profit': 0,
            'total_orders': 0,
            'total_items_sold': 0,
            'pos_orders_count': 0,
            'web_orders_count': 0,
            'total_customers': 0,
            'monthly_data': {},
            'product_sales': {},
            'customer_data': {},
        }


def get_category_icon(category):
    icons = {
        'Phones': 'fa-mobile-screen',
        'Laptops': 'fa-laptop',
        'Accessories': 'fa-headphones',
        'Wearables': 'fa-watch',
        'Audio': 'fa-music',
        'Televisions': 'fa-tv',
        'Gaming': 'fa-gamepad',
        'Tablets': 'fa-tablet',
        'Smart Home': 'fa-home'
    }
    return icons.get(category, 'fa-box')


def get_all_categories():
    return {
        'Phones': 'fa-mobile-screen',
        'Laptops': 'fa-laptop',
        'Accessories': 'fa-headphones',
        'Wearables': 'fa-watch',
        'Audio': 'fa-music',
        'Televisions': 'fa-tv',
        'Gaming': 'fa-gamepad',
        'Tablets': 'fa-tablet',
        'Smart Home': 'fa-home'
    }
