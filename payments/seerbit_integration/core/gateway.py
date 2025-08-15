# -*- coding: utf-8 -*-
"""
SeerBit Gateway - Main interface for SeerBit payment gateway integration
Replaces the scattered gateway logic with a unified interface
"""

import frappe
from frappe import _
from payments.utils import create_request_log
from .api_client import get_api_client


class SeerBitGateway:
    """Main SeerBit gateway for payment processing"""
    
    def __init__(self):
        from .api_client import get_seerbit_settings
        self.settings = get_seerbit_settings()
        self.api_client = get_api_client(self.settings)
        
        if not self.settings.is_enabled:
            frappe.throw(_("SeerBit payment gateway is not enabled"))
    
    def validate_transaction_currency(self, currency):
        """Validate if currency is supported"""
        if not hasattr(self.settings, 'supported_currencies'):
            supported_currencies = ["NGN", "USD", "GBP", "EUR"]
        else:
            supported_currencies = [c.strip() for c in str(self.settings.supported_currencies).split(',') if c.strip()]
        
        if currency not in supported_currencies:
            frappe.throw(_("Currency {0} is not supported by SeerBit").format(currency))
    
    def create_payment_request(self, **kwargs):
        """Create payment request and return checkout URL"""
        # Validate required parameters
        required_params = ["amount", "currency", "email", "full_name"]
        for param in required_params:
            if not kwargs.get(param):
                frappe.throw(_("Missing required parameter: {0}").format(param))
        
        # Validate currency
        self.validate_transaction_currency(kwargs["currency"])
        
        # Generate unique payment reference
        payment_reference = kwargs.get("payment_reference") or frappe.generate_hash(length=20)
        kwargs["payment_reference"] = payment_reference
        
        # Create request log
        request_log_name = create_request_log(
            data=kwargs,
            integration_type="SeerBit",
            service_name="Payment Creation"
        )
        
        try:
            # Create SeerBit Order record first
            order = self._create_order_record(kwargs, payment_reference)
            
            # Create payment with SeerBit API
            payment_result = self.api_client.create_payment(**kwargs)
            
            # Update order with payment details
            order.redirect_url = payment_result["redirectLink"]
            order.gateway_reference = payment_result.get("paymentReference", payment_reference)
            order.save(ignore_permissions=True)
            
            # Update request log
            if request_log_name:
                frappe.db.set_value("Integration Request", request_log_name, "status", "Completed")
                frappe.db.set_value("Integration Request", request_log_name, "output", frappe.as_json(payment_result))
            
            return {
                "status": "success",
                "payment_reference": payment_reference,
                "redirect_url": payment_result["redirectLink"],
                "order_id": order.name,
                "payment_status": payment_result.get("paymentStatus", "PENDING")
            }
            
        except Exception as e:
            # Update request log with error
            if request_log_name:
                frappe.db.set_value("Integration Request", request_log_name, "status", "Failed")
                frappe.db.set_value("Integration Request", request_log_name, "error", str(e))
            
            frappe.log_error(frappe.get_traceback(), "SeerBit Payment Creation Error")
            frappe.throw(_("Failed to create payment: {0}").format(str(e)))
    
    def verify_payment(self, payment_reference):
        """Verify payment status with SeerBit"""
        try:
            verification_result = self.api_client.verify_payment(payment_reference)
            
            # Update local order if exists
            self._update_order_from_verification(payment_reference, verification_result)
            
            return verification_result
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Payment Verification Error for {payment_reference}")
            frappe.throw(_("Payment verification failed: {0}").format(str(e)))
    
    def process_webhook(self, webhook_data):
        """Process webhook notification"""
        from .webhooks import SeerBitWebhookHandler
        
        webhook_handler = SeerBitWebhookHandler(self.settings)
        return webhook_handler.process_webhook(webhook_data)
    
    def _create_order_record(self, payment_data, payment_reference):
        """Create SeerBit Order record for tracking"""
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": payment_reference,
            "amount": float(payment_data["amount"]),
            "currency": payment_data["currency"],
            "customer_email": payment_data["email"],
            "customer_name": payment_data["full_name"],
            "customer_mobile": payment_data.get("mobile", ""),
            "callback_url": payment_data.get("callback_url", ""),
            "status": "Pending",
            "meta_data": frappe.as_json({
                "product_id": payment_data.get("productId", ""),
                "product_description": payment_data.get("productDescription", ""),
                "country": payment_data.get("country", "NG"),
                "created_via": "Gateway"
            })
        })
        order.insert(ignore_permissions=True)
        return order
    
    def _update_order_from_verification(self, payment_reference, verification_data):
        """Update order record from verification data"""
        if frappe.db.exists("SeerBit Order", {"payment_reference": payment_reference}):
            order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
            
            transaction_status = verification_data.get("transactionStatus", "UNKNOWN")
            
            if transaction_status == "SUCCESSFUL":
                order.status = "Paid"
            elif transaction_status == "FAILED":
                order.status = "Failed"
            else:
                order.status = "Processing"
            
            order.gateway_reference = verification_data.get("transactionRef", order.gateway_reference)
            order.gateway_message = verification_data.get("message", "")
            order.transaction_id = verification_data.get("transactionId", "")
            order.save(ignore_permissions=True)


# Factory function and API endpoints
def get_gateway():
    """Factory function to get SeerBit gateway instance"""
    return SeerBitGateway()


@frappe.whitelist()
def create_payment_request(**kwargs):
    """Whitelist wrapper for payment request creation"""
    gateway = get_gateway()
    return gateway.create_payment_request(**kwargs)


@frappe.whitelist()
def verify_payment_status(payment_reference):
    """Whitelist wrapper for payment verification"""
    gateway = get_gateway()
    return gateway.verify_payment(payment_reference)


@frappe.whitelist(allow_guest=True)
def process_webhook():
    """Whitelist wrapper for webhook processing"""
    gateway = get_gateway()
    webhook_data = frappe.local.form_dict
    return gateway.process_webhook(webhook_data)
