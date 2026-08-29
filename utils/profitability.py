import os
import json
import requests
from datetime import datetime
from config import Config

# ============================================================
# PROFITABILITY TRACKING - ONLY PAID SALES
# ============================================================

def get_paid_sales():
    """
    Get ONLY PAID sales:
    - Cash + POS = already paid
    - Credit payments = paid by credit customers
    - Credit outstanding = NOT counted (not yet paid)
    """
    try:
        # 1. Get orders (Cash + POS - already paid)
        orders_response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/orders?select=total,status",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        total_orders = 0
        if orders_response.status_code == 200:
            orders = orders_response.json()
            for order in orders:
                if order.get('status') != 'cancelled':
                    total_orders += float(order.get('total', 0))
        
        # 2. Get credit PAYMENTS (money actually received from credit customers)
        credit_response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?select=amount,transaction_type",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        total_credit_paid = 0
        total_credit_sales = 0
        if credit_response.status_code == 200:
            transactions = credit_response.json()
            for tx in transactions:
                tx_type = tx.get('transaction_type', '').lower()
                amount = float(tx.get('amount', 0))
                if tx_type == 'purchase':
                    total_credit_sales += amount
                elif tx_type == 'payment':
                    total_credit_paid += amount
        
        # 3. Calculate totals
        # ✅ Only PAID sales count towards profit
        total_paid_sales = total_orders + total_credit_paid
        outstanding_credit = total_credit_sales - total_credit_paid
        
        return {
            'total_paid_sales': total_paid_sales,
            'cash_pos_sales': total_orders,
            'credit_payments_received': total_credit_paid,
            'total_credit_sales': total_credit_sales,
            'outstanding_credit': outstanding_credit,
            'collection_rate': round((total_credit_paid / total_credit_sales * 100) if total_credit_sales > 0 else 0, 2)
        }
        
    except Exception as e:
        print(f"❌ Error getting paid sales: {e}")
        return {
            'total_paid_sales': 0,
            'cash_pos_sales': 0,
            'credit_payments_received': 0,
            'total_credit_sales': 0,
            'outstanding_credit': 0,
            'collection_rate': 0
        }

def get_profitability_summary():
    """Get profitability based ONLY on PAID sales"""
    try:
        sales_data = get_paid_sales()
        
        # ✅ Cost is based on PAID sales only
        cost_of_goods = sales_data['total_paid_sales'] * 0.7
        total_profit = sales_data['total_paid_sales'] - cost_of_goods
        profit_margin = round((total_profit / sales_data['total_paid_sales'] * 100) if sales_data['total_paid_sales'] > 0 else 0, 2)
        
        return {
            'total_revenue': sales_data['total_paid_sales'],           # ✅ Only paid sales
            'cash_pos_revenue': sales_data['cash_pos_sales'],
            'credit_payments_received': sales_data['credit_payments_received'],
            'total_credit_sales': sales_data['total_credit_sales'],
            'outstanding_credit': sales_data['outstanding_credit'],
            'collection_rate': sales_data['collection_rate'],
            'cost_of_goods': cost_of_goods,
            'total_profit': total_profit,
            'profit_margin': profit_margin
        }
        
    except Exception as e:
        print(f"❌ Error getting profitability: {e}")
        return {
            'total_revenue': 0,
            'cash_pos_revenue': 0,
            'credit_payments_received': 0,
            'total_credit_sales': 0,
            'outstanding_credit': 0,
            'collection_rate': 0,
            'cost_of_goods': 0,
            'total_profit': 0,
            'profit_margin': 0
        }

def get_monthly_profitability(year=None):
    """Get monthly profitability based ONLY on PAID sales"""
    try:
        if not year:
            year = datetime.utcnow().year
        
        # Get orders (Cash + POS)
        orders_response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/orders?select=total,created_at,status",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        # Get credit transactions
        credit_response = requests.get(
            f"{Config.SUPABASE_URL}/rest/v1/credit_transactions?select=amount,transaction_type,created_at",
            headers=Config.SUPABASE_HEADERS,
            timeout=30
        )
        
        months = {}
        month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Process orders (already paid)
        if orders_response.status_code == 200:
            orders = orders_response.json()
            for order in orders:
                if order.get('status') == 'cancelled':
                    continue
                    
                created_at = order.get('created_at', '')
                if not created_at:
                    continue
                    
                try:
                    if 'T' in created_at:
                        clean_date = created_at.replace('Z', '').replace('+00:00', '')
                        order_date = datetime.fromisoformat(clean_date[:19])
                    else:
                        order_date = datetime.strptime(created_at[:10], '%Y-%m-%d')
                except:
                    continue
                
                if order_date.year != year:
                    continue
                
                month_key = order_date.strftime('%b %Y')
                
                if month_key not in months:
                    months[month_key] = {
                        'month': month_key,
                        'cash_pos_sales': 0,
                        'credit_payments': 0,
                        'total_paid_sales': 0,
                        'credit_sales': 0,
                        'outstanding': 0,
                        'profit': 0,
                        'margin': 0
                    }
                
                months[month_key]['cash_pos_sales'] += float(order.get('total', 0))
        
        # Process credit transactions
        if credit_response.status_code == 200:
            transactions = credit_response.json()
            for tx in transactions:
                created_at = tx.get('created_at', '')
                if not created_at:
                    continue
                    
                try:
                    if 'T' in created_at:
                        clean_date = created_at.replace('Z', '').replace('+00:00', '')
                        tx_date = datetime.fromisoformat(clean_date[:19])
                    else:
                        tx_date = datetime.strptime(created_at[:10], '%Y-%m-%d')
                except:
                    continue
                
                if tx_date.year != year:
                    continue
                
                month_key = tx_date.strftime('%b %Y')
                
                if month_key not in months:
                    months[month_key] = {
                        'month': month_key,
                        'cash_pos_sales': 0,
                        'credit_payments': 0,
                        'total_paid_sales': 0,
                        'credit_sales': 0,
                        'outstanding': 0,
                        'profit': 0,
                        'margin': 0
                    }
                
                tx_type = tx.get('transaction_type', '').lower()
                amount = float(tx.get('amount', 0))
                
                if tx_type == 'purchase':
                    months[month_key]['credit_sales'] += amount
                elif tx_type == 'payment':
                    months[month_key]['credit_payments'] += amount
        
        # Calculate totals and profit for each month
        for key in months:
            # ✅ Only PAID sales count
            months[key]['total_paid_sales'] = months[key]['cash_pos_sales'] + months[key]['credit_payments']
            months[key]['outstanding'] = months[key]['credit_sales'] - months[key]['credit_payments']
            months[key]['profit'] = months[key]['total_paid_sales'] * 0.3  # 30% profit margin
            months[key]['margin'] = round((months[key]['profit'] / months[key]['total_paid_sales'] * 100) if months[key]['total_paid_sales'] > 0 else 0, 2)
        
        report = list(months.values())
        report.sort(key=lambda x: month_order.index(x['month'].split()[0]) if x['month'].split()[0] in month_order else 99)
        
        return report
        
    except Exception as e:
        print(f"❌ Error getting monthly profitability: {e}")
        return []
