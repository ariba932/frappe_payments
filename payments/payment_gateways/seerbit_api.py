#Seerbit API for Frappe Framework 
# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import get_url, nowdate
from frappe.utils.password import get_decrypted_password
import json
import hashlib
import hmac
from frappe import throw
from frappe import generate_hash


@frappe.whitelist(allow_guest=True)
def create_seerbit_order(**kwargs):
    """Create a SeerBit payment order"""
    try:
        # Get SeerBit settings
        settings = frappe.get_doc("SeerBit Settings")
        
        if not settings.is_enabled:
            frappe.throw(_("SeerBit payment gateway is not enabled"))
        
        # Validate required parameters
        required_params = ["amount", "currency", "email", "full_name"]
        for param in required_params:
            if not kwargs.get(param):
                frappe.throw(_("Missing required parameter: {0}").format(param))
        
        # Generate unique payment reference
        payment_reference = frappe.generate_hash(length=20)
        
        # Create SeerBit Order record
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": payment_reference,
            "amount": float(kwargs["amount"]),
            "currency": kwargs["currency"],
            "customer_email": kwargs["email"],
            "customer_name": kwargs["full_name"],
            "customer_mobile": kwargs.get("mobile", ""),
            "callback_url": kwargs.get("callback_url", frappe.utils.get_url("/api/method/payments.payment_gateways.seerbit_api.seerbit_callback")),
            "status": "Pending"
        })
        order.insert(ignore_permissions=True)
        
        # Create payment with SeerBit
        payment_data = settings.get_payment_url(
            amount=kwargs["amount"],
            currency=kwargs["currency"],
            email=kwargs["email"],
            fullName=kwargs["full_name"],
            paymentReference=payment_reference,
            callbackUrl=order.callback_url,
            country=kwargs.get("country", "NG"),
            productId=kwargs.get("product_id", ""),
            productDescription=kwargs.get("product_description", "")
        )
        
        # Update order with redirect URL
        order.redirect_url = payment_data["redirect_url"]
        order.save(ignore_permissions=True)
        
        return {
            "status": "success",
            "payment_reference": payment_reference,
            "redirect_url": payment_data["redirect_url"],
            "order_id": order.name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Order Creation Error")
        frappe.throw(_("Failed to create payment order: {0}").format(str(e)))


@frappe.whitelist(allow_guest=True)
def seerbit_webhook_handler():
    """Handle SeerBit webhook notifications"""
    try:
        # Get the request data
        webhook_data = frappe.local.form_dict
        
        # Verify webhook signature
        verify_webhook_signature()
        
        # Extract notification items
        notification_items = webhook_data.get("notificationItems", [])
        
        for item in notification_items:
            notification_request = item.get("notificationRequestItem", {})
            event_type = notification_request.get("eventType")
            event_data = notification_request.get("data", {})
            
            if event_type == "transaction":
                process_transaction_webhook(event_data)
            elif event_type == "refund":
                process_refund_webhook(event_data)
            # Add more event types as needed
        
        return {"status": "success", "message": "Webhook processed successfully"}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Webhook Error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist(allow_guest=True)
def seerbit_callback():
    """Handle SeerBit payment callback"""
    try:
        data = frappe.local.form_dict
        
        # Verify webhook signature if provided
        settings = frappe.get_doc("SeerBit Settings")
        
        # Process the callback
        if data.get("paymentReference"):
            # Update SeerBit Order
            if frappe.db.exists("SeerBit Order", {"payment_reference": data.get("paymentReference")}):
                order = frappe.get_doc("SeerBit Order", {"payment_reference": data.get("paymentReference")})
                order.gateway_reference = data.get("gatewayRef", "")
                order.gateway_message = data.get("message", "")
                order.status = "Paid" if data.get("transactionStatus") == "SUCCESSFUL" else "Failed"
                order.save(ignore_permissions=True)
        
        # Redirect based on status
        if data.get("transactionStatus") == "SUCCESSFUL":
            frappe.local.response["type"] = "redirect"
            redirect_url = "/seerbit_payment_success"
        else:
            frappe.local.response["type"] = "redirect"
            redirect_url = "/seerbit_payment_failed"
        
        frappe.local.response["location"] = redirect_url
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Callback Error")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/seerbit_payment_error"

# Extended SeerBit API integrations for ERPNext
@frappe.whitelist()
def create_invoice_payment_link(invoice_name):
    """Create SeerBit payment link for Sales Invoice"""
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    
    if invoice.outstanding_amount <= 0:
        frappe.throw(_("Invoice has no outstanding amount"))
    
    settings = frappe.get_doc("SeerBit Settings")
    if not settings.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    # Create payment URL
    payment_data = {
        "amount": invoice.outstanding_amount,
        "currency": invoice.currency,
        "payer_email": invoice.contact_email or "customer@example.com",
        "payer_name": invoice.customer_name,
        "reference_doctype": "Sales Invoice",
        "reference_docname": invoice.name,
        "callback_url": get_url("/api/method/payments.payment_gateways.seerbit_api.payment_callback"),
        "productId": f"INV-{invoice.name}",
        "productDescription": f"Payment for Invoice {invoice.name}"
    }
    
    result = settings.get_payment_url(**payment_data)
    
    # Update invoice with payment reference
    invoice.db_set("seerbit_payment_reference", result.get("reference"))
    
    return result

@frappe.whitelist()
def send_payment_link_email(invoice_name, customer_email):
    """Send payment link email to customer"""
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    
    # Get or create payment link
    if not invoice.seerbit_payment_reference:
        result = create_invoice_payment_link(invoice_name)
        payment_url = result.get("redirect_url")
    else:
        # Recreate payment link
        result = create_invoice_payment_link(invoice_name) 
        payment_url = result.get("redirect_url")
    
    # Send email
    frappe.sendmail(
        recipients=[customer_email],
        subject=f"Payment Link for Invoice {invoice.name}",
        message=f"""
        <p>Dear {invoice.customer_name},</p>
        <p>Please click the link below to pay for Invoice {invoice.name}:</p>
        <p><a href="{payment_url}" target="_blank">Pay Now - {frappe.utils.fmt_money(invoice.outstanding_amount, currency=invoice.currency)}</a></p>
        <p>Thank you for your business!</p>
        """,
        header="Payment Link"
    )
    
    return {"status": "success", "message": "Payment link sent successfully"}

@frappe.whitelist(allow_guest=True)
def payment_callback():
    """Handle SeerBit payment callback for invoices"""
    try:
        data = frappe.local.form_dict
        
        # Verify payment
        settings = frappe.get_doc("SeerBit Settings")
        payment_data = settings.verify_payment(data.get("paymentReference"))
        
        if payment_data.get("transactionStatus") == "SUCCESSFUL":
            # Find related invoice
            invoice_name = data.get("productId", "").replace("INV-", "")
            if frappe.db.exists("Sales Invoice", invoice_name):
                create_payment_entry_from_callback(invoice_name, payment_data)
                
                frappe.local.response["type"] = "redirect"
                frappe.local.response["location"] = "/payment-success"
            else:
                frappe.log_error("Invoice not found for payment callback", "SeerBit Payment Error")
                frappe.local.response["type"] = "redirect" 
                frappe.local.response["location"] = "/payment-error"
        else:
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/payment-failed"
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Payment Callback Error")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-error"

def create_payment_entry_from_callback(invoice_name, payment_data):
    """Create Payment Entry from successful SeerBit payment"""
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    
    # Create Payment Entry
    payment_entry = frappe.new_doc("Payment Entry")
    payment_entry.payment_type = "Receive"
    payment_entry.party_type = "Customer"
    payment_entry.party = invoice.customer
    payment_entry.posting_date = nowdate()
    payment_entry.paid_from = invoice.debit_to
    
    # Get default cash/bank account
    company = frappe.get_doc("Company", invoice.company)
    payment_entry.paid_to = company.default_cash_account or company.default_bank_account
    
    payment_entry.paid_amount = float(payment_data.get("amount", 0))
    payment_entry.received_amount = payment_entry.paid_amount
    payment_entry.reference_no = payment_data.get("transactionRef")
    payment_entry.reference_date = nowdate()
    payment_entry.mode_of_payment = "SeerBit"
    
    # Link to invoice
    payment_entry.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": invoice.name,
        "allocated_amount": payment_entry.paid_amount
    })
    
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()
    
    # Update invoice status
    invoice.db_set("seerbit_payment_status", "Paid")
    
    return payment_entry


def verify_webhook_signature():
    """Verify webhook signature for security"""
    try:
        # Get signature from headers
        signature = frappe.get_request_header("X-SeerBit-Signature")
        
        if not signature:
            frappe.throw(_("Webhook signature not found"))
        
        # Get webhook secret
        settings = frappe.get_doc("SeerBit Settings")
        webhook_secret = get_decrypted_password("SeerBit Settings", "SeerBit Settings", "webhook_secret")
        
        if not webhook_secret:
            frappe.throw(_("Webhook secret not configured"))
        
        # Get request payload
        payload = frappe.request.get_data()
        
        # Calculate expected signature
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        if not hmac.compare_digest(signature, expected_signature):
            frappe.throw(_("Invalid webhook signature"))
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Signature Verification Error")
        frappe.throw(_("Webhook signature verification failed"))


def process_transaction_webhook(data):
    """Process transaction webhook notification"""
    payment_reference = data.get("reference")
    
    if not payment_reference:
        frappe.log_error("Payment reference not found in webhook data", "SeerBit Webhook")
        return
    
    try:
        # Get the order
        order = frappe.get_doc("SeerBit Order", payment_reference)
        
        # Update order from webhook data
        order.update_from_webhook_data({"data": data})
        
    except frappe.DoesNotExistError:
        frappe.log_error(f"SeerBit Order not found for reference: {payment_reference}", "SeerBit Webhook")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Transaction Webhook Error")


def process_refund_webhook(data):
    """Process refund webhook notification"""
    # Implement refund processing logic
    frappe.log_error(f"Refund webhook received: {json.dumps(data)}", "SeerBit Refund Webhook")


@frappe.whitelist()
def verify_seerbit_payment(payment_reference):
    """Manually verify a SeerBit payment"""
    try:
        settings = frappe.get_doc("SeerBit Settings")
        verification_result = settings.verify_payment(payment_reference)
        
        # Update order if exists
        try:
            order = frappe.get_doc("SeerBit Order", payment_reference)
            order.update_from_webhook_data({"data": verification_result["payments"]})
        except frappe.DoesNotExistError:
            pass
        
        return {
            "status": "success",
            "data": verification_result
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Verification Error")
        return {
            "status": "error",
            "message": str(e)
        }
