# -*- coding: utf-8 -*-
"""
SeerBit Selling Operations - Sales Order Payment Processing
Handles sales order specific payment operations
"""

import frappe
from frappe import _
from frappe.utils import nowdate
from .invoice_payments import SeerBitSellingOperations

# This module extends the main selling operations
# Additional sales order specific functions can be added here

@frappe.whitelist()
def get_sales_order_payment_status(sales_order_name):
    """Get payment status for a sales order"""
    sales_order = frappe.get_doc("Sales Order", sales_order_name)
    
    # Get latest SeerBit order for this sales order
    orders = frappe.get_all("SeerBit Order", 
        filters={
            "customer_name": sales_order.customer_name,
            "currency": sales_order.currency
        },
        fields=["name", "payment_reference", "status", "amount", "created"],
        order_by="created desc",
        limit=5
    )
    
    # Filter orders that match this sales order from metadata
    matching_orders = []
    for order_data in orders:
        order = frappe.get_doc("SeerBit Order", order_data.name)
        meta_data = frappe.parse_json(order.meta_data or "{}")
        if meta_data.get("sales_order_name") == sales_order_name:
            matching_orders.append({
                "order_id": order.name,
                "payment_reference": order.payment_reference,
                "status": order.status,
                "amount": order.amount,
                "created": order.creation
            })
    
    return {
        "sales_order": sales_order_name,
        "total_amount": sales_order.grand_total,
        "advance_paid": sales_order.advance_paid,
        "outstanding_amount": sales_order.grand_total - sales_order.advance_paid,
        "payment_orders": matching_orders
    }


@frappe.whitelist()
def create_balance_payment_link(sales_order_name):
    """Create payment link for remaining balance after advance payments"""
    sales_order = frappe.get_doc("Sales Order", sales_order_name)
    
    outstanding_amount = sales_order.grand_total - sales_order.advance_paid
    if outstanding_amount <= 0:
        frappe.throw(_("No outstanding amount for this Sales Order"))
    
    selling_ops = SeerBitSellingOperations()
    
    # Calculate the percentage needed to pay the remaining balance
    balance_percentage = (outstanding_amount / (sales_order.grand_total - sales_order.advance_paid)) * 100
    
    return selling_ops.create_sales_order_advance_payment(
        sales_order_name, 
        advance_percentage=balance_percentage
    )
