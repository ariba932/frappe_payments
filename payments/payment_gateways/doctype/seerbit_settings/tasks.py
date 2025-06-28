#Scheduled tasks for payment gateway verification and cleanup
# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import now
from datetime import datetime,timedelta

def add_hours(dt, hours):
    if isinstance(dt, str):
        dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S.%f")  # or use parse_datetime from frappe.utils
    return dt + timedelta(hours=hours)

def verify_pending_payments():
    """Verify pending SeerBit payments that are older than 1 hour"""
    try:
        # Get pending orders older than 1 hour
        one_hour_ago = add_hours(now(), -1)
        
        pending_orders = frappe.get_all(
            "SeerBit Order",
            filters={
                "status": "Pending",
                "creation": ["<", one_hour_ago]
            },
            fields=["name", "payment_reference"]
        )
        
        if not pending_orders:
            return
        
        settings = frappe.get_doc("SeerBit Settings")
        
        if not settings.is_enabled:
            return
        
        for order_data in pending_orders:
            try:
                # Verify payment status
                verification_result = settings.verify_payment(order_data.payment_reference)
                
                # Update order
                order = frappe.get_doc("SeerBit Order", order_data.name)
                order.update_from_webhook_data({"data": verification_result["payments"]})
                
                frappe.db.commit()
                
            except Exception as e:
                frappe.log_error(
                    f"Failed to verify payment for order {order_data.name}: {str(e)}",
                    "SeerBit Payment Verification Task"
                )
                continue
    
    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "SeerBit Scheduled Payment Verification"
        )


def cleanup_old_orders():
    """Clean up old completed/failed orders (older than 90 days)"""
    try:
        from frappe.utils import add_days
        
        ninety_days_ago = add_days(now(), -90)
        
        old_orders = frappe.get_all(
            "SeerBit Order",
            filters={
                "status": ["in", ["Paid", "Failed", "Cancelled"]],
                "creation": ["<", ninety_days_ago]
            },
            fields=["name"]
        )
        
        for order in old_orders:
            frappe.delete_doc("SeerBit Order", order.name, ignore_permissions=True)
        
        if old_orders:
            frappe.db.commit()
            frappe.log_error(
                f"Cleaned up {len(old_orders)} old SeerBit orders",
                "SeerBit Cleanup Task"
            )
    
    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "SeerBit Cleanup Task Error"
        )
