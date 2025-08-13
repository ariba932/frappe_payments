#!/usr/bin/env python3
"""
Enhanced SeerBit Dashboard and Reporting Utilities
Provides comprehensive analytics and reporting for SeerBit payments
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days, get_datetime
import json
from datetime import datetime, timedelta

@frappe.whitelist()
def get_payment_dashboard_data(company=None, from_date=None, to_date=None):
    """
    Get comprehensive payment dashboard data for SeerBit
    """
    try:
        if not from_date:
            from_date = add_days(getdate(), -30)
        if not to_date:
            to_date = getdate()
        
        # Base filters
        filters = {
            "creation": ["between", [from_date, to_date]]
        }
        
        if company:
            filters["company"] = company
        
        # Get payment summary
        payment_summary = get_payment_summary(filters)
        
        # Get payment trends
        payment_trends = get_payment_trends(filters)
        
        # Get top customers
        top_customers = get_top_customers(filters)
        
        # Get payment method breakdown
        payment_methods = get_payment_method_breakdown(filters)
        
        # Get recent transactions
        recent_transactions = get_recent_transactions(filters)
        
        # Get payout summary
        payout_summary = get_payout_summary(filters)
        
        return {
            "payment_summary": payment_summary,
            "payment_trends": payment_trends,
            "top_customers": top_customers,
            "payment_methods": payment_methods,
            "recent_transactions": recent_transactions,
            "payout_summary": payout_summary,
            "date_range": {
                "from_date": from_date,
                "to_date": to_date
            }
        }
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Dashboard Error")
        return {"error": str(e)}

def get_payment_summary(filters):
    """
    Get payment summary statistics
    """
    # Total payments received
    payment_entries = frappe.get_all("Payment Entry",
        filters=dict(filters, **{
            "payment_type": "Receive",
            "docstatus": 1,
            "custom_payment_gateway": "SeerBit"
        }),
        fields=["sum(paid_amount) as total_amount", "count(name) as total_count"]
    )
    
    total_received = payment_entries[0]["total_amount"] if payment_entries else 0
    total_count = payment_entries[0]["total_count"] if payment_entries else 0
    
    # SeerBit Orders summary
    seerbit_orders = frappe.get_all("SeerBit Order",
        filters=filters,
        fields=["sum(amount) as total_amount", "count(name) as total_count",
                "status"]
    )
    
    orders_by_status = {}
    total_order_amount = 0
    total_order_count = 0
    
    for order in seerbit_orders:
        status = order.get("status", "Unknown")
        orders_by_status[status] = {
            "amount": order["total_amount"] or 0,
            "count": order["total_count"] or 0
        }
        total_order_amount += order["total_amount"] or 0
        total_order_count += order["total_count"] or 0
    
    # Success rate calculation
    completed_orders = orders_by_status.get("Completed", {"count": 0, "amount": 0})
    success_rate = (completed_orders["count"] / total_order_count * 100) if total_order_count > 0 else 0
    
    # Average transaction value
    avg_transaction_value = total_received / total_count if total_count > 0 else 0
    
    return {
        "total_received": total_received,
        "total_transactions": total_count,
        "total_order_amount": total_order_amount,
        "total_order_count": total_order_count,
        "success_rate": round(success_rate, 2),
        "avg_transaction_value": round(avg_transaction_value, 2),
        "orders_by_status": orders_by_status
    }

def get_payment_trends(filters):
    """
    Get payment trends over time
    """
    from_date = filters["creation"][1][0]
    to_date = filters["creation"][1][1]
    
    # Generate date range
    date_list = []
    current_date = getdate(from_date)
    end_date = getdate(to_date)
    
    while current_date <= end_date:
        date_list.append(current_date.strftime("%Y-%m-%d"))
        current_date = add_days(current_date, 1)
    
    # Get daily payment data
    daily_payments = frappe.db.sql("""
        SELECT 
            DATE(creation) as payment_date,
            SUM(amount) as total_amount,
            COUNT(*) as transaction_count
        FROM `tabSeerBit Order`
        WHERE creation BETWEEN %s AND %s
        AND status = 'Completed'
        GROUP BY DATE(creation)
        ORDER BY payment_date
    """, (from_date, to_date), as_dict=True)
    
    # Create trends data
    trends_data = []
    payment_lookup = {p["payment_date"].strftime("%Y-%m-%d"): p for p in daily_payments}
    
    for date_str in date_list:
        payment_data = payment_lookup.get(date_str, {"total_amount": 0, "transaction_count": 0})
        trends_data.append({
            "date": date_str,
            "amount": payment_data["total_amount"],
            "count": payment_data["transaction_count"]
        })
    
    return trends_data

def get_top_customers(filters, limit=10):
    """
    Get top customers by payment amount
    """
    top_customers = frappe.db.sql("""
        SELECT 
            pe.party as customer,
            c.customer_name,
            SUM(pe.paid_amount) as total_paid,
            COUNT(pe.name) as transaction_count
        FROM `tabPayment Entry` pe
        JOIN `tabCustomer` c ON pe.party = c.name
        WHERE pe.payment_type = 'Receive'
        AND pe.docstatus = 1
        AND pe.custom_payment_gateway = 'SeerBit'
        AND pe.creation BETWEEN %s AND %s
        GROUP BY pe.party
        ORDER BY total_paid DESC
        LIMIT %s
    """, (filters["creation"][1][0], filters["creation"][1][1], limit), as_dict=True)
    
    return top_customers

def get_payment_method_breakdown(filters):
    """
    Get payment method breakdown from SeerBit orders
    """
    # Since SeerBit handles various payment methods, we can extract this from gateway responses
    orders = frappe.get_all("SeerBit Order",
        filters=dict(filters, status="Completed"),
        fields=["gateway_response", "amount"]
    )
    
    method_breakdown = {}
    
    for order in orders:
        try:
            if order.gateway_response:
                response_data = json.loads(order.gateway_response)
                payment_method = response_data.get("paymentMethod", "Unknown")
                
                if payment_method not in method_breakdown:
                    method_breakdown[payment_method] = {"amount": 0, "count": 0}
                
                method_breakdown[payment_method]["amount"] += order.amount
                method_breakdown[payment_method]["count"] += 1
        except:
            # Handle invalid JSON
            if "Unknown" not in method_breakdown:
                method_breakdown["Unknown"] = {"amount": 0, "count": 0}
            method_breakdown["Unknown"]["amount"] += order.amount
            method_breakdown["Unknown"]["count"] += 1
    
    # Convert to list format
    method_list = []
    for method, data in method_breakdown.items():
        method_list.append({
            "method": method,
            "amount": data["amount"],
            "count": data["count"],
            "percentage": 0  # Will be calculated on frontend
        })
    
    # Calculate percentages
    total_amount = sum(m["amount"] for m in method_list)
    if total_amount > 0:
        for method in method_list:
            method["percentage"] = round(method["amount"] / total_amount * 100, 2)
    
    return sorted(method_list, key=lambda x: x["amount"], reverse=True)

def get_recent_transactions(filters, limit=50):
    """
    Get recent transactions
    """
    recent_orders = frappe.get_all("SeerBit Order",
        filters=filters,
        fields=["name", "payment_reference", "amount", "currency", "status", 
                "customer_name", "customer_email", "creation", "transaction_id",
                "meta_data"],
        order_by="creation desc",
        limit=limit
    )
    
    # Enhance with document type information
    for order in recent_orders:
        try:
            if order.meta_data:
                meta_data = json.loads(order.meta_data)
                if "sales_invoice_name" in meta_data:
                    order["document_type"] = "Sales Invoice"
                    order["document_name"] = meta_data["sales_invoice_name"]
                elif "sales_order_name" in meta_data:
                    order["document_type"] = "Sales Order"
                    order["document_name"] = meta_data["sales_order_name"]
                    order["advance_percentage"] = meta_data.get("advance_percentage", 0)
                else:
                    order["document_type"] = "Unknown"
                    order["document_name"] = ""
            else:
                order["document_type"] = "Unknown"
                order["document_name"] = ""
        except:
            order["document_type"] = "Unknown"
            order["document_name"] = ""
    
    return recent_orders

def get_payout_summary(filters):
    """
    Get payout summary for SeerBit
    """
    # Get payout payment entries
    payout_entries = frappe.get_all("Payment Entry",
        filters=dict(filters, **{
            "payment_type": "Pay",
            "docstatus": 1,
            "custom_payment_gateway": "SeerBit"
        }),
        fields=["sum(paid_amount) as total_amount", "count(name) as total_count",
                "custom_seerbit_payout_status"]
    )
    
    total_payout_amount = 0
    total_payout_count = 0
    payout_by_status = {}
    
    for payout in payout_entries:
        status = payout.get("custom_seerbit_payout_status", "Pending")
        if status not in payout_by_status:
            payout_by_status[status] = {"amount": 0, "count": 0}
        
        payout_by_status[status]["amount"] += payout["total_amount"] or 0
        payout_by_status[status]["count"] += payout["total_count"] or 0
        total_payout_amount += payout["total_amount"] or 0
        total_payout_count += payout["total_count"] or 0
    
    return {
        "total_payout_amount": total_payout_amount,
        "total_payout_count": total_payout_count,
        "payout_by_status": payout_by_status
    }

@frappe.whitelist()
def get_payment_analytics_report(company=None, from_date=None, to_date=None, group_by="daily"):
    """
    Get detailed payment analytics report
    """
    try:
        if not from_date:
            from_date = add_days(getdate(), -30)
        if not to_date:
            to_date = getdate()
        
        # Determine grouping SQL
        if group_by == "daily":
            date_format = "DATE(creation)"
        elif group_by == "weekly":
            date_format = "YEARWEEK(creation)"
        elif group_by == "monthly":
            date_format = "DATE_FORMAT(creation, '%Y-%m')"
        else:
            date_format = "DATE(creation)"
        
        # Get grouped payment data
        analytics_data = frappe.db.sql(f"""
            SELECT 
                {date_format} as period,
                SUM(CASE WHEN status = 'Completed' THEN amount ELSE 0 END) as successful_amount,
                COUNT(CASE WHEN status = 'Completed' THEN 1 END) as successful_count,
                SUM(CASE WHEN status = 'Failed' THEN amount ELSE 0 END) as failed_amount,
                COUNT(CASE WHEN status = 'Failed' THEN 1 END) as failed_count,
                SUM(CASE WHEN status = 'Pending' THEN amount ELSE 0 END) as pending_amount,
                COUNT(CASE WHEN status = 'Pending' THEN 1 END) as pending_count,
                SUM(amount) as total_amount,
                COUNT(*) as total_count
            FROM `tabSeerBit Order`
            WHERE creation BETWEEN %s AND %s
            GROUP BY {date_format}
            ORDER BY period
        """, (from_date, to_date), as_dict=True)
        
        # Calculate success rates and other metrics
        for data in analytics_data:
            total_transactions = data["total_count"]
            if total_transactions > 0:
                data["success_rate"] = round(data["successful_count"] / total_transactions * 100, 2)
                data["failure_rate"] = round(data["failed_count"] / total_transactions * 100, 2)
                data["pending_rate"] = round(data["pending_count"] / total_transactions * 100, 2)
            else:
                data["success_rate"] = 0
                data["failure_rate"] = 0
                data["pending_rate"] = 0
            
            data["avg_transaction_value"] = round(data["successful_amount"] / data["successful_count"], 2) if data["successful_count"] > 0 else 0
        
        return {
            "analytics_data": analytics_data,
            "group_by": group_by,
            "date_range": {
                "from_date": from_date,
                "to_date": to_date
            }
        }
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Analytics Report Error")
        return {"error": str(e)}

@frappe.whitelist()
def export_payment_report(company=None, from_date=None, to_date=None, format="xlsx"):
    """
    Export detailed payment report
    """
    try:
        if not from_date:
            from_date = add_days(getdate(), -90)
        if not to_date:
            to_date = getdate()
        
        # Get detailed payment data
        payment_data = frappe.db.sql("""
            SELECT 
                so.creation,
                so.payment_reference,
                so.amount,
                so.currency,
                so.status,
                so.customer_name,
                so.customer_email,
                so.transaction_id,
                pe.name as payment_entry,
                pe.reference_date,
                CASE 
                    WHEN so.meta_data LIKE '%%sales_invoice_name%%' THEN 'Sales Invoice'
                    WHEN so.meta_data LIKE '%%sales_order_name%%' THEN 'Sales Order'
                    ELSE 'Unknown'
                END as document_type
            FROM `tabSeerBit Order` so
            LEFT JOIN `tabPayment Entry` pe ON so.payment_entry = pe.name
            WHERE so.creation BETWEEN %s AND %s
            ORDER BY so.creation DESC
        """, (from_date, to_date), as_dict=True)
        
        if format == "xlsx":
            return generate_excel_report(payment_data, from_date, to_date)
        else:
            return generate_csv_report(payment_data, from_date, to_date)
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Export Report Error")
        frappe.throw(_("Failed to generate report: {0}").format(str(e)))

def generate_excel_report(data, from_date, to_date):
    """
    Generate Excel report for payment data
    """
    from frappe.utils.xlsxutils import make_xlsx
    
    columns = [
        "Date", "Payment Reference", "Amount", "Currency", "Status",
        "Customer Name", "Customer Email", "Transaction ID", 
        "Payment Entry", "Document Type"
    ]
    
    rows = []
    for payment in data:
        rows.append([
            payment.get("creation", ""),
            payment.get("payment_reference", ""),
            payment.get("amount", 0),
            payment.get("currency", ""),
            payment.get("status", ""),
            payment.get("customer_name", ""),
            payment.get("customer_email", ""),
            payment.get("transaction_id", ""),
            payment.get("payment_entry", ""),
            payment.get("document_type", "")
        ])
    
    filename = f"seerbit_payment_report_{from_date}_to_{to_date}.xlsx"
    
    xlsx_data = make_xlsx([columns] + rows, "SeerBit Payment Report")
    
    frappe.response["filename"] = filename
    frappe.response["filecontent"] = xlsx_data
    frappe.response["type"] = "download"

def generate_csv_report(data, from_date, to_date):
    """
    Generate CSV report for payment data
    """
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Date", "Payment Reference", "Amount", "Currency", "Status",
        "Customer Name", "Customer Email", "Transaction ID", 
        "Payment Entry", "Document Type"
    ])
    
    # Write data
    for payment in data:
        writer.writerow([
            payment.get("creation", ""),
            payment.get("payment_reference", ""),
            payment.get("amount", 0),
            payment.get("currency", ""),
            payment.get("status", ""),
            payment.get("customer_name", ""),
            payment.get("customer_email", ""),
            payment.get("transaction_id", ""),
            payment.get("payment_entry", ""),
            payment.get("document_type", "")
        ])
    
    filename = f"seerbit_payment_report_{from_date}_to_{to_date}.csv"
    
    frappe.response["filename"] = filename
    frappe.response["filecontent"] = output.getvalue()
    frappe.response["type"] = "download"
