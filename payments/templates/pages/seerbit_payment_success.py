import frappe
from frappe import _

def get_context(context):
    """Get context for payment success page"""
    payment_reference = frappe.form_dict.get('reference')
    
    context.payment_reference = payment_reference
    context.title = _("Payment Successful")
    
    if payment_reference:
        try:
            # Get order details
            order = frappe.get_doc("SeerBit Order", payment_reference)
            context.order = order
            context.amount = order.amount
            context.currency = order.currency
            context.customer_name = order.customer_name
            context.gateway_reference = order.gateway_reference
            
        except frappe.DoesNotExistError:
            context.error = _("Payment record not found")
    
    return context
