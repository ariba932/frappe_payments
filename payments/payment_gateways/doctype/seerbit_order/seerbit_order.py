#Seerbit Order Document --- via SeerBit Order doctype
#         "before_insert": "payments.payment_gateways.doctype.seerbit_order.seerbit_order.SeerBitOrder.before_insert",
#         "on_update": "payments.payment_gateways.doctype.seerbit_order.seerbit_order.SeerBitOrder.on_update",
#         "on_payment_captured": "payments.payment_gateways.doctype.seerbit_order.seerbit_order.SeerBitOrder.on_payment_success",
#         "on_payment_failed": "payments.payment_gateways.doctype.seerbit_order.seerbit_order.SeerBitOrder.on_payment_failure",
# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
import json


class SeerBitOrder(Document):
    def before_insert(self):
        self.created_at = frappe.utils.now()
    
    def on_update(self):
        self.updated_at = frappe.utils.now()
        
        # Handle status changes
        if self.has_value_changed("status"):
            self.handle_status_change()
    
    def handle_status_change(self):
        """Handle payment status changes and trigger appropriate actions"""
        if self.status == "Paid":
            self.on_payment_success()
        elif self.status == "Failed":
            self.on_payment_failure()
    
    def on_payment_success(self):
        """Actions to perform when payment is successful"""
        # You can override this method in your custom app
        # Example: Send confirmation email, update related documents, etc.
        
        # Log the successful payment
        frappe.log_error(
            f"SeerBit payment successful for reference: {self.payment_reference}",
            "SeerBit Payment Success"
        )
        
        # Emit a custom event that other apps can listen to
        self.run_method("on_payment_captured")
    
    def on_payment_failure(self):
        """Actions to perform when payment fails"""
        # Log the failed payment
        frappe.log_error(
            f"SeerBit payment failed for reference: {self.payment_reference}. "
            f"Gateway message: {self.gateway_message}",
            "SeerBit Payment Failure"
        )
        
        # Emit a custom event that other apps can listen to
        self.run_method("on_payment_failed")
    
    def update_from_webhook_data(self, webhook_data):
        """Update order from webhook notification data"""
        data = webhook_data.get("data", {})
        
        # Update payment details
        self.gateway_reference = data.get("gatewayReference")
        self.gateway_message = data.get("gatewayMessage")
        self.gateway_code = data.get("gatewayCode") or data.get("code")
        self.payment_type = data.get("paymentType")
        self.channel_type = data.get("channelType")
        
        # Update customer details if not already set
        if not self.customer_email:
            self.customer_email = data.get("email")
        if not self.customer_name:
            self.customer_name = data.get("fullname")
        if not self.customer_mobile:
            self.customer_mobile = data.get("mobile")
        
        # Update status based on gateway response
        if data.get("gatewayCode") == "00" or data.get("code") == "00":
            self.status = "Paid"
        else:
            self.status = "Failed"
        
        # Store additional metadata
        self.meta_data = json.dumps(data, indent=2)
        
        self.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.publish_realtime(
            event="seerbit_order_updated",
            message={"order": self.as_dict()},
            user=self.owner
        )
        frappe.log_error(
            f"SeerBit order updated from webhook: {self.name}",
            "SeerBit Order Update"
        )