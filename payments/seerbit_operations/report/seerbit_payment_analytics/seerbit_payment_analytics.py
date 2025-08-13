# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, formatdate, get_first_day, get_last_day, add_months


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(filters)
    
    return columns, data, None, None, summary


def get_columns():
    return [
        {
            "fieldname": "date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "payment_request",
            "label": _("Payment Request"),
            "fieldtype": "Link",
            "options": "SeerBit Payment Request",
            "width": 150
        },
        {
            "fieldname": "customer_name",
            "label": _("Customer"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "reference_doctype",
            "label": _("Reference Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "reference_name",
            "label": _("Reference"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "amount",
            "label": _("Amount"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "currency",
            "label": _("Currency"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "payment_method",
            "label": _("Payment Method"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "seerbit_reference",
            "label": _("SeerBit Reference"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "processing_time",
            "label": _("Processing Time (hrs)"),
            "fieldtype": "Float",
            "width": 120
        }
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    
    data = frappe.db.sql(f"""
        SELECT
            DATE(pr.request_date) as date,
            pr.name as payment_request,
            pr.customer_name,
            pr.reference_doctype,
            pr.reference_name,
            pr.amount,
            pr.currency,
            pr.status,
            tl.payment_method,
            pr.seerbit_payment_reference as seerbit_reference,
            CASE 
                WHEN pr.payment_date IS NOT NULL AND pr.request_date IS NOT NULL
                THEN TIMESTAMPDIFF(HOUR, pr.request_date, pr.payment_date)
                ELSE NULL
            END as processing_time
        FROM `tabSeerBit Payment Request` pr
        LEFT JOIN `tabSeerBit Transaction Log` tl 
            ON tl.reference_name = pr.name 
            AND tl.reference_doctype = 'SeerBit Payment Request'
            AND tl.status = 'Success'
        WHERE {conditions}
        ORDER BY pr.request_date DESC
    """, as_dict=1)
    
    return data


def get_conditions(filters):
    conditions = ["1=1"]
    
    if filters.get("from_date"):
        conditions.append(f"pr.request_date >= '{filters.get('from_date')}'")
    
    if filters.get("to_date"):
        conditions.append(f"pr.request_date <= '{filters.get('to_date')}'")
    
    if filters.get("status"):
        conditions.append(f"pr.status = '{filters.get('status')}'")
    
    if filters.get("customer"):
        conditions.append(f"pr.customer = '{filters.get('customer')}'")
    
    if filters.get("reference_doctype"):
        conditions.append(f"pr.reference_doctype = '{filters.get('reference_doctype')}'")
    
    return " AND ".join(conditions)


def get_summary(filters):
    conditions = get_conditions(filters)
    
    summary_data = frappe.db.sql(f"""
        SELECT
            COUNT(*) as total_requests,
            SUM(CASE WHEN status = 'Paid' THEN 1 ELSE 0 END) as successful_payments,
            SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) as failed_payments,
            SUM(CASE WHEN status = 'Paid' THEN amount ELSE 0 END) as total_collections,
            AVG(CASE WHEN status = 'Paid' THEN amount ELSE NULL END) as avg_transaction_value,
            COUNT(DISTINCT customer) as unique_customers
        FROM `tabSeerBit Payment Request` pr
        WHERE {conditions}
    """, as_dict=1)
    
    if summary_data:
        data = summary_data[0]
        success_rate = (data.successful_payments / data.total_requests * 100) if data.total_requests > 0 else 0
        
        return [
            {
                "value": data.total_requests or 0,
                "label": _("Total Requests"),
                "datatype": "Int",
                "indicator": "Blue"
            },
            {
                "value": data.successful_payments or 0,
                "label": _("Successful Payments"),
                "datatype": "Int",
                "indicator": "Green"
            },
            {
                "value": f"{success_rate:.1f}%",
                "label": _("Success Rate"),
                "datatype": "Data",
                "indicator": "Green" if success_rate >= 90 else "Orange" if success_rate >= 75 else "Red"
            },
            {
                "value": flt(data.total_collections or 0, 2),
                "label": _("Total Collections"),
                "datatype": "Currency",
                "indicator": "Green"
            },
            {
                "value": flt(data.avg_transaction_value or 0, 2),
                "label": _("Average Transaction"),
                "datatype": "Currency",
                "indicator": "Blue"
            },
            {
                "value": data.unique_customers or 0,
                "label": _("Unique Customers"),
                "datatype": "Int",
                "indicator": "Purple"
            }
        ]
    
    return []


def get_chart_data(data, filters):
    """Generate chart data for the report"""
    if not data:
        return None
    
    # Group data by date for trends
    date_wise_data = {}
    for row in data:
        date = row.get("date")
        if date not in date_wise_data:
            date_wise_data[date] = {"successful": 0, "failed": 0, "amount": 0}
        
        if row.get("status") == "Paid":
            date_wise_data[date]["successful"] += 1
            date_wise_data[date]["amount"] += flt(row.get("amount", 0))
        elif row.get("status") == "Failed":
            date_wise_data[date]["failed"] += 1
    
    # Sort dates
    sorted_dates = sorted(date_wise_data.keys())
    
    return {
        "data": {
            "labels": [formatdate(date) for date in sorted_dates],
            "datasets": [
                {
                    "name": "Successful Payments",
                    "values": [date_wise_data[date]["successful"] for date in sorted_dates]
                },
                {
                    "name": "Failed Payments", 
                    "values": [date_wise_data[date]["failed"] for date in sorted_dates]
                },
                {
                    "name": "Collection Amount",
                    "values": [date_wise_data[date]["amount"] for date in sorted_dates],
                    "yAxis": 1
                }
            ]
        },
        "type": "line",
        "colors": ["#28a745", "#dc3545", "#007bff"]
    }
