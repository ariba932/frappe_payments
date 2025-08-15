# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe

no_cache = True


def get_context(context):
	"""SeerBit-specific payment success page"""
	form_dict = frappe.local.form_dict
	
	# Get payment reference and status from URL parameters
	payment_reference = form_dict.get("ref", "Unknown")
	status = form_dict.get("status", "unknown")
	
	# Set context based on payment status
	if status == "success":
		context["page_title"] = "Payment Successful"
		context["status_class"] = "success"
		context["status_icon"] = "check-circle"
		context["payment_message"] = f"Your payment has been processed successfully!"
		context["reference_message"] = f"Payment Reference: {payment_reference}"
		context["next_action"] = "You can now close this window or continue shopping."
		context["show_continue"] = True
	elif status == "failed":
		context["page_title"] = "Payment Failed"
		context["status_class"] = "danger"
		context["status_icon"] = "x-circle"
		context["payment_message"] = "Payment could not be processed."
		context["reference_message"] = f"Reference: {payment_reference}"
		context["next_action"] = "Please try again or contact support if the problem persists."
		context["show_retry"] = True
	else:
		context["page_title"] = "Payment Status"
		context["status_class"] = "warning"
		context["status_icon"] = "alert-circle"
		context["payment_message"] = "Payment status is being processed."
		context["reference_message"] = f"Reference: {payment_reference}"
		context["next_action"] = "Please wait while we confirm your payment status."
		context["show_contact"] = True
	
	# Add payment reference for any additional processing
	context["payment_reference"] = payment_reference
	context["payment_status"] = status
	
	# Check if there's a linked SeerBit Order to get more details
	try:
		if payment_reference and payment_reference != "Unknown":
			order = frappe.get_value("SeerBit Order", 
				{"payment_reference": payment_reference}, 
				["name", "amount", "currency", "customer_name", "meta_data"], 
				as_dict=True
			)
			
			if order:
				context["order_details"] = order
				meta_data = frappe.parse_json(order.get("meta_data", "{}"))
				context["linked_document"] = meta_data.get("invoice_name") or meta_data.get("sales_order_name")
	except Exception as e:
		frappe.log_error(f"Error fetching order details for {payment_reference}: {str(e)}", "SeerBit Payment Status")
