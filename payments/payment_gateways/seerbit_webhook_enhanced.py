#!/usr/bin/env python3
"""
Enhanced SeerBit Webhook Handler for ERPNext
Handles all SeerBit webhook events with proper verification and processing
"""

import frappe
import json
import hashlib
import hmac
from frappe import _
from frappe.utils import now_datetime, getdate, cstr
from payments.payment_gateways.seerbit_settings import SeerBitSettings

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """
    Enhanced webhook handler for SeerBit events
    Supports: payment success, payment failure, payout completion, refunds
    """
    try:
        # Get webhook data
        webhook_data = frappe.local.form_dict or {}
        
        # For POST requests, get data from request body
        if frappe.request.method == "POST":
            webhook_data = frappe.request.get_json() or webhook_data
        
        frappe.logger().info(f"SeerBit Webhook received: {json.dumps(webhook_data, indent=2)}")
        
        # Verify webhook signature
        if not verify_webhook_signature(webhook_data):
            frappe.log_error("Invalid webhook signature", "SeerBit Webhook Security Error")
            return {"status": "error", "message": "Invalid signature"}
        
        # Extract event details
        event_type = webhook_data.get("eventType")
        payment_reference = webhook_data.get("paymentReference")
        transaction_data = webhook_data.get("data", {})
        
        if not event_type or not payment_reference:
            frappe.log_error(f"Missing event type or payment reference: {webhook_data}", "SeerBit Webhook Error")
            return {"status": "error", "message": "Missing required fields"}
        
        # Process different event types
        if event_type == "PAYMENT_COMPLETE":
            return process_payment_complete(payment_reference, transaction_data)
        elif event_type == "PAYMENT_FAILED":
            return process_payment_failed(payment_reference, transaction_data)
        elif event_type == "PAYOUT_COMPLETE":
            return process_payout_complete(payment_reference, transaction_data)
        elif event_type == "PAYOUT_FAILED":
            return process_payout_failed(payment_reference, transaction_data)
        elif event_type == "REFUND_COMPLETE":
            return process_refund_complete(payment_reference, transaction_data)
        else:
            frappe.logger().info(f"Unhandled webhook event type: {event_type}")
            return {"status": "ok", "message": "Event type not processed"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Webhook Error")
        return {"status": "error", "message": str(e)}

def verify_webhook_signature(webhook_data):
    """
    Verify SeerBit webhook signature for security
    """
    try:
        settings = frappe.get_doc("SeerBit Settings")
        
        # Skip signature verification in development mode
        if frappe.conf.get("developer_mode") and not settings.enforce_webhook_signature:
            return True
        
        signature = frappe.request.headers.get("X-SeerBit-Signature")
        if not signature:
            return False
        
        # Calculate expected signature
        payload = json.dumps(webhook_data, separators=(',', ':'))
        expected_signature = hmac.new(
            settings.get_password("webhook_secret").encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    except Exception as e:
        frappe.log_error(f"Webhook signature verification error: {str(e)}", "SeerBit Security Error")
        return False

def process_payment_complete(payment_reference, transaction_data):
    """
    Process successful payment webhook
    """
    try:
        # Find SeerBit Order
        orders = frappe.get_all("SeerBit Order", 
                               filters={"payment_reference": payment_reference},
                               limit=1)
        
        if not orders:
            frappe.log_error(f"SeerBit Order not found for reference: {payment_reference}", "Webhook Processing Error")
            return {"status": "error", "message": "Order not found"}
        
        order = frappe.get_doc("SeerBit Order", orders[0].name)
        
        # Skip if already processed
        if order.status == "Completed":
            return {"status": "ok", "message": "Already processed"}
        
        # Extract metadata
        meta_data = frappe.parse_json(order.meta_data or "{}")
        
        # Determine document type and process accordingly
        if "sales_invoice_name" in meta_data:
            return process_invoice_payment_webhook(order, transaction_data, meta_data)
        elif "sales_order_name" in meta_data:
            return process_sales_order_payment_webhook(order, transaction_data, meta_data)
        else:
            frappe.log_error(f"Unknown payment type for reference: {payment_reference}", "Webhook Processing Error")
            return {"status": "error", "message": "Unknown payment type"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Payment Complete Webhook Error for {payment_reference}")
        return {"status": "error", "message": str(e)}

def process_invoice_payment_webhook(order, transaction_data, meta_data):
    """
    Process Sales Invoice payment completion via webhook
    """
    try:
        invoice_name = meta_data.get("sales_invoice_name")
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Create Payment Entry
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": invoice.customer,
            "paid_amount": order.amount,
            "received_amount": order.amount,
            "paid_to": _get_default_cash_account(invoice.company),
            "paid_from": _get_default_receivable_account(invoice.company),
            "reference_no": order.payment_reference,
            "reference_date": getdate(),
            "party_balance": 0,
            "remarks": f"SeerBit payment for Sales Invoice {invoice.name} (Webhook)",
            "custom_seerbit_payment_reference": order.payment_reference,
            "custom_seerbit_transaction_id": transaction_data.get("transactionId"),
            "custom_payment_gateway": "SeerBit"
        })
        
        # Add reference to Sales Invoice
        payment_entry.append("references", {
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": order.amount
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update order status
        order.status = "Completed"
        order.transaction_id = transaction_data.get("transactionId")
        order.gateway_response = json.dumps(transaction_data)
        order.payment_entry = payment_entry.name
        order.webhook_processed_at = now_datetime()
        order.save(ignore_permissions=True)
        
        # Update Sales Invoice
        invoice.db_set("custom_seerbit_last_payment_status", "Completed")
        
        frappe.db.commit()
        
        # Send confirmation email if configured
        send_payment_confirmation_email(invoice, payment_entry, order)
        
        return {"status": "success", "message": "Invoice payment processed"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Invoice Payment Webhook Error for {order.payment_reference}")
        return {"status": "error", "message": str(e)}

def process_sales_order_payment_webhook(order, transaction_data, meta_data):
    """
    Process Sales Order advance payment completion via webhook
    """
    try:
        sales_order_name = meta_data.get("sales_order_name")
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        
        advance_amount = meta_data.get("advance_amount")
        advance_percentage = meta_data.get("advance_percentage")
        
        # Create advance Payment Entry
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": sales_order.customer,
            "paid_amount": advance_amount,
            "received_amount": advance_amount,
            "paid_to": _get_default_cash_account(sales_order.company),
            "paid_from": _get_default_receivable_account(sales_order.company),
            "reference_no": order.payment_reference,
            "reference_date": getdate(),
            "is_advance": "Yes",
            "party_balance": 0,
            "remarks": f"SeerBit advance payment ({advance_percentage}%) for Sales Order {sales_order.name} (Webhook)",
            "custom_seerbit_payment_reference": order.payment_reference,
            "custom_seerbit_transaction_id": transaction_data.get("transactionId"),
            "custom_payment_gateway": "SeerBit"
        })
        
        # Add reference to Sales Order
        payment_entry.append("references", {
            "reference_doctype": "Sales Order",
            "reference_name": sales_order.name,
            "allocated_amount": advance_amount
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update order status
        order.status = "Completed"
        order.transaction_id = transaction_data.get("transactionId")
        order.gateway_response = json.dumps(transaction_data)
        order.payment_entry = payment_entry.name
        order.webhook_processed_at = now_datetime()
        order.save(ignore_permissions=True)
        
        # Update Sales Order
        sales_order.db_set("custom_seerbit_last_payment_status", "Completed")
        
        frappe.db.commit()
        
        # Send advance payment confirmation
        send_advance_payment_confirmation_email(sales_order, payment_entry, order)
        
        return {"status": "success", "message": "Advance payment processed"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Sales Order Payment Webhook Error for {order.payment_reference}")
        return {"status": "error", "message": str(e)}

def process_payment_failed(payment_reference, transaction_data):
    """
    Process failed payment webhook
    """
    try:
        orders = frappe.get_all("SeerBit Order", 
                               filters={"payment_reference": payment_reference},
                               limit=1)
        
        if orders:
            order = frappe.get_doc("SeerBit Order", orders[0].name)
            order.status = "Failed"
            order.gateway_response = json.dumps(transaction_data)
            order.webhook_processed_at = now_datetime()
            order.save(ignore_permissions=True)
            
            # Update related documents
            meta_data = frappe.parse_json(order.meta_data or "{}")
            if "sales_invoice_name" in meta_data:
                invoice = frappe.get_doc("Sales Invoice", meta_data["sales_invoice_name"])
                invoice.db_set("custom_seerbit_last_payment_status", "Failed")
            elif "sales_order_name" in meta_data:
                sales_order = frappe.get_doc("Sales Order", meta_data["sales_order_name"])
                sales_order.db_set("custom_seerbit_last_payment_status", "Failed")
            
            frappe.db.commit()
        
        return {"status": "ok", "message": "Payment failure processed"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Payment Failed Webhook Error for {payment_reference}")
        return {"status": "error", "message": str(e)}

def process_payout_complete(payment_reference, transaction_data):
    """
    Process successful payout webhook
    """
    try:
        # Find Payment Entry with this reference
        payment_entries = frappe.get_all("Payment Entry",
                                       filters={"custom_seerbit_payment_reference": payment_reference},
                                       limit=1)
        
        if payment_entries:
            payment_entry = frappe.get_doc("Payment Entry", payment_entries[0].name)
            payment_entry.db_set("custom_seerbit_payout_status", "Completed")
            payment_entry.db_set("custom_seerbit_transaction_id", transaction_data.get("transactionId"))
            
            # Log payout completion
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Payment Entry",
                "reference_name": payment_entry.name,
                "content": f"SeerBit payout completed successfully. Transaction ID: {transaction_data.get('transactionId')}"
            }).insert(ignore_permissions=True)
            
            frappe.db.commit()
        
        return {"status": "success", "message": "Payout completion processed"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Payout Complete Webhook Error for {payment_reference}")
        return {"status": "error", "message": str(e)}

def process_payout_failed(payment_reference, transaction_data):
    """
    Process failed payout webhook
    """
    try:
        # Find Payment Entry with this reference
        payment_entries = frappe.get_all("Payment Entry",
                                       filters={"custom_seerbit_payment_reference": payment_reference},
                                       limit=1)
        
        if payment_entries:
            payment_entry = frappe.get_doc("Payment Entry", payment_entries[0].name)
            payment_entry.db_set("custom_seerbit_payout_status", "Failed")
            
            # Log payout failure
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Workflow",
                "reference_doctype": "Payment Entry",
                "reference_name": payment_entry.name,
                "content": f"SeerBit payout failed. Reason: {transaction_data.get('message', 'Unknown error')}"
            }).insert(ignore_permissions=True)
            
            frappe.db.commit()
        
        return {"status": "ok", "message": "Payout failure processed"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Payout Failed Webhook Error for {payment_reference}")
        return {"status": "error", "message": str(e)}

def process_refund_complete(payment_reference, transaction_data):
    """
    Process refund completion webhook
    """
    try:
        # Find original Payment Entry
        payment_entries = frappe.get_all("Payment Entry",
                                       filters={"custom_seerbit_payment_reference": payment_reference},
                                       limit=1)
        
        if payment_entries:
            original_pe = frappe.get_doc("Payment Entry", payment_entries[0].name)
            
            # Create refund Payment Entry
            refund_pe = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": "Pay",
                "party_type": original_pe.party_type,
                "party": original_pe.party,
                "paid_amount": transaction_data.get("refundAmount", original_pe.paid_amount),
                "received_amount": transaction_data.get("refundAmount", original_pe.received_amount),
                "paid_from": original_pe.paid_to,  # Reverse the accounts
                "paid_to": original_pe.paid_from,
                "reference_no": f"REFUND-{payment_reference}",
                "reference_date": getdate(),
                "remarks": f"SeerBit refund for {original_pe.name}",
                "custom_seerbit_payment_reference": f"REFUND-{payment_reference}",
                "custom_seerbit_transaction_id": transaction_data.get("transactionId"),
                "custom_payment_gateway": "SeerBit",
                "custom_is_refund": 1,
                "custom_original_payment_entry": original_pe.name
            })
            
            refund_pe.insert(ignore_permissions=True)
            refund_pe.submit()
            
            # Update original Payment Entry
            original_pe.db_set("custom_seerbit_refund_status", "Completed")
            original_pe.db_set("custom_seerbit_refund_entry", refund_pe.name)
            
            frappe.db.commit()
        
        return {"status": "success", "message": "Refund processed"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Refund Webhook Error for {payment_reference}")
        return {"status": "error", "message": str(e)}

def send_payment_confirmation_email(invoice, payment_entry, order):
    """
    Send payment confirmation email to customer
    """
    try:
        settings = frappe.get_doc("SeerBit Settings")
        if not settings.send_payment_confirmation_email:
            return
        
        customer = frappe.get_doc("Customer", invoice.customer)
        if not customer.email_id:
            return
        
        frappe.sendmail(
            recipients=[customer.email_id],
            subject=f"Payment Confirmation - Invoice {invoice.name}",
            template="seerbit_payment_confirmation",
            args={
                "invoice": invoice,
                "payment_entry": payment_entry,
                "order": order,
                "customer": customer
            },
            now=True
        )
    except Exception as e:
        frappe.log_error(f"Payment confirmation email error: {str(e)}", "SeerBit Email Error")

def send_advance_payment_confirmation_email(sales_order, payment_entry, order):
    """
    Send advance payment confirmation email to customer
    """
    try:
        settings = frappe.get_doc("SeerBit Settings")
        if not settings.send_payment_confirmation_email:
            return
        
        customer = frappe.get_doc("Customer", sales_order.customer)
        if not customer.email_id:
            return
        
        frappe.sendmail(
            recipients=[customer.email_id],
            subject=f"Advance Payment Confirmation - Order {sales_order.name}",
            template="seerbit_advance_payment_confirmation",
            args={
                "sales_order": sales_order,
                "payment_entry": payment_entry,
                "order": order,
                "customer": customer
            },
            now=True
        )
    except Exception as e:
        frappe.log_error(f"Advance payment confirmation email error: {str(e)}", "SeerBit Email Error")

def _get_default_cash_account(company):
    """Get default cash account for company"""
    return frappe.db.get_value("Company", company, "default_cash_account")

def _get_default_receivable_account(company):
    """Get default receivable account for company"""
    return frappe.db.get_value("Company", company, "default_receivable_account")
