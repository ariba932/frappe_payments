# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now


class SeerBitSettings(Document):
	def validate(self):
		"""Validate SeerBit settings"""
		if self.is_active and not self.public_key:
			frappe.throw("Public Key is required when SeerBit is active")
		
		if self.is_active and not self.secret_key:
			frappe.throw("Secret Key is required when SeerBit is active")
			
		if self.enable_payouts and not self.pocket_id:
			frappe.throw("Pocket ID is required when payouts are enabled")


def on_payment_captured(doc, method):
	"""Handle payment captured event for SeerBit Order"""
	try:
		# Update payment status
		doc.db_set("status", "Completed")
		doc.db_set("payment_captured_at", now())
		
		# Process the completion based on the document type
		meta_data = frappe.parse_json(doc.meta_data or "{}")
		document_type = meta_data.get("document_type")
		
		if document_type == "Sales Invoice":
			from payments.seerbit_integration.selling.invoice_payments import process_invoice_payment_completion
			process_invoice_payment_completion(doc.name, meta_data)
		elif document_type == "Sales Order":
			from payments.seerbit_integration.selling.invoice_payments import process_sales_order_payment_completion
			process_sales_order_payment_completion(doc.name, meta_data)
		
		frappe.log_error(f"SeerBit payment captured for order {doc.name}", "SeerBit Payment Captured")
		
	except Exception as e:
		frappe.log_error(f"Error processing payment captured for {doc.name}: {str(e)}", "SeerBit Payment Error")


def on_payment_failed(doc, method):
	"""Handle payment failed event for SeerBit Order"""
	try:
		# Update payment status
		doc.db_set("status", "Failed")
		doc.db_set("payment_failed_at", now())
		
		# Update related document status
		meta_data = frappe.parse_json(doc.meta_data or "{}")
		document_type = meta_data.get("document_type")
		
		if document_type == "Sales Invoice" and meta_data.get("invoice_name"):
			invoice = frappe.get_doc("Sales Invoice", meta_data["invoice_name"])
			invoice.db_set("seerbit_payment_status", "Failed")
		elif document_type == "Sales Order" and meta_data.get("sales_order_name"):
			sales_order = frappe.get_doc("Sales Order", meta_data["sales_order_name"])
			sales_order.db_set("custom_seerbit_last_payment_status", "Failed")
		
		frappe.log_error(f"SeerBit payment failed for order {doc.name}", "SeerBit Payment Failed")
		
	except Exception as e:
		frappe.log_error(f"Error processing payment failure for {doc.name}: {str(e)}", "SeerBit Payment Error")
