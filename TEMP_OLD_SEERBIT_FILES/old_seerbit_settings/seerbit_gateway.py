#Seerbit Payment Gateway Integration
#         self.payment_reference = data.get("payment_reference", self.payment_reference)
#         self.status = data.get("status", self.status)
#         self.amount = data.get("amount", self.amount)
#         self.currency = data.get("currency", self.currency)
# -*- coding: utf-8 -*-
import frappe
from frappe import _
from payments.utils import create_request_log


class SeerBitGateway:
    """SeerBit Payment Gateway Integration"""
    
    def __init__(self, gateway_name="SeerBit"):
        self.gateway_name = gateway_name
        self.settings = frappe.get_doc("SeerBit Settings")
    
    def validate_transaction_currency(self, currency):
        """Validate if currency is supported"""
        supported_currencies = [c.strip() for c in self.settings.supported_currencies.split('\n') if c.strip()]
        
        if currency not in supported_currencies:
            frappe.throw(_("Currency {0} is not supported by SeerBit").format(currency))
    
    def get_payment_url(self, **kwargs):
        """Get payment URL for checkout"""
        # Validate currency
        self.validate_transaction_currency(kwargs.get("currency"))
        
        # Create request log
        request_log_name = create_request_log(
            data=kwargs,
            integration_type="SeerBit",
            service_name="Payment URL Generation"
        )
        
        try:
            # Create payment order
            result = frappe.call(
                "payments.payment_gateways.api.create_seerbit_order",
                **kwargs
            )
            
            # Update request log
            if request_log_name:
                frappe.db.set_value("Integration Request", request_log_name, "status", "Completed")
                frappe.db.set_value("Integration Request", request_log_name, "output", frappe.as_json(result))
            
            return result
            
        except Exception as e:
            # Update request log with error
            if request_log_name:
                frappe.db.set_value("Integration Request", request_log_name, "status", "Failed")
                frappe.db.set_value("Integration Request", request_log_name, "error", str(e))
            raise
    
    def process_webhook(self, webhook_data):
        """Process webhook notification"""
        return frappe.call(
            "payments.payment_gateways.api.seerbit_webhook_handler",
            webhook_data=webhook_data
        )
    
    def verify_payment(self, payment_reference):
        """Verify payment status"""
        return frappe.call(
            "payments.payment_gateways.api.verify_seerbit_payment",
            payment_reference=payment_reference
        )
    
    def generate_payment_link(self, **kwargs):
        """Generate payment link for Sales Invoice or Sales Order"""
        try:
            # Import enhanced checkout handler
            from payments.payment_gateways.seerbit_checkout_enhanced import SeerBitStandardCheckoutEnhanced
            
            # Get SeerBit settings
            settings = frappe.get_doc("SeerBit Settings")
            if not settings.is_enabled:
                frappe.throw(_("SeerBit is not enabled"))
            
            # Initialize enhanced checkout
            checkout = SeerBitStandardCheckoutEnhanced(settings)
            
            # Determine document type and call appropriate method
            reference_doctype = kwargs.get("reference_doctype")
            reference_docname = kwargs.get("reference_docname")
            
            if reference_doctype == "Sales Invoice":
                return frappe.call(
                    "payments.payment_gateways.seerbit_checkout_enhanced.create_invoice_payment_request",
                    invoice_name=reference_docname
                )
            elif reference_doctype == "Sales Order":
                advance_percentage = kwargs.get("advance_percentage", 50)
                return frappe.call(
                    "payments.payment_gateways.seerbit_checkout_enhanced.create_sales_order_payment_request",
                    sales_order_name=reference_docname,
                    advance_percentage=advance_percentage
                )
            else:
                frappe.throw(_("Document type {0} is not supported for SeerBit payments").format(reference_doctype))
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"SeerBit Payment Link Generation Error")
            frappe.throw(_("Failed to generate payment link: {0}").format(str(e)))


def get_gateway():
    """Factory function to get SeerBit gateway instance"""
    return SeerBitGateway()

@frappe.whitelist()
def generate_payment_link(**kwargs):
    """Whitelist wrapper for generate_payment_link"""
    gateway = get_gateway()
    return gateway.generate_payment_link(**kwargs)
