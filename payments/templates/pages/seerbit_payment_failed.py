import frappe
from frappe import _

def get_context(context):
    """Get context for payment failed page"""
    payment_reference = frappe.form_dict.get('reference')
    
    context.payment_reference = payment_reference
    context.title = _("Payment Failed")
    
    if payment_reference:
        try:
            # Get order details
            order = frappe.get_doc("SeerBit Order", payment_reference)
            context.order = order
            context.amount = order.amount
            context.currency = order.currency
            context.gateway_message = order.gateway_message
            context.failure_reason = order.gateway_message or _("Payment processing failed")
            
        except frappe.DoesNotExistError:
            context.error = _("Payment record not found")
    
    return context
#     context.description = _("Your payment was not successful. Please try again or contact support.")
#     context.error = _("Payment processing failed. Please try again or contact support.")
#         context.description = _("Your payment was not successful. Please try again or contact support.")
#         context.error = _("Payment processing failed. Please try again or contact support.")  