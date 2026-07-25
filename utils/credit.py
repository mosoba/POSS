import os
import json
import uuid
import requests
from datetime import datetime, timedelta
from config import Config

# ============================================================
# ENVIRONMENT DETECTION
# ============================================================
IS_VERCEL = os.environ.get('VERCEL') == '1' or os.environ.get('NOW_REGION') is not None
print(f"🏦 Credit module running on: {'Vercel' if IS_VERCEL else 'Localhost'}")

# ============================================================
# CREDIT CUSTOMER FUNCTIONS
# ============================================================

def generate_customer_id():
    """Generate a unique credit customer ID"""
    return f'CR-{uuid.uuid4().hex[:8].upper()}'

def generate_transaction_id():
    """Generate a unique transaction ID"""
    return f'TXN-{uuid.uuid4().hex[:8].upper()}'

def add_credit_customer(customer_data):
    """Add a new credit customer"""
    try:
        if not customer_data.get('customer_id'):
            customer_data['customer_id'] = generate_customer_id()
        
        customer_data['created_at'] = datetime.utcnow().isoformat()
        customer_data['updated_at'] = datetime.utcnow().isoformat()
        
        if not customer_data.get('account_status'):
            customer_data['account_status'] = 'active'
        if not customer_data.get('current_balance'):
            customer_data['current_balance'] = 0
        if not customer_data.get('credit_limit'):
            customer_data['credit_limit'] = 0
        if not customer_data.get('total_purchases'):
            customer_data['total_purchases'] = 0
        if not customer_data.get('total_payments'):
            customer_data['total_payments'] = 0
        
        clean_data = {k: v for k, v in customer_data.items() if v is not None}
        
        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers",
            headers=Config.SUPABASE_HEADERS,
            json=clean_data,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            return {
                'success': True,
                'message': 'Credit customer added successfully',
                'data': response.json() if response.json() else customer_data
            }
        else:
            print(f"❌ Failed to add credit customer: {response.status_code} - {response.text}")
            return {
                'success': False,
                'message': f'Failed to add customer: {response.status_code}',
                'error': response.text
            }
            
    except Exception as e:
        print(f"❌ Error adding credit customer: {e}")
        return {'success': False, 'message': str(e)}

def get_all_credit_customers():
    """Get all credit customers"""
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?select=*&order=created_at.desc",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            customers = response.json()
            for customer in customers:
                if customer.get('created_at'):
                    try:
                        customer['created_at'] = customer['created_at'][:10]
                    except:
                        pass
            return customers
        else:
            print(f"⚠️ Failed to get credit customers: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error getting credit customers: {e}")
        return []

def get_credit_customer_by_id(customer_id):
    """Get a specific credit customer by ID"""
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?customer_id=eq.{customer_id}&select=*",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            customers = response.json()
            return customers[0] if customers else None
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting credit customer: {e}")
        return None

def get_credit_customer_by_phone(phone):
    """Find a credit customer by phone number"""
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?phone=eq.{phone}&select=*",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            customers = response.json()
            return customers[0] if customers else None
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error finding customer by phone: {e}")
        return None

def get_credit_customer_by_db_id(db_id):
    """Get a credit customer by database ID (for transactions)"""
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?id=eq.{db_id}&select=*",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            customers = response.json()
            return customers[0] if customers else None
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting customer by DB ID: {e}")
        return None

def update_credit_customer(customer_id, update_data):
    """Update a credit customer"""
    try:
        update_data['updated_at'] = datetime.utcnow().isoformat()
        clean_data = {k: v for k, v in update_data.items() if v is not None}
        
        response = requests.patch(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?customer_id=eq.{customer_id}",
            headers=Config.SUPABASE_HEADERS,
            json=clean_data,
            timeout=30
        )
        
        if response.status_code in [200, 204]:
            return {
                'success': True,
                'message': 'Customer updated successfully'
            }
        else:
            return {
                'success': False,
                'message': f'Failed to update customer: {response.status_code}'
            }
            
    except Exception as e:
        print(f"❌ Error updating credit customer: {e}")
        return {'success': False, 'message': str(e)}

def delete_credit_customer(customer_id):
    """Soft delete a credit customer (set status to inactive)"""
    return update_credit_customer(customer_id, {'account_status': 'inactive'})

# ============================================================
# CREDIT TRANSACTION FUNCTIONS
# ============================================================

def record_credit_purchase(customer_id, items, total_amount, staff_name, notes=""):
    """Record a credit purchase transaction"""
    try:
        customer = get_credit_customer_by_id(customer_id)
        if not customer:
            return {'success': False, 'message': 'Customer not found'}
        
        current_balance = customer.get('current_balance', 0)
        current_total_purchases = customer.get('total_purchases', 0)
        
        # Check credit limit
        credit_limit = customer.get('credit_limit', 0)
        if credit_limit > 0 and (current_balance + total_amount) > credit_limit:
            return {
                'success': False, 
                'message': f'Credit limit exceeded. Limit: KSh {credit_limit:,.2f}, Available: KSh {(credit_limit - current_balance):,.2f}'
            }
        
        # Calculate due date
        payment_terms = customer.get('payment_terms', '30 days')
        days = int(payment_terms.split()[0]) if payment_terms.split()[0].isdigit() else 30
        due_date = (datetime.utcnow() + timedelta(days=days)).date()
        
        transaction_id = generate_transaction_id()
        db_id = customer.get('id')
        
        # Save transaction
        transaction_data = {
            'transaction_id': transaction_id,
            'customer_id': db_id,
            'transaction_type': 'purchase',
            'amount': total_amount,
            'balance_after': current_balance + total_amount,
            'due_date': due_date.isoformat(),
            'payment_status': 'pending',
            'order_ref': json.dumps(items) if isinstance(items, list) else items,
            'staff_name': staff_name,
            'notes': notes,
            'created_at': datetime.utcnow().isoformat()
        }
        
        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions",
            headers=Config.SUPABASE_HEADERS,
            json=transaction_data,
            timeout=30
        )
        
        if response.status_code not in [200, 201]:
            print(f"❌ Failed to save transaction: {response.status_code} - {response.text}")
            return {
                'success': False,
                'message': f'Failed to record transaction: {response.status_code}'
            }
        
        # Update customer
        new_balance = current_balance + total_amount
        new_total_purchases = current_total_purchases + total_amount
        
        update_data = {
            'current_balance': new_balance,
            'total_purchases': new_total_purchases,
            'last_purchase_date': datetime.utcnow().date().isoformat()
        }
        
        update_result = update_credit_customer(customer_id, update_data)
        
        if not update_result['success']:
            return {
                'success': False,
                'message': 'Transaction recorded but failed to update balance'
            }
        
        print(f"✅ Credit purchase: {customer_id} - KSh {total_amount} - Total Purchases: KSh {new_total_purchases}")
        
        return {
            'success': True,
            'message': f'Credit purchase recorded successfully. New balance: KSh {new_balance:,.2f}',
            'transaction_id': transaction_id,
            'balance_after': new_balance,
            'due_date': due_date.isoformat()
        }
        
    except Exception as e:
        print(f"❌ Error recording credit purchase: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': str(e)}

def record_credit_payment(customer_id, amount, staff_name, notes=""):
    """Record a credit payment from customer"""
    try:
        customer = get_credit_customer_by_id(customer_id)
        if not customer:
            return {'success': False, 'message': 'Customer not found'}
        
        current_balance = customer.get('current_balance', 0)
        current_total_payments = customer.get('total_payments', 0)
        
        if amount > current_balance:
            return {
                'success': False,
                'message': f'Payment amount exceeds balance. Balance: KSh {current_balance:,.2f}'
            }
        
        transaction_id = generate_transaction_id()
        db_id = customer.get('id')
        
        # Save transaction
        transaction_data = {
            'transaction_id': transaction_id,
            'customer_id': db_id,
            'transaction_type': 'payment',
            'amount': amount,
            'balance_after': current_balance - amount,
            'payment_status': 'paid',
            'staff_name': staff_name,
            'notes': notes,
            'created_at': datetime.utcnow().isoformat()
        }
        
        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions",
            headers=Config.SUPABASE_HEADERS,
            json=transaction_data,
            timeout=30
        )
        
        if response.status_code not in [200, 201]:
            print(f"❌ Failed to save payment: {response.status_code} - {response.text}")
            return {
                'success': False,
                'message': f'Failed to record payment: {response.status_code}'
            }
        
        # Update customer
        new_balance = current_balance - amount
        new_total_payments = current_total_payments + amount
        
        update_data = {
            'current_balance': new_balance,
            'total_payments': new_total_payments,
            'last_payment_date': datetime.utcnow().date().isoformat()
        }
        
        update_result = update_credit_customer(customer_id, update_data)
        
        if not update_result['success']:
            return {
                'success': False,
                'message': 'Payment recorded but failed to update balance'
            }
        
        print(f"✅ Credit payment: {customer_id} - KSh {amount} - Total Payments: KSh {new_total_payments}")
        
        return {
            'success': True,
            'message': f'Payment recorded successfully. New balance: KSh {new_balance:,.2f}',
            'transaction_id': transaction_id,
            'balance_after': new_balance
        }
        
    except Exception as e:
        print(f"❌ Error recording credit payment: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': str(e)}

def get_customer_transactions(customer_id):
    """Get all transactions for a customer"""
    try:
        customer = get_credit_customer_by_id(customer_id)
        if not customer:
            return []
        
        db_id = customer.get('id')
        
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?customer_id=eq.{db_id}&order=created_at.desc",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting transactions: {e}")
        return []

def get_customer_balance(customer_id):
    """Get current balance for a customer"""
    try:
        customer = get_credit_customer_by_id(customer_id)
        if customer:
            return {
                'customer_id': customer_id,
                'customer_name': customer.get('full_name'),
                'current_balance': customer.get('current_balance', 0),
                'credit_limit': customer.get('credit_limit', 0),
                'available_credit': customer.get('credit_limit', 0) - customer.get('current_balance', 0),
                'total_purchases': customer.get('total_purchases', 0),
                'total_payments': customer.get('total_payments', 0)
            }
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting balance: {e}")
        return None

# ============================================================
# CREDIT MONEY TRACKING FUNCTIONS
# ============================================================

def get_all_credit_transactions():
    """Get all credit transactions with customer names"""
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?select=*&order=created_at.desc",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            transactions = response.json()
            # Get customer names for each transaction
            for t in transactions:
                if t.get('customer_id'):
                    customer = get_credit_customer_by_db_id(t.get('customer_id'))
                    if customer:
                        t['customer_name'] = customer.get('full_name', 'Unknown')
                        t['customer_phone'] = customer.get('phone', '')
                    else:
                        t['customer_name'] = 'Unknown'
            return transactions
        else:
            print(f"⚠️ Failed to get transactions: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error getting all credit transactions: {e}")
        return []

def get_full_credit_summary():
    """Get full credit summary with money tracking"""
    try:
        customers = get_all_credit_customers()
        
        total_credit_sales = 0
        total_payments_received = 0
        current_outstanding = 0
        overdue_balance = 0
        overdue_count = 0
        
        for c in customers:
            total_credit_sales += c.get('total_purchases', 0)
            total_payments_received += c.get('total_payments', 0)
            current_outstanding += c.get('current_balance', 0)
            
            # Check if overdue
            if c.get('account_status') == 'active' and c.get('current_balance', 0) > 0:
                txs = get_customer_transactions(c.get('customer_id'))
                if txs and txs[0].get('due_date'):
                    due_date = datetime.fromisoformat(txs[0]['due_date']).date()
                    if due_date < datetime.utcnow().date():
                        overdue_balance += c.get('current_balance', 0)
                        overdue_count += 1
        
        # Also calculate from transactions as backup
        transactions = get_all_credit_transactions()
        tx_sales = 0
        tx_payments = 0
        for tx in transactions:
            tx_type = tx.get('transaction_type', '').lower().strip()
            tx_amount = float(tx.get('amount', 0))
            
            # 🔥 SIMPLE FIX: Only count as PAYMENT if explicitly 'payment'
            if tx_type == 'payment':
                tx_payments += tx_amount
            else:
                # Everything else is a purchase
                tx_sales += tx_amount
        
        # Use max values to catch any discrepancies
        if tx_sales > total_credit_sales:
            total_credit_sales = tx_sales
        if tx_payments > total_payments_received:
            total_payments_received = tx_payments
        
        collection_rate = round((total_payments_received / total_credit_sales * 100) if total_credit_sales > 0 else 0, 1)
        
        print(f"📊 Credit Summary Calculated:")
        print(f"   Total Credit Sales: KSh {total_credit_sales:,.2f}")
        print(f"   Total Payments Received: KSh {total_payments_received:,.2f}")
        print(f"   Current Outstanding: KSh {current_outstanding:,.2f}")
        print(f"   Overdue Balance: KSh {overdue_balance:,.2f}")
        print(f"   Collection Rate: {collection_rate}%")
        
        return {
            'total_credit_sales': total_credit_sales,
            'total_payments_received': total_payments_received,
            'current_outstanding': current_outstanding,
            'overdue_balance': overdue_balance,
            'overdue_count': overdue_count,
            'collection_rate': collection_rate,
            'total_customers': len(customers),
            'active_customers': len([c for c in customers if c.get('account_status') == 'active'])
        }
        
    except Exception as e:
        print(f"❌ Error getting full credit summary: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total_credit_sales': 0,
            'total_payments_received': 0,
            'current_outstanding': 0,
            'overdue_balance': 0,
            'overdue_count': 0,
            'collection_rate': 0,
            'total_customers': 0,
            'active_customers': 0
        }

def get_overdue_customers_with_details():
    """Get detailed overdue customer information"""
    try:
        customers = get_all_credit_customers()
        overdue_list = []
        
        for c in customers:
            if c.get('account_status') != 'active':
                continue
            if c.get('current_balance', 0) <= 0:
                continue
            
            txs = get_customer_transactions(c.get('customer_id'))
            if txs and txs[0].get('due_date'):
                due_date = datetime.fromisoformat(txs[0]['due_date']).date()
                days_overdue = (datetime.utcnow().date() - due_date).days
                
                if days_overdue > 0:
                    overdue_list.append({
                        'customer_id': c.get('customer_id'),
                        'full_name': c.get('full_name'),
                        'phone': c.get('phone'),
                        'balance': c.get('current_balance', 0),
                        'credit_limit': c.get('credit_limit', 0),
                        'due_date': due_date.isoformat(),
                        'days_overdue': days_overdue,
                        'last_payment_date': c.get('last_payment_date'),
                        'total_purchases': c.get('total_purchases', 0)
                    })
        
        overdue_list.sort(key=lambda x: x['days_overdue'], reverse=True)
        return overdue_list
        
    except Exception as e:
        print(f"❌ Error getting overdue customers: {e}")
        return []

# ============================================================
# FIXED MONTHLY CREDIT REPORT - SIMPLE FIX
# ============================================================

def get_monthly_credit_report(year=None):
    """Get monthly credit report using customer data"""
    try:
        if not year:
            year = datetime.utcnow().year
        
        # Get customers instead of transactions
        customers = get_all_credit_customers()
        
        print(f"📊 Using customer data for monthly report - {len(customers)} customers")
        
        # Group by month using customer created_at
        months = {}
        
        for c in customers:
            # Get the date from customer
            tx_date = None
            date_str = c.get('created_at', '')
            
            if date_str:
                try:
                    if ' ' in date_str:
                        clean_date = date_str.split(' ')[0]
                        tx_date = datetime.strptime(clean_date, '%Y-%m-%d')
                    elif 'T' in date_str:
                        clean_date = date_str.replace('Z', '').replace('+00:00', '')
                        tx_date = datetime.fromisoformat(clean_date[:19])
                    else:
                        tx_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
                except Exception as e:
                    print(f"⚠️ Date parse error for {date_str}: {e}")
                    tx_date = datetime.utcnow()
            
            if not tx_date:
                tx_date = datetime.utcnow()
            
            # Only include customers from the selected year
            if tx_date.year != year:
                continue
            
            # Create month key
            month_key = tx_date.strftime('%b %Y')
            
            # Initialize month if not exists
            if month_key not in months:
                months[month_key] = {
                    'month': month_key,
                    'total_credit_sales': 0,
                    'total_payments': 0,
                    'net_change': 0,
                    'transactions_count': 0
                }
            
            # Add customer totals to the month
            months[month_key]['total_credit_sales'] += c.get('total_purchases', 0)
            months[month_key]['total_payments'] += c.get('total_payments', 0)
            months[month_key]['transactions_count'] += 1
        
        # Convert to list and sort
        report = list(months.values())
        month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        report.sort(key=lambda x: month_order.index(x['month'].split()[0]) if x['month'].split()[0] in month_order else 99)
        
        # Calculate net change
        for r in report:
            r['net_change'] = r['total_credit_sales'] - r['total_payments']
        
        print(f"📊 Monthly report generated:")
        for r in report:
            print(f"  {r['month']}: Sales={r['total_credit_sales']}, Payments={r['total_payments']}")
        
        return report
        
    except Exception as e:
        print(f"❌ Error getting monthly credit report: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_credit_summary():
    """Get credit summary statistics - for backward compatibility"""
    try:
        customers = get_all_credit_customers()
        
        total_customers = len(customers)
        active_customers = len([c for c in customers if c.get('account_status') == 'active'])
        total_balance = sum(c.get('current_balance', 0) for c in customers)
        total_credit_limit = sum(c.get('credit_limit', 0) for c in customers)
        total_purchases = sum(c.get('total_purchases', 0) for c in customers)
        total_payments = sum(c.get('total_payments', 0) for c in customers)
        
        return {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'inactive_customers': total_customers - active_customers,
            'total_balance': total_balance,
            'total_credit_limit': total_credit_limit,
            'total_purchases': total_purchases,
            'total_payments': total_payments,
            'average_balance': total_balance / active_customers if active_customers > 0 else 0
        }
        
    except Exception as e:
        print(f"❌ Error getting credit summary: {e}")
        return {
            'total_customers': 0,
            'active_customers': 0,
            'inactive_customers': 0,
            'total_balance': 0,
            'total_credit_limit': 0,
            'total_purchases': 0,
            'total_payments': 0,
            'average_balance': 0
        }

def get_overdue_customers():
    """Get customers with overdue payments (for admin dashboard)"""
    return get_overdue_customers_with_details()

def fix_transaction_dates():
    """Fix transactions with missing or invalid created_at dates"""
    try:
        transactions = get_all_credit_transactions()
        fixed_count = 0
        
        for tx in transactions:
            if not tx.get('created_at'):
                # If no date, set to current date
                tx_id = tx.get('id')
                if tx_id:
                    response = requests.patch(
                        f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?id=eq.{tx_id}",
                        headers=Config.SUPABASE_HEADERS,
                        json={'created_at': datetime.utcnow().isoformat()},
                        timeout=30
                    )
                    if response.status_code in [200, 204]:
                        fixed_count += 1
                        print(f"✅ Fixed transaction {tx_id}")
        
        return {'success': True, 'fixed': fixed_count}
    except Exception as e:
        print(f"❌ Error fixing dates: {e}")
        return {'success': False, 'error': str(e)}

# ============================================================
# CREDIT ROUTES - FOR ADMIN DASHBOARD
# ============================================================

def get_credit_dashboard_data():
    """Get all data needed for credit dashboard"""
    try:
        summary = get_full_credit_summary()
        overdue = get_overdue_customers_with_details()
        customers = get_all_credit_customers()
        transactions = get_all_credit_transactions()
        monthly_report = get_monthly_credit_report()
        
        return {
            'summary': summary,
            'overdue': overdue,
            'customers': customers[:20],
            'recent_transactions': transactions[:20],
            'monthly_report': monthly_report,
            'total_transactions': len(transactions)
        }
        
    except Exception as e:
        print(f"❌ Error getting credit dashboard data: {e}")
        return {
            'summary': {
                'total_credit_sales': 0,
                'total_payments_received': 0,
                'current_outstanding': 0,
                'overdue_balance': 0,
                'overdue_count': 0,
                'collection_rate': 0,
                'total_customers': 0,
                'active_customers': 0
            },
            'overdue': [],
            'customers': [],
            'recent_transactions': [],
            'monthly_report': [],
            'total_transactions': 0
        }
