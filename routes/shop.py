import traceback
from datetime import datetime
import json
import requests

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from config import Config
from utils.data import (
    get_all_categories,
    get_cart,
    get_category_icon,
    get_sample_products,
    load_bundles,
    load_products,
    save_order_to_supabase,
    update_product_stock,
)

shop_bp = Blueprint('shop', __name__)


# ============================================================
# CATEGORY ICONS - FULL LIST FOR GENERAL STORE
# ============================================================
CATEGORY_ICONS = {
    'All': 'fa-th-large',
    'Beverages': 'fa-wine-bottle',
    'Snacks': 'fa-utensils',
    'Groceries': 'fa-apple-alt',
    'Food': 'fa-apple-alt',
    'Electronics': 'fa-laptop',
    'Phones': 'fa-mobile-alt',
    'Phone Accessories': 'fa-plug',
    'Laptops': 'fa-laptop',
    'Computers': 'fa-desktop',
    'Audio': 'fa-headphones',
    'Headphones': 'fa-headphones',
    'Fashion': 'fa-tshirt',
    'Clothing': 'fa-tshirt',
    "Men's Fashion": 'fa-user-tie',
    "Women's Fashion": 'fa-female',
    'Shoes': 'fa-shoe-prints',
    'Accessories': 'fa-plug',
    'Bags': 'fa-bag-shopping',
    'Watches': 'fa-clock',
    'Jewelry': 'fa-ring',
    'Sunglasses': 'fa-glasses',
    'Home & Kitchen': 'fa-utensils',
    'Furniture': 'fa-couch',
    'Home Decor': 'fa-home',
    'Kitchen': 'fa-kitchen-set',
    'Bedding': 'fa-bed',
    'Bath': 'fa-bath',
    'Cleaning': 'fa-spray-can-sparkles',
    'Laundry': 'fa-shirt',
    'Beauty': 'fa-spa',
    'Personal Care': 'fa-spa',
    'Skincare': 'fa-spa',
    'Makeup': 'fa-paint-brush',
    'Fragrance': 'fa-perfume',
    'Books': 'fa-book',
    'Stationery': 'fa-pen',
    'School Supplies': 'fa-book-open',
    'Office Supplies': 'fa-briefcase',
    'Toys': 'fa-gamepad',
    'Games': 'fa-gamepad',
    'Gaming': 'fa-gamepad',
    'Sports': 'fa-dumbbell',
    'Fitness': 'fa-dumbbell',
    'Outdoor': 'fa-tree',
    'Garden': 'fa-tree',
    'Automotive': 'fa-car',
    'Car Accessories': 'fa-car',
    'Health': 'fa-heartbeat',
    'Wellness': 'fa-heartbeat',
    'Baby': 'fa-baby',
    'Kids': 'fa-baby',
    'Pet': 'fa-paw',
    'Pet Supplies': 'fa-paw',
    'Music': 'fa-music',
    'Instruments': 'fa-guitar',
    'Cameras': 'fa-camera',
    'Photography': 'fa-camera',
    'Printers': 'fa-print',
    'Networking': 'fa-network-wired',
    'Software': 'fa-code',
    'Gifts': 'fa-gift',
    'Flowers': 'fa-seedling',
    'Crafts': 'fa-paintbrush',
    'Hobbies': 'fa-puzzle-piece',
    'Party': 'fa-party-horn',
    'Uncategorized': 'fa-tag',
    'Other': 'fa-tag',
}

def get_category_icon(category):
    """Get Font Awesome icon for a category"""
    return CATEGORY_ICONS.get(category, 'fa-tag')


# ============================================================
# HELPER: CLEAN PRODUCTS - Fix None values for Vercel
# ============================================================
def clean_products(products):
    """Clean products to ensure no None values"""
    if not products:
        return []
    
    cleaned = []
    for p in products:
        if not p:
            continue
        clean = dict(p)
        if clean.get('stock') is None:
            clean['stock'] = 0
        if clean.get('price') is None:
            clean['price'] = 0
        if clean.get('name') is None:
            clean['name'] = 'Unnamed Product'
        if clean.get('category') is None:
            clean['category'] = 'Uncategorized'
        if clean.get('image') is None:
            clean['image'] = ''
        if clean.get('description') is None:
            clean['description'] = ''
        if clean.get('badge') is None:
            clean['badge'] = ''
        if clean.get('cost_price') is None:
            clean['cost_price'] = 0
        if clean.get('rating') is None:
            clean['rating'] = 4.0
        if clean.get('reviews') is None:
            clean['reviews'] = 0
        if clean.get('barcode') is None:
            clean['barcode'] = ''
        cleaned.append(clean)
    return cleaned


# ============================================================
# BUILD CATEGORIES WITH COUNTS
# ============================================================
def build_categories(products_list):
    """Build categories dictionary with counts and icons"""
    categories = {}
    for product in products_list:
        if not product:
            continue
        cat = product.get('category', 'Uncategorized')
        if cat not in categories:
            categories[cat] = {
                'name': cat,
                'icon': get_category_icon(cat),
                'count': 0,
            }
        categories[cat]['count'] += 1
    
    sorted_categories = dict(sorted(categories.items(), key=lambda x: x[0].lower()))
    return sorted_categories


@shop_bp.route('/')
def index():
    products_list = load_products()
    products_list = clean_products(products_list)
    bundles_list = load_bundles()

    products_dict = {}
    for product in products_list:
        if product and 'id' in product:
            products_dict[str(product['id'])] = product

    bundles_dict = {}
    for bundle in bundles_list:
        if bundle and 'id' in bundle:
            bundles_dict[str(bundle['id'])] = bundle

    best_sellers = [p for p in products_list if p.get('badge') == 'Best Seller']
    new_arrivals = [p for p in products_list if p.get('badge') == 'New']
    trending = [p for p in products_list if p.get('badge') == 'Trending']

    categories = build_categories(products_list)

    all_categories = {
        'All': {
            'name': 'All',
            'icon': 'fa-th-large',
            'count': len(products_list)
        }
    }
    all_categories.update(categories)

    return render_template(
        'shop.html',
        products=products_dict,
        all_products=products_dict,
        bundles=bundles_dict,
        best_sellers=best_sellers,
        new_arrivals=new_arrivals,
        trending=trending,
        categories=all_categories,
        CATEGORIES=get_all_categories(),
    )


@shop_bp.route('/category/<category_name>')
def category_page(category_name):
    products = load_products()
    products = clean_products(products)
    
    products_dict = {}
    for product in products:
        if product and 'id' in product and product.get('category') == category_name:
            products_dict[str(product['id'])] = product
    
    categories = build_categories(products)
    all_categories = {
        'All': {
            'name': 'All',
            'icon': 'fa-th-large',
            'count': len(products)
        }
    }
    all_categories.update(categories)
    
    return render_template(
        'category.html', 
        products=products_dict, 
        category_name=category_name, 
        categories=all_categories,
        CATEGORIES=get_all_categories()
    )


@shop_bp.route('/product/<product_id>')
def product_detail(product_id):
    products = load_products()
    products = clean_products(products)
    
    product = None
    for candidate in products:
        if str(candidate.get('id')) == str(product_id):
            product = candidate
            break

    if not product:
        flash('Product not found', 'danger')
        return redirect(url_for('shop.index'))

    related = [p for p in products if p.get('category') == product.get('category') and str(p.get('id')) != product_id][:4]
    related_dict = {}
    for item in related:
        if item and 'id' in item:
            related_dict[str(item['id'])] = item

    return render_template('product.html', product=product, related=related_dict)


# ============================================================
# ✅ FIXED: CART PAGE - NO HARDCODED 800
# ============================================================
@shop_bp.route('/cart')
def cart_page():
    try:
        cart = get_cart()
        cart_items = []
        subtotal = 0
        total_items = 0
        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()

        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
            if product:
                item_total = product.get('price', 0) * quantity
                cart_items.append({
                    'id': item_id,
                    'name': product.get('name', 'Product'),
                    'price': product.get('price', 0),
                    'image': product.get('image', ''),
                    'type': 'product',
                    'quantity': quantity,
                    'item_total': item_total,
                    'stock': product.get('stock', 0),
                    'description': product.get('description', ''),
                    'specs': product.get('specs', []),
                })
                subtotal += item_total
                total_items += quantity
                continue

            for bundle in bundles:
                if str(bundle.get('id')) == str(item_id):
                    item_total = bundle.get('price', 0) * quantity
                    cart_items.append({
                        'id': item_id,
                        'name': bundle.get('name', 'Bundle'),
                        'price': bundle.get('price', 0),
                        'image': bundle.get('image', ''),
                        'type': 'bundle',
                        'quantity': quantity,
                        'item_total': item_total,
                        'products': bundle.get('products', []),
                    })
                    subtotal += item_total
                    total_items += quantity
                    break

        return render_template('cart.html', 
            cart_items=cart_items, 
            subtotal=subtotal, 
            total_items=total_items
        )
    except Exception as exc:
        print(f'Cart error: {exc}')
        flash('Error loading cart', 'danger')
        return redirect(url_for('shop.index'))


@shop_bp.route('/add-to-cart/<item_id>', methods=['POST'])
def add_to_cart(item_id):
    try:
        cart = get_cart()
        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()

        product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
        if product:
            current_qty = cart.get(item_id, 0)
            if current_qty >= product.get('stock', 0):
                return jsonify({'success': False, 'message': 'Not enough stock available!'})

        bundle_exists = any(str(b.get('id')) == str(item_id) for b in bundles)
        if not product and not bundle_exists:
            return jsonify({'success': False, 'message': 'Item not found'})

        cart[item_id] = cart.get(item_id, 0) + 1
        session['cart'] = cart
        session.modified = True
        total_items = sum(cart.values())
        return jsonify({'success': True, 'message': 'Added to cart!', 'count': total_items, 'quantity': cart[item_id]})
    except Exception as exc:
        print(f'Error adding to cart: {exc}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(exc)}'}), 500


# ============================================================
# ✅ FIXED: UPDATE CART - NO HARDCODED 800
# ============================================================
@shop_bp.route('/update-cart/<item_id>/<action>', methods=['POST'])
def update_cart_item(item_id, action):
    try:
        cart = get_cart()
        products = load_products()
        products = clean_products(products)

        if action == 'increase':
            product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
            if product:
                current = cart.get(item_id, 0)
                if current >= product.get('stock', 0):
                    return jsonify({'success': False, 'message': 'Not enough stock available!'})
            cart[item_id] = cart.get(item_id, 0) + 1
        elif action == 'decrease':
            if item_id in cart:
                if cart[item_id] <= 1:
                    del cart[item_id]
                else:
                    cart[item_id] -= 1
            else:
                return jsonify({'success': False, 'message': 'Item not in cart'})
        elif action == 'remove':
            if item_id in cart:
                del cart[item_id]
            else:
                return jsonify({'success': False, 'message': 'Item not in cart'})
        else:
            return jsonify({'success': False, 'message': 'Invalid action'})

        session['cart'] = cart
        session.modified = True

        subtotal = 0
        bundles = load_bundles()
        for iid, qty in cart.items():
            for product in products:
                if str(product.get('id')) == str(iid):
                    subtotal += product.get('price', 0) * qty
                    break
            else:
                for bundle in bundles:
                    if str(bundle.get('id')) == str(iid):
                        subtotal += bundle.get('price', 0) * qty
                        break

        item_price = 0
        for product in products:
            if str(product.get('id')) == str(item_id):
                item_price = product.get('price', 0)
                break
        else:
            for bundle in bundles:
                if str(bundle.get('id')) == str(item_id):
                    item_price = bundle.get('price', 0)
                    break

        return jsonify({
            'success': True,
            'quantity': cart.get(item_id, 0),
            'subtotal': subtotal,
            'total_items': sum(cart.values()),
            'item_total': item_price * cart.get(item_id, 0),
        })
    except Exception as exc:
        print(f'Error updating cart: {exc}')
        return jsonify({'success': False, 'message': str(exc)}), 500


@shop_bp.route('/remove-from-cart/<item_id>', methods=['POST'])
def remove_from_cart(item_id):
    try:
        cart = get_cart()
        if item_id in cart:
            del cart[item_id]
            session['cart'] = cart
            session.modified = True
            return jsonify({'success': True, 'message': 'Removed from cart!', 'count': sum(cart.values())})
        return jsonify({'success': False, 'message': 'Item not in cart'})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc)}), 500


# ============================================================
# ✅ FIXED: CHECKOUT PAGE - PASSES SUBTOTAL TO FRONTEND
# ============================================================
@shop_bp.route('/checkout')
def checkout_page():
    try:
        cart = get_cart()
        if not cart:
            flash('Your cart is empty', 'warning')
            return redirect(url_for('shop.index'))

        cart_items = []
        subtotal = 0
        total_items = 0
        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()

        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            product = next((p for p in products if str(p.get('id')) == str(item_id)), None)
            if product:
                item_total = product.get('price', 0) * quantity
                cart_items.append({
                    'id': item_id,
                    'name': product.get('name', 'Product'),
                    'price': product.get('price', 0),
                    'image': product.get('image', ''),
                    'type': 'product',
                    'quantity': quantity,
                    'item_total': item_total,
                    'description': product.get('description', ''),
                    'specs': product.get('specs', []),
                })
                subtotal += item_total
                total_items += quantity
                continue

            for bundle in bundles:
                if str(bundle.get('id')) == str(item_id):
                    item_total = bundle.get('price', 0) * quantity
                    cart_items.append({
                        'id': item_id,
                        'name': bundle.get('name', 'Bundle'),
                        'price': bundle.get('price', 0),
                        'image': bundle.get('image', ''),
                        'type': 'bundle',
                        'quantity': quantity,
                        'item_total': item_total,
                    })
                    subtotal += item_total
                    total_items += quantity
                    break

        return render_template('checkout.html', 
            cart_items=cart_items, 
            subtotal=subtotal, 
            total_items=total_items
        )
    except Exception as exc:
        print(f'Checkout error: {exc}')
        flash('Error loading checkout', 'danger')
        return redirect(url_for('shop.index'))


# ============================================================
# ✅ COMPLETELY FIXED: PLACE ORDER - RECEIVES SHIPPING FROM FRONTEND
# ============================================================
@shop_bp.route('/place-order', methods=['POST'])
def place_order():
    try:
        cart = get_cart()
        if not cart:
            return jsonify({'success': False, 'message': 'Cart is empty'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400

        print("=" * 60)
        print("📦 PLACE ORDER REQUEST")
        print(f"📋 Data received: {data}")
        print("=" * 60)

        # ===== GET CUSTOMER DATA =====
        customer_name = data.get('customer_name') or data.get('name') or 'Web Customer'
        customer_email = data.get('customer_email') or data.get('email') or 'web@example.com'
        customer_phone = data.get('customer_phone') or data.get('phone') or 'N/A'
        customer_address = data.get('customer_address') or data.get('address') or 'Online Order'

        # ✅ Get shipping from frontend (calculated by geolocation)
        shipping = data.get('shipping', 0)
        shipping_distance = data.get('shipping_distance', 0)
        total = data.get('total', 0)
        subtotal = data.get('subtotal', 0)

        # If subtotal not sent, calculate from cart
        if subtotal == 0:
            products = load_products()
            products = clean_products(products)
            bundles = load_bundles()
            for item_id, quantity in cart.items():
                for product in products:
                    if str(product.get('id')) == str(item_id):
                        subtotal += product.get('price', 0) * quantity
                        break
                else:
                    for bundle in bundles:
                        if str(bundle.get('id')) == str(item_id):
                            subtotal += bundle.get('price', 0) * quantity
                            break

        # Calculate total if not provided
        if total == 0:
            total = subtotal + shipping

        print(f"👤 Customer: {customer_name}")
        print(f"📧 Email: {customer_email}")
        print(f"📱 Phone: {customer_phone}")
        print(f"📍 Address: {customer_address}")
        print(f"📦 Subtotal: {subtotal}")
        print(f"🚚 Shipping: {shipping}")
        print(f"💰 Total: {total}")
        print("=" * 60)

        # ===== BUILD ORDER ITEMS =====
        products = load_products()
        products = clean_products(products)
        bundles = load_bundles()
        order_items = []

        for item_id, quantity in cart.items():
            if quantity <= 0:
                continue
            item_found = False
            for product in products:
                if str(product.get('id')) == str(item_id):
                    current_stock = product.get('stock', 0)
                    if current_stock < quantity:
                        return jsonify({
                            'success': False, 
                            'message': f'Not enough stock for {product.get("name")}. Available: {current_stock}'
                        }), 400
                    item_total = product.get('price', 0) * quantity
                    order_items.append({
                        'product_id': str(item_id),
                        'name': product.get('name', 'Product'),
                        'price': float(product.get('price', 0)),
                        'quantity': int(quantity),
                        'total': float(item_total),
                        'type': 'product',
                    })
                    item_found = True
                    new_stock = max(0, current_stock - quantity)
                    update_product_stock(item_id, new_stock)
                    break

            if not item_found:
                for bundle in bundles:
                    if str(bundle.get('id')) == str(item_id):
                        item_total = bundle.get('price', 0) * quantity
                        order_items.append({
                            'product_id': str(item_id),
                            'name': bundle.get('name', 'Bundle'),
                            'price': float(bundle.get('price', 0)),
                            'quantity': int(quantity),
                            'total': float(item_total),
                            'type': 'bundle',
                        })
                        break

        if not order_items:
            return jsonify({'success': False, 'message': 'No valid items in cart'}), 400

        # Generate order ID if not provided
        order_id = data.get('order_id') or f'ELEC-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'

        # ============================================================
        # ✅ PROPER SUPABASE FORMAT - ALL FIELDS CLEAN
        # ============================================================
        order_data = {
            'order_id': str(order_id),
            'items': order_items,
            'subtotal': float(subtotal),
            'shipping': float(shipping),
            'total': float(total),
            'status': str(data.get('status', 'pending')),
            'source': str(data.get('source', 'web')),
            'created_at': datetime.utcnow().isoformat(),
            'customer_name': str(customer_name),
            'customer_email': str(customer_email),
            'customer_phone': str(customer_phone),
            'customer_address': str(customer_address),
            'customer': {
                'name': str(customer_name),
                'email': str(customer_email),
                'phone': str(customer_phone),
                'address': str(customer_address),
            },
            'shipping_distance': float(shipping_distance) if shipping_distance else 0,
            'estimated_delivery': str(data.get('estimated_delivery', '')),
            'delivery_notes': str(data.get('delivery_notes', '')),
        }

        # Add location data if present
        if data.get('location'):
            order_data['location'] = data.get('location')

        print(f"🔥 SAVING ORDER: {order_id}")
        print(f"📦 Order data: {json.dumps(order_data, indent=2, default=str)}")

        # ============================================================
        # ✅ SAVE TO SUPABASE
        # ============================================================
        try:
            # Try inserting directly with proper headers
            response = requests.post(
                f"{Config.SUPABASE_URL}/rest/v1/orders",
                headers={
                    **Config.SUPABASE_HEADERS,
                    'Content-Type': 'application/json',
                    'Prefer': 'return=representation'
                },
                json=order_data,
                timeout=15,
            )

            print(f"📥 Supabase response status: {response.status_code}")
            print(f"📥 Supabase response body: {response.text[:500]}")  # Truncate for readability

            if response.status_code in [200, 201, 204]:
                print(f"✅ Order saved: {order_id}")
                session['cart'] = {}
                session.modified = True

                # Clear cache
                import utils.data
                utils.data.orders_cache = []

                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'total': total,
                    'message': 'Order placed successfully!',
                    'customer_name': customer_name,
                })
            else:
                print(f"❌ Supabase error: {response.status_code}")
                print(f"❌ Response: {response.text}")
                return jsonify({
                    'success': False,
                    'message': f'Database error: {response.status_code} - {response.text[:200]}'
                }), 500

        except requests.exceptions.Timeout:
            print("❌ Request timeout")
            return jsonify({
                'success': False,
                'message': 'Request timeout. Please try again.'
            }), 500
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {e}")
            return jsonify({
                'success': False,
                'message': f'Network error: {str(e)}'
            }), 500

    except Exception as exc:
        print(f'Error placing order: {exc}')
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(exc)}'}), 500


@shop_bp.route('/order-confirmation/<order_id>')
def order_confirmation(order_id):
    return render_template('confirmation.html', order_id=order_id)


@shop_bp.route('/clear-cart', methods=['POST'])
def clear_cart():
    session['cart'] = {}
    session.modified = True
    return jsonify({'success': True, 'message': 'Cart cleared'})


# ============================================================
# CATEGORY API
# ============================================================
@shop_bp.route('/api/categories')
def api_categories():
    products = load_products()
    products = clean_products(products)
    categories = build_categories(products)
    
    all_categories = {
        'All': {
            'name': 'All',
            'icon': 'fa-th-large',
            'count': len(products)
        }
    }
    all_categories.update(categories)
    
    return jsonify(all_categories)
