import frappe
from frappe import _

def get_context(context):
    """Get context for payment error page"""
    context.title = _("Payment Error")
    context.error_message = _("An error occurred while processing your payment. Please try again or contact support.")
    
    return context
#     context.description = _("An error occurred while processing your payment. Please try again or contact support.")
#     context.error = _("Payment processing error. Please try again or contact support.")
#     context.title = _("Payment Error")
#     context.error_message = _("An error occurred while processing your payment. Please try again or contact support.")
#     return context