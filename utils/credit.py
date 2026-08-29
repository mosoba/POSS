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
    return f'CR-{uuid.uuid4().hex[:8].upper()}'

def add_credit_customer(customer_data):
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
    try:
        customer_id = str(customer_id).strip()
        print(f"🔍 get_credit_customer_by_id searching for: '{customer_id}'")
        
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?customer_id=eq.{customer_id}&select=*",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            customers = response.json()
            if customers:
                customer = customers[0]
                print(f"✅ Found customer: {customer.get('full_name')}")
                return customer
            else:
                print(f"⚠️ No customer found with customer_id: {customer_id}")
        else:
            print(f"❌ API error: {response.status_code}")
        
        return None
            
    except Exception as e:
        print(f"❌ Error getting credit customer: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_credit_customer(customer_id, update_data):
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
            return {'success': True, 'message': 'Customer updated successfully'}
        else:
            return {'success': False, 'message': f'Failed to update customer: {response.status_code}'}
            
    except Exception as e:
        print(f"❌ Error updating credit customer: {e}")
        return {'success': False, 'message': str(e)}

def delete_credit_customer(customer_id):
    return update_credit_customer(customer_id, {'account_status': 'inactive'})

# ============================================================
# record_credit_purchase - THE WORKING VERSION
# ============================================================

def record_credit_purchase(customer_id, items, total_amount, staff_name, notes=""):
    try:
        print(f"🔍 record_credit_purchase called with customer_id: '{customer_id}'")
        print(f"💰 Amount: {total_amount}")
        
        # Get the customer
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?customer_id=eq.{customer_id}&select=*",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code != 200:
            return {'success': False, 'message': 'Customer not found'}
        
        customers = response.json()
        if not customers:
            return {'success': False, 'message': 'Customer not found'}
        
        customer = customers[0]
        print(f"✅ Customer found: {customer.get('full_name')}")
        
        current_balance = float(customer.get('current_balance', 0))
        credit_limit = float(customer.get('credit_limit', 0))
        total_amount = float(total_amount)
        
        if credit_limit > 0 and (current_balance + total_amount) > credit_limit:
            return {
                'success': False, 
                'message': f'Credit limit exceeded. Limit: KSh {credit_limit:,.2f}'
            }
        
        new_balance = current_balance + total_amount
        
        # Save transaction
        transaction_data = {
            'customer_id': customer_id,
            'transaction_type': 'purchase',
            'amount': total_amount,
            'description': f'Credit purchase: {items} | Staff: {staff_name} | Notes: {notes}',
            'staff_name': staff_name,
            'created_at': datetime.utcnow().isoformat()
        }
        
        print(f"📤 Inserting transaction: {transaction_data}")
        
        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions",
            headers=Config.SUPABASE_HEADERS,
            json=transaction_data,
            timeout=30
        )
        
        if response.status_code not in [200, 201]:
            print(f"❌ Transaction error: {response.text}")
            return {'success': False, 'message': f'Failed to record transaction: {response.status_code}'}
        
        print(f"✅ Transaction saved")
        
        # UPDATE CUSTOMER BALANCE
        update_data = {
            'current_balance': new_balance,
            'total_purchases': float(customer.get('total_purchases', 0)) + total_amount,
            'last_purchase_date': datetime.utcnow().date().isoformat()
        }
        
        print(f"📤 Updating customer balance: {update_data}")
        
        update_response = requests.patch(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?customer_id=eq.{customer_id}",
            headers=Config.SUPABASE_HEADERS,
            json=update_data,
            timeout=30
        )
        
        if update_response.status_code not in [200, 204]:
            print(f"⚠️ Failed to update customer balance")
            return {'success': False, 'message': 'Transaction saved but failed to update balance'}
        
        print(f"✅ Customer balance updated to: {new_balance}")
        
        return {
            'success': True,
            'balance_after': new_balance,
            'customer_name': customer.get('full_name'),
            'message': f'Credit purchase recorded. New balance: KSh {new_balance:,.2f}'
        }
        
    except Exception as e:
        print(f"❌ Error recording credit purchase: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': str(e)}

# ============================================================
# record_credit_payment - THE WORKING VERSION
# ============================================================

def record_credit_payment(customer_id, amount, staff_name, notes=""):
    try:
        customer = get_credit_customer_by_id(customer_id)
        if not customer:
            return {'success': False, 'message': 'Customer not found'}
        
        current_balance = float(customer.get('current_balance', 0))
        current_total_payments = float(customer.get('total_payments', 0))
        amount = float(amount)
        
        if amount > current_balance:
            return {'success': False, 'message': f'Payment exceeds balance. Balance: KSh {current_balance:,.2f}'}
        
        new_balance = current_balance - amount
        
        # Save payment
        transaction_data = {
            'customer_id': customer_id,
            'transaction_type': 'payment',
            'amount': amount,
            'description': f'Payment: {notes} | Staff: {staff_name}',
            'staff_name': staff_name,
            'created_at': datetime.utcnow().isoformat()
        }
        
        print(f"📤 Inserting payment: {transaction_data}")
        
        response = requests.post(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions",
            headers=Config.SUPABASE_HEADERS,
            json=transaction_data,
            timeout=30
        )
        
        if response.status_code not in [200, 201]:
            return {'success': False, 'message': f'Failed to record payment: {response.status_code}'}
        
        print(f"✅ Payment saved")
        
        # UPDATE CUSTOMER BALANCE
        update_data = {
            'current_balance': new_balance,
            'total_payments': current_total_payments + amount,
            'last_payment_date': datetime.utcnow().date().isoformat()
        }
        
        print(f"📤 Updating customer balance: {update_data}")
        
        update_response = requests.patch(
            f"{Config.SUPABASE_URL}/rest/v1/credit_customers?customer_id=eq.{customer_id}",
            headers=Config.SUPABASE_HEADERS,
            json=update_data,
            timeout=30
        )
        
        if update_response.status_code not in [200, 204]:
            return {'success': False, 'message': 'Payment recorded but failed to update balance'}
        
        print(f"✅ Customer balance updated to: {new_balance}")
        
        return {
            'success': True,
            'balance_after': new_balance,
            'customer_name': customer.get('full_name'),
            'message': f'Payment recorded. New balance: KSh {new_balance:,.2f}'
        }
        
    except Exception as e:
        print(f"❌ Error recording payment: {e}")
        return {'success': False, 'message': str(e)}

def get_customer_transactions(customer_id):
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?customer_id=eq.{customer_id}&order=created_at.desc",
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

def get_all_credit_transactions():
    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?select=*&order=created_at.desc",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            transactions = response.json()
            for t in transactions:
                if t.get('customer_id'):
                    customer = get_credit_customer_by_id(t.get('customer_id'))
                    if customer:
                        t['customer_name'] = customer.get('full_name', 'Unknown')
                    else:
                        t['customer_name'] = 'Unknown'
            return transactions
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting all credit transactions: {e}")
        return []

def get_full_credit_summary():
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
            
            # Check overdue (simplified)
            if c.get('account_status') == 'active' and c.get('current_balance', 0) > 0:
                overdue_count += 1
        
        collection_rate = round((total_payments_received / total_credit_sales * 100) if total_credit_sales > 0 else 0, 1)
        
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

def get_credit_summary():
    return get_full_credit_summary()

def get_overdue_customers():
    try:
        customers = get_all_credit_customers()
        overdue = []
        for c in customers:
            if c.get('account_status') == 'active' and c.get('current_balance', 0) > 0:
                overdue.append({
                    'customer_id': c.get('customer_id'),
                    'full_name': c.get('full_name'),
                    'phone': c.get('phone'),
                    'balance': c.get('current_balance', 0),
                    'credit_limit': c.get('credit_limit', 0),
                    'days_overdue': 0
                })
        return overdue
    except Exception as e:
        print(f"❌ Error getting overdue customers: {e}")
        return []

def get_monthly_credit_report(year=None):
    try:
        if not year:
            year = datetime.utcnow().year
        
        transactions = get_all_credit_transactions()
        months = {}
        
        for tx in transactions:
            tx_date = None
            date_str = tx.get('created_at', '')
            
            if date_str:
                try:
                    if 'T' in date_str:
                        clean_date = date_str.replace('Z', '').replace('+00:00', '')
                        tx_date = datetime.fromisoformat(clean_date[:19])
                    else:
                        tx_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
                except:
                    tx_date = datetime.utcnow()
            
            if not tx_date:
                tx_date = datetime.utcnow()
            
            if tx_date.year != year:
                continue
            
            month_key = tx_date.strftime('%b %Y')
            
            if month_key not in months:
                months[month_key] = {
                    'month': month_key,
                    'total_credit_sales': 0,
                    'total_payments': 0,
                    'net_change': 0,
                    'transactions_count': 0
                }
            
            tx_type = tx.get('transaction_type', 'purchase').lower()
            tx_amount = float(tx.get('amount', 0))
            
            if tx_type == 'payment':
                months[month_key]['total_payments'] += tx_amount
            else:
                months[month_key]['total_credit_sales'] += tx_amount
            
            months[month_key]['transactions_count'] += 1
        
        report = list(months.values())
        for r in report:
            r['net_change'] = r['total_credit_sales'] - r['total_payments']
        
        return report
        
    except Exception as e:
        print(f"❌ Error getting monthly credit report: {e}")
        return []

def get_credit_dashboard_data():
    try:
        summary = get_full_credit_summary()
        overdue = get_overdue_customers()
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
