# Enhanced SeerBit Standard Checkout Implementation
# Correcting parameter mapping and adding missing features

import frappe
from frappe import _
from frappe.utils import get_url, nowdate, get_request_site_address
import requests
import json

class SeerBitStandardCheckoutEnhanced:
    """
    Enhanced SeerBit Standard Checkout implementation fixing parameter mapping
    and adding missing features as per official documentation
    """
    
    def __init__(self, settings_doc):
        self.settings = settings_doc
        self.base_url = "https://seerbitapi.com" if not settings_doc.sandbox_mode else "https://sandbox.seerbitapi.com"
    
    def create_payment_request_enhanced(self, **kwargs):
        """
        Enhanced payment request creation following exact SeerBit Standard Checkout specs
        
        Required Parameters:
        - amount (string): Payment amount
        - currency (string): Payment currency (NGN, USD, etc.)
        - email (string): Customer email
        - fullName (string): Customer full name
        - paymentReference (string): Unique payment reference
        
        Optional Parameters:
        - country (string): Default "NG"
        - tokenize (string): Default "false"
        - callbackUrl (string): URL for payment completion redirect
        - productId (string): Product identifier
        - productDescription (string): Product description
        """
        
        # Validate required parameters per SeerBit documentation
        required_params = ["amount", "currency", "email", "fullName", "paymentReference"]
        for param in required_params:
            if not kwargs.get(param):
                frappe.throw(_("Missing required parameter: {0}").format(param))
        
        # Get encrypted key for authentication
        encrypted_key = self.settings.get_encrypted_key()
        
        # Prepare payment data exactly as per SeerBit documentation
        payment_data = {
            "publicKey": self.settings.public_key,
            "amount": str(kwargs["amount"]),  # Must be string per docs
            "currency": kwargs["currency"],
            "country": kwargs.get("country", "NG"),
            "paymentReference": kwargs["paymentReference"],
            "email": kwargs["email"],
            "fullName": kwargs["fullName"],
            "tokenize": kwargs.get("tokenize", "false"),
            "callbackUrl": kwargs.get("callbackUrl", self._get_default_callback_url())
        }
        
        # Add optional fields if provided
        if kwargs.get("productId"):
            payment_data["productId"] = kwargs["productId"]
        if kwargs.get("productDescription"):
            payment_data["productDescription"] = kwargs["productDescription"]
        
        # API call to SeerBit
        url = f"{self.base_url}/api/v2/payments"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {encrypted_key}"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payment_data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "SUCCESS":
                    payment_info = result["data"]["payments"]
                    return {
                        "status": "success",
                        "redirect_url": payment_info["redirectLink"],
                        "payment_status": payment_info["paymentStatus"],
                        "payment_reference": kwargs["paymentReference"],
                        "gateway_response": result
                    }
                else:
                    frappe.log_error(str(result), "SeerBit Payment Creation Failure")
                    frappe.throw(_("Payment creation failed: {0}").format(result.get("message", "Unknown error")))
            else:
                frappe.log_error(f"HTTP {response.status_code}: {response.text}", "SeerBit Payment API Error")
                frappe.throw(_("Payment API request failed with status: {0}").format(response.status_code))
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SeerBit Payment Request Error")
            frappe.throw(_("Failed to create payment request: {0}").format(str(e)))
    
    def _get_default_callback_url(self):
        """Get default callback URL for payment completion"""
        return get_request_site_address(True) + "/api/method/payments.payment_gateways.seerbit_checkout_enhanced.payment_callback"

# Enhanced API methods for ERPNext integration
@frappe.whitelist()
def create_invoice_payment_request(invoice_name, include_charges=False):
    """
    Create SeerBit payment request for Sales Invoice with enhanced parameter mapping
    """
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    
    if invoice.outstanding_amount <= 0:
        frappe.throw(_("Invoice has no outstanding amount"))
    
    settings = frappe.get_doc("SeerBit Settings")
    if not settings.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    # Calculate amount (include charges if requested)
    payment_amount = invoice.outstanding_amount
    if include_charges:
        # Add transaction charges as per SeerBit documentation notes
        charge_percentage = settings.get("transaction_charge_percentage", 0)
        if charge_percentage > 0:
            payment_amount = payment_amount * (1 + charge_percentage / 100)
    
    # Generate unique payment reference
    payment_reference = f"INV-{invoice.name}-{frappe.generate_hash(length=8)}"
    
    checkout_handler = SeerBitStandardCheckoutEnhanced(settings)
    
    # Prepare payment request parameters
    payment_params = {
        "amount": payment_amount,
        "currency": invoice.currency,
        "email": invoice.contact_email or invoice.customer_email_id or "noreply@company.com",
        "fullName": invoice.customer_name,
        "paymentReference": payment_reference,
        "country": settings.get("default_country", "NG"),
        "productId": f"INV-{invoice.name}",
        "productDescription": f"Payment for Invoice {invoice.name}",
        "callbackUrl": get_request_site_address(True) + f"/api/method/payments.payment_gateways.seerbit_checkout_enhanced.invoice_payment_callback?invoice={invoice.name}"
    }
    
    try:
        result = checkout_handler.create_payment_request_enhanced(**payment_params)
        
        # Update invoice with payment details
        invoice.db_set("seerbit_payment_reference", payment_reference)
        invoice.db_set("seerbit_payment_link", result["redirect_url"])
        invoice.db_set("seerbit_payment_status", "Pending")
        
        # Create SeerBit Order record for tracking
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": payment_reference,
            "amount": payment_amount,
            "currency": invoice.currency,
            "customer_email": payment_params["email"],
            "customer_name": payment_params["fullName"],
            "callback_url": payment_params["callbackUrl"],
            "redirect_url": result["redirect_url"],
            "status": "Pending",
            "meta_data": frappe.as_json({
                "invoice_name": invoice.name,
                "original_amount": invoice.outstanding_amount,
                "includes_charges": include_charges,
                "gateway_response": result["gateway_response"]
            })
        })
        order.insert(ignore_permissions=True)
        
        return {
            "status": "success",
            "payment_reference": payment_reference,
            "redirect_url": result["redirect_url"],
            "order_id": order.name,
            "amount": payment_amount
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Invoice Payment Request Error for {invoice_name}")
        frappe.throw(_("Failed to create payment request: {0}").format(str(e)))

@frappe.whitelist()
def create_sales_order_payment_request(sales_order_name, advance_percentage=100):
    """
    Create SeerBit payment request for Sales Order (advance payment)
    """
    sales_order = frappe.get_doc("Sales Order", sales_order_name)
    
    if sales_order.advance_paid >= sales_order.grand_total:
        frappe.throw(_("Sales Order is already fully paid"))
    
    settings = frappe.get_doc("SeerBit Settings")
    if not settings.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    # Calculate advance amount
    remaining_amount = sales_order.grand_total - sales_order.advance_paid
    advance_amount = remaining_amount * (advance_percentage / 100)
    
    if advance_amount <= 0:
        frappe.throw(_("Invalid advance amount"))
    
    # Generate unique payment reference
    payment_reference = f"SO-{sales_order.name}-{frappe.generate_hash(length=8)}"
    
    checkout_handler = SeerBitStandardCheckoutEnhanced(settings)
    
    # Prepare payment request parameters
    payment_params = {
        "amount": advance_amount,
        "currency": sales_order.currency,
        "email": sales_order.contact_email or "noreply@company.com",
        "fullName": sales_order.customer_name,
        "paymentReference": payment_reference,
        "country": settings.get("default_country", "NG"),
        "productId": f"SO-{sales_order.name}",
        "productDescription": f"Advance payment for Sales Order {sales_order.name}",
        "callbackUrl": get_request_site_address(True) + f"/api/method/payments.payment_gateways.seerbit_checkout_enhanced.sales_order_payment_callback?sales_order={sales_order.name}"
    }
    
    try:
        result = checkout_handler.create_payment_request_enhanced(**payment_params)
        
        # Create SeerBit Order record for tracking
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": payment_reference,
            "amount": advance_amount,
            "currency": sales_order.currency,
            "customer_email": payment_params["email"],
            "customer_name": payment_params["fullName"],
            "callback_url": payment_params["callbackUrl"],
            "redirect_url": result["redirect_url"],
            "status": "Pending",
            "meta_data": frappe.as_json({
                "sales_order_name": sales_order.name,
                "advance_percentage": advance_percentage,
                "advance_amount": advance_amount,
                "gateway_response": result["gateway_response"]
            })
        })
        order.insert(ignore_permissions=True)
        
        return {
            "status": "success",
            "payment_reference": payment_reference,
            "redirect_url": result["redirect_url"],
            "order_id": order.name,
            "amount": advance_amount
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Sales Order Payment Request Error for {sales_order_name}")
        frappe.throw(_("Failed to create payment request: {0}").format(str(e)))

@frappe.whitelist(allow_guest=True)
def sales_order_payment_callback():
    """
    Enhanced callback handler for Sales Order advance payments
    """
    try:
        data = frappe.local.form_dict
        sales_order_name = data.get("sales_order")
        
        if not sales_order_name:
            frappe.log_error("Sales Order name missing in callback", "SeerBit Callback Error")
            return _redirect_to_error_page()
        
        # Verify payment with SeerBit
        payment_reference = data.get("paymentReference")
        if not payment_reference:
            frappe.log_error("Payment reference missing in callback", "SeerBit Callback Error")
            return _redirect_to_error_page()
        
        settings = frappe.get_doc("SeerBit Settings")
        verification_result = settings.verify_payment(payment_reference)
        
        if verification_result.get("transactionStatus") == "SUCCESSFUL":
            # Process successful advance payment
            sales_order = frappe.get_doc("Sales Order", sales_order_name)
            order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
            
            # Extract advance payment details
            meta_data = frappe.parse_json(order.meta_data)
            advance_amount = meta_data.get("advance_amount")
            advance_percentage = meta_data.get("advance_percentage")
            
            # Create Payment Entry for advance payment
            payment_entry = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": "Receive",
                "party_type": "Customer",
                "party": sales_order.customer,
                "paid_amount": advance_amount,
                "received_amount": advance_amount,
                "paid_to": _get_default_cash_account(sales_order.company),
                "paid_from": _get_default_receivable_account(sales_order.company),
                "reference_no": payment_reference,
                "reference_date": frappe.utils.nowdate(),
                "is_advance": "Yes",
                "party_balance": 0,  # Will be calculated automatically
                "remarks": f"SeerBit advance payment ({advance_percentage}%) for Sales Order {sales_order.name}",
                "custom_seerbit_payment_reference": payment_reference,
                "custom_seerbit_transaction_id": verification_result.get("transactionId"),
                "custom_payment_gateway": "SeerBit"
            })
            
            # Add advance payment reference to Sales Order
            payment_entry.append("references", {
                "reference_doctype": "Sales Order",
                "reference_name": sales_order.name,
                "allocated_amount": advance_amount
            })
            
            payment_entry.insert(ignore_permissions=True)
            payment_entry.submit()
            
            # Update SeerBit Order status
            order.status = "Completed"
            order.transaction_id = verification_result.get("transactionId")
            order.gateway_response = frappe.as_json(verification_result)
            order.payment_entry = payment_entry.name
            order.save(ignore_permissions=True)
            
            # Update Sales Order with advance payment info
            sales_order.db_set("custom_seerbit_last_payment_reference", payment_reference)
            sales_order.db_set("custom_seerbit_last_payment_status", "Completed")
            
            frappe.db.commit()
            
            # Redirect to success page
            return _redirect_to_success_page(
                title="Advance Payment Successful",
                message=f"Advance payment of {frappe.format_value(advance_amount, {'fieldtype': 'Currency'})} for Sales Order {sales_order.name} has been processed successfully.",
                reference=payment_reference
            )
        else:
            # Payment failed
            try:
                order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
                order.status = "Failed"
                order.gateway_response = frappe.as_json(verification_result)
                order.save(ignore_permissions=True)
                
                # Update Sales Order status
                sales_order = frappe.get_doc("Sales Order", sales_order_name)
                sales_order.db_set("custom_seerbit_last_payment_status", "Failed")
                
                frappe.db.commit()
            except:
                pass
            
            return _redirect_to_error_page(
                title="Payment Failed",
                message="Your advance payment could not be processed. Please try again or contact support.",
                reference=payment_reference
            )
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Sales Order Callback Error")
        return _redirect_to_error_page()

@frappe.whitelist(allow_guest=True)
def invoice_payment_callback():
    """
    Enhanced callback handler for invoice payments
    """
    try:
        data = frappe.local.form_dict
        invoice_name = data.get("invoice")
        
        if not invoice_name:
            frappe.log_error("Invoice name missing in callback", "SeerBit Callback Error")
            return _redirect_to_error_page()
        
        # Verify payment with SeerBit
        payment_reference = data.get("paymentReference")
        if not payment_reference:
            frappe.log_error("Payment reference missing in callback", "SeerBit Callback Error")
            return _redirect_to_error_page()
        
        settings = frappe.get_doc("SeerBit Settings")
        verification_result = settings.verify_payment(payment_reference)
        
        if verification_result.get("transactionStatus") == "SUCCESSFUL":
            # Process successful payment
            invoice = frappe.get_doc("Sales Invoice", invoice_name)
            
            # Create Payment Entry
            payment_entry = _create_payment_entry_for_invoice(invoice, verification_result)
            
            # Update invoice status
            invoice.db_set("seerbit_payment_status", "Paid")
            
            # Update SeerBit Order
            if frappe.db.exists("SeerBit Order", {"payment_reference": payment_reference}):
                order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
                order.status = "Paid"
                order.gateway_reference = verification_result.get("transactionRef")
                order.gateway_message = verification_result.get("message", "Payment successful")
                order.save(ignore_permissions=True)
            
            return _redirect_to_success_page(invoice_name, payment_entry.name)
        else:
            # Handle failed payment
            return _redirect_to_failure_page(invoice_name, verification_result.get("message", "Payment failed"))
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Invoice Callback Error")
        return _redirect_to_error_page()

@frappe.whitelist(allow_guest=True) 
def sales_order_payment_callback():
    """
    Enhanced callback handler for sales order advance payments
    """
    try:
        data = frappe.local.form_dict
        sales_order_name = data.get("sales_order")
        
        if not sales_order_name:
            frappe.log_error("Sales Order name missing in callback", "SeerBit Callback Error")
            return _redirect_to_error_page()
        
        # Verify payment with SeerBit
        payment_reference = data.get("paymentReference")
        if not payment_reference:
            frappe.log_error("Payment reference missing in callback", "SeerBit Callback Error")
            return _redirect_to_error_page()
        
        settings = frappe.get_doc("SeerBit Settings")
        verification_result = settings.verify_payment(payment_reference)
        
        if verification_result.get("transactionStatus") == "SUCCESSFUL":
            # Process successful advance payment
            sales_order = frappe.get_doc("Sales Order", sales_order_name)
            
            # Create Payment Entry for advance
            payment_entry = _create_advance_payment_entry(sales_order, verification_result)
            
            # Update SeerBit Order
            if frappe.db.exists("SeerBit Order", {"payment_reference": payment_reference}):
                order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
                order.status = "Paid"
                order.gateway_reference = verification_result.get("transactionRef")
                order.gateway_message = verification_result.get("message", "Payment successful")
                order.save(ignore_permissions=True)
            
            return _redirect_to_success_page(sales_order_name, payment_entry.name, doc_type="Sales Order")
        else:
            # Handle failed payment
            return _redirect_to_failure_page(sales_order_name, verification_result.get("message", "Payment failed"))
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Sales Order Callback Error")
        return _redirect_to_error_page()

def _create_payment_entry_for_invoice(invoice, payment_data):
    """Create Payment Entry for successful invoice payment"""
    payment_entry = frappe.new_doc("Payment Entry")
    payment_entry.payment_type = "Receive"
    payment_entry.party_type = "Customer"
    payment_entry.party = invoice.customer
    payment_entry.posting_date = nowdate()
    payment_entry.paid_from = invoice.debit_to
    
    # Get company's default cash/bank account
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
    
    return payment_entry

def _create_advance_payment_entry(sales_order, payment_data):
    """Create Payment Entry for advance payment against Sales Order"""
    payment_entry = frappe.new_doc("Payment Entry")
    payment_entry.payment_type = "Receive"
    payment_entry.party_type = "Customer" 
    payment_entry.party = sales_order.customer
    payment_entry.posting_date = nowdate()
    
    # Get customer's default receivable account
    customer = frappe.get_doc("Customer", sales_order.customer)
    payment_entry.paid_from = customer.get("accounts", [{"company": sales_order.company}])[0].get("account")
    
    # Get company's default cash/bank account
    company = frappe.get_doc("Company", sales_order.company)
    payment_entry.paid_to = company.default_cash_account or company.default_bank_account
    
    payment_entry.paid_amount = float(payment_data.get("amount", 0))
    payment_entry.received_amount = payment_entry.paid_amount
    payment_entry.reference_no = payment_data.get("transactionRef")
    payment_entry.reference_date = nowdate()
    payment_entry.mode_of_payment = "SeerBit"
    
    # Set as advance payment
    payment_entry.is_advance = "Yes"
    
    # Link to sales order for advance allocation
    payment_entry.append("references", {
        "reference_doctype": "Sales Order",
        "reference_name": sales_order.name,
        "allocated_amount": payment_entry.paid_amount
    })
    
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()
    
    return payment_entry

def _redirect_to_success_page(doc_name, payment_entry_name, doc_type="Sales Invoice"):
    """Redirect to success page with payment details"""
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"/seerbit_payment_success?doc={doc_name}&payment={payment_entry_name}&type={doc_type}"

def _redirect_to_failure_page(doc_name, message):
    """Redirect to failure page with error message"""
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"/seerbit_payment_failed?doc={doc_name}&message={message}"

def _redirect_to_error_page():
    """Redirect to generic error page"""
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = "/seerbit_payment_error"

# Utility methods for payment verification and management
@frappe.whitelist()
def verify_payment_status(payment_reference):
    """Verify payment status with SeerBit API"""
    settings = frappe.get_doc("SeerBit Settings")
    
    if not settings.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    try:
        verification_result = settings.verify_payment(payment_reference)
        
        # Update local order status if exists
        if frappe.db.exists("SeerBit Order", {"payment_reference": payment_reference}):
            order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
            
            if verification_result.get("transactionStatus") == "SUCCESSFUL" and order.status != "Paid":
                order.status = "Paid"
                order.gateway_reference = verification_result.get("transactionRef")
                order.save(ignore_permissions=True)
            elif verification_result.get("transactionStatus") == "FAILED" and order.status != "Failed":
                order.status = "Failed"
                order.gateway_message = verification_result.get("message", "Payment failed")
                order.save(ignore_permissions=True)
        
        return {
            "status": "success",
            "payment_status": verification_result.get("transactionStatus"),
            "amount": verification_result.get("amount"),
            "transaction_ref": verification_result.get("transactionRef"),
            "message": verification_result.get("message")
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Payment Verification Error for {payment_reference}")
        return {
            "status": "error",
            "message": str(e)
        }
