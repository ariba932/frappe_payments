# -*- coding: utf-8 -*-
"""
SeerBit Webhook Handler - Centralized webhook processing for all SeerBit events
Replaces multiple scattered webhook handlers
"""

import frappe
from frappe import _
import json
from frappe.utils import nowdate


class SeerBitWebhookHandler:
    """Centralized webhook handler for all SeerBit events"""
    
    def __init__(self, settings_doc):
        self.settings = settings_doc
    
    def process_webhook(self, webhook_data):
        """Process incoming webhook notification"""
        try:
            # Verify webhook signature if configured
            if self.settings.get("webhook_secret"):
                self._verify_webhook_signature()
            
            # Log webhook for debugging
            self._log_webhook(webhook_data)
            
            # Process different types of notifications
            notification_items = webhook_data.get("notificationItems", [])
            if not notification_items and webhook_data.get("data"):
                # Handle direct webhook format
                return self._process_direct_webhook(webhook_data)
            
            # Process notification items format
            results = []
            for item in notification_items:
                notification_request = item.get("notificationRequestItem", {})
                event_type = notification_request.get("eventType")
                event_data = notification_request.get("data", {})
                
                result = self._process_event_by_type(event_type, event_data)
                results.append(result)
            
            return {
                "status": "success",
                "message": "Webhook processed successfully",
                "processed_events": len(results),
                "results": results
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SeerBit Webhook Processing Error")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _process_direct_webhook(self, webhook_data):
        """Process direct webhook format (simple payment callback)"""
        data = webhook_data.get("data", webhook_data)
        payment_reference = data.get("paymentReference") or data.get("reference")
        
        if not payment_reference:
            frappe.log_error("No payment reference found in webhook", "SeerBit Webhook Error")
            return {"status": "error", "message": "No payment reference found"}
        
        # Update order status
        self._update_order_from_webhook(payment_reference, data)
        
        # Process payment completion if successful
        if data.get("transactionStatus") == "SUCCESSFUL":
            self._process_successful_payment(payment_reference, data)
        
        return {"status": "success", "payment_reference": payment_reference}
    
    def _process_event_by_type(self, event_type, event_data):
        """Process webhook event based on type"""
        if event_type == "transaction":
            return self._process_transaction_event(event_data)
        elif event_type == "payout":
            return self._process_payout_event(event_data)
        elif event_type == "refund":
            return self._process_refund_event(event_data)
        else:
            frappe.log_error(f"Unknown webhook event type: {event_type}", "SeerBit Webhook")
            return {"status": "ignored", "event_type": event_type}
    
    def _process_transaction_event(self, event_data):
        """Process transaction webhook event"""
        payment_reference = event_data.get("reference") or event_data.get("paymentReference")
        
        if not payment_reference:
            return {"status": "error", "message": "No payment reference in transaction event"}
        
        try:
            # Update order from webhook data
            self._update_order_from_webhook(payment_reference, event_data)
            
            # Process successful payment
            if event_data.get("transactionStatus") == "SUCCESSFUL":
                self._process_successful_payment(payment_reference, event_data)
            
            return {"status": "success", "payment_reference": payment_reference}
            
        except Exception as e:
            frappe.log_error(f"Transaction event processing failed: {str(e)}", "SeerBit Webhook")
            return {"status": "error", "message": str(e)}
    
    def _process_payout_event(self, event_data):
        """Process payout webhook event"""
        payout_reference = event_data.get("reference")
        
        if not payout_reference:
            return {"status": "error", "message": "No payout reference in event"}
        
        try:
            # Update payout status
            if frappe.db.exists("SeerBit Payout", {"payout_reference": payout_reference}):
                payout = frappe.get_doc("SeerBit Payout", {"payout_reference": payout_reference})
                
                payout_status = event_data.get("status", "").upper()
                if payout_status == "SUCCESSFUL":
                    payout.status = "Paid"
                elif payout_status == "FAILED":
                    payout.status = "Failed"
                else:
                    payout.status = "Processing"
                
                payout.gateway_response = frappe.as_json(event_data)
                payout.save(ignore_permissions=True)
            
            return {"status": "success", "payout_reference": payout_reference}
            
        except Exception as e:
            frappe.log_error(f"Payout event processing failed: {str(e)}", "SeerBit Webhook")
            return {"status": "error", "message": str(e)}
    
    def _process_refund_event(self, event_data):
        """Process refund webhook event"""
        # Implement refund processing logic
        refund_reference = event_data.get("reference")
        frappe.log_error(f"Refund webhook received: {json.dumps(event_data)}", "SeerBit Refund Webhook")
        
        return {"status": "processed", "refund_reference": refund_reference}
    
    def _update_order_from_webhook(self, payment_reference, webhook_data):
        """Update SeerBit Order from webhook data"""
        if frappe.db.exists("SeerBit Order", {"payment_reference": payment_reference}):
            order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
            
            transaction_status = webhook_data.get("transactionStatus", "").upper()
            
            if transaction_status == "SUCCESSFUL":
                order.status = "Paid"
            elif transaction_status == "FAILED":
                order.status = "Failed"
            else:
                order.status = "Processing"
            
            order.gateway_reference = webhook_data.get("gatewayRef") or webhook_data.get("transactionRef", order.gateway_reference)
            order.gateway_message = webhook_data.get("message", "")
            order.transaction_id = webhook_data.get("transactionId", "")
            order.save(ignore_permissions=True)
    
    def _process_successful_payment(self, payment_reference, payment_data):
        """Process successful payment and create payment entries"""
        try:
            # Check if this is linked to an invoice or sales order
            order = frappe.get_doc("SeerBit Order", {"payment_reference": payment_reference})
            meta_data = frappe.parse_json(order.meta_data or "{}")
            
            # Process invoice payment
            if meta_data.get("invoice_name"):
                from ..selling.invoice_payments import process_invoice_payment_completion
                process_invoice_payment_completion(order.name, payment_data)
            
            # Process sales order advance payment
            elif meta_data.get("sales_order_name"):
                from ..selling.sales_order_payments import process_sales_order_payment_completion
                process_sales_order_payment_completion(order.name, payment_data)
            
            # Process general payment
            else:
                frappe.log_error(f"Payment completed but no linked document found for {payment_reference}", "SeerBit Payment")
                
        except Exception as e:
            frappe.log_error(f"Error processing successful payment {payment_reference}: {str(e)}", "SeerBit Payment Processing")
    
    def _verify_webhook_signature(self):
        """Verify webhook signature for security"""
        try:
            signature = frappe.get_request_header("X-SeerBit-Signature")
            if not signature:
                frappe.throw(_("Webhook signature not found"))
            
            payload = frappe.request.get_data()
            webhook_secret = self.settings.get_password("webhook_secret")
            
            if not webhook_secret:
                frappe.throw(_("Webhook secret not configured"))
            
            from .api_client import get_api_client
            api_client = get_api_client(self.settings)
            
            if not api_client.verify_webhook_signature(payload, signature):
                frappe.throw(_("Invalid webhook signature"))
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SeerBit Webhook Signature Verification Error")
            frappe.throw(_("Webhook signature verification failed: {0}").format(str(e)))
    
    def _log_webhook(self, webhook_data):
        """Log webhook for debugging and audit trail"""
        try:
            log_doc = frappe.get_doc({
                "doctype": "Integration Request",
                "integration_type": "SeerBit",
                "integration_request_service": "Webhook",
                "data": frappe.as_json(webhook_data),
                "status": "Completed"
            })
            log_doc.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to log webhook: {str(e)}", "SeerBit Webhook Logging")


# API endpoints for webhook handling
@frappe.whitelist(allow_guest=True)
def payment_callback():
    """Handle payment callback from SeerBit"""
    try:
        data = frappe.local.form_dict
        # Log callback with shorter title to avoid length exceeded error
        frappe.log_error(f"Code: {data.get('code')}, Ref: {data.get('reference')}", "SeerBit Callback")
        
        # Use SeerBitAPIClient to get settings instead of importing function
        from .api_client import SeerBitAPIClient
        client = SeerBitAPIClient()
        settings = client.settings
        
        # Map SeerBit callback parameters to our expected format
        # SeerBit sends: code, message, reference, linkingreference
        # We need: transactionStatus, paymentReference
        mapped_data = {
            "transactionStatus": "SUCCESSFUL" if data.get("code") == "00" else "FAILED",
            "paymentReference": data.get("reference"),
            "message": data.get("message", ""),
            "gatewayRef": data.get("linkingreference", ""),
            "transactionRef": data.get("linkingreference", ""),
            "code": data.get("code", ""),
            "originalData": data  # Keep original for debugging
        }
        
        webhook_handler = SeerBitWebhookHandler(settings)
        
        # Process the callback with mapped data
        result = webhook_handler._process_direct_webhook({"data": mapped_data})
        
        # Redirect based on status
        payment_reference = data.get("reference")
        code = data.get("code")
        
        if code == "00":  # Successful transaction
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = f"/seerbit_payment_status?ref={payment_reference}&status=success"
        else:  # Failed transaction
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = f"/seerbit_payment_status?ref={payment_reference}&status=failed"
        
        return result
        
    except Exception as e:
        # Log error with shorter title
        frappe.log_error(f"Callback error: {str(e)[:80]}", "SeerBit Callback Error")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/seerbit_payment_status?status=error"


@frappe.whitelist(allow_guest=True)
def webhook_handler():
    """Main webhook endpoint for SeerBit notifications"""
    try:
        webhook_data = frappe.local.form_dict
        # Use SeerBitAPIClient to get settings instead of importing function
        from .api_client import SeerBitAPIClient
        client = SeerBitAPIClient()
        settings = client.settings
        webhook_handler = SeerBitWebhookHandler(settings)
        
        return webhook_handler.process_webhook(webhook_data)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Webhook Handler Error")
        return {"status": "error", "message": str(e)}
