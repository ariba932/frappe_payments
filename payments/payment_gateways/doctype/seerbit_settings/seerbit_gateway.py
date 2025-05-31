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
        request_log = create_request_log(
            doctype="SeerBit Order",
            reference_doctype=kwargs.get("reference_doctype"),
            reference_docname=kwargs.get("reference_docname"),
            request_data=kwargs
        )
        
        try:
            # Create payment order
            result = frappe.call(
                "payments.payment_gateways.api.create_seerbit_order",
                **kwargs
            )
            
            # Update request log
            request_log.db_set("status", "Initiated")
            request_log.db_set("response_data", frappe.as_json(result))
            
            return result
            
        except Exception as e:
            # Update request log with error
            request_log.db_set("status", "Failed")
            request_log.db_set("error", str(e))
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


def get_gateway():
    """Factory function to get SeerBit gateway instance"""
    return SeerBitGateway()
