# -*- coding: utf-8 -*-
"""
SeerBit Selling Operations - Invoice and Sales Order Payment Processing
Consolidates all selling-related payment functionality
"""

import frappe
from frappe import _
from frappe.utils import nowdate, get_request_site_address
from ..core.api_client import get_api_client


class SeerBitSellingOperations:
    """Handles all selling operations - invoices and sales orders"""
    
    def __init__(self):
        self.settings = frappe.get_doc("SeerBit Settings")
        self.api_client = get_api_client(self.settings)
        
        if not self.settings.is_enabled:
            frappe.throw(_("SeerBit is not enabled"))
    
    def create_invoice_payment_link(self, invoice_name, include_charges=False):
        """Create payment link for Sales Invoice"""
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        if invoice.outstanding_amount <= 0:
            frappe.throw(_("Invoice has no outstanding amount"))
        
        # Calculate amount including charges if requested
        payment_amount = invoice.outstanding_amount
        if include_charges and self.settings.get("transaction_charge_percentage", 0) > 0:
            charge_percentage = self.settings.transaction_charge_percentage
            payment_amount = payment_amount * (1 + charge_percentage / 100)
        
        # Generate unique payment reference
        payment_reference = f"INV-{invoice.name}-{frappe.generate_hash(length=8)}"
        
        # Prepare payment parameters
        payment_params = {
            "amount": payment_amount,
            "currency": invoice.currency,
            "email": invoice.contact_email or invoice.customer_email_id or "noreply@company.com",
            "full_name": invoice.customer_name,
            "payment_reference": payment_reference,
            "country": self.settings.get("default_country", "NG"),
            "productId": f"INV-{invoice.name}",
            "productDescription": f"Payment for Invoice {invoice.name}",
            "callback_url": get_request_site_address(True) + f"/api/method/payments.seerbit_integration.core.webhooks.payment_callback?type=invoice&doc={invoice.name}"
        }
        
        try:
            # Create payment request
            payment_result = self.api_client.create_payment(**payment_params)
            
            # Create SeerBit Order record
            order = self._create_order_record(payment_params, payment_reference, {
                "invoice_name": invoice.name,
                "original_amount": invoice.outstanding_amount,
                "includes_charges": include_charges,
                "document_type": "Sales Invoice"
            })
            
            # Update order with payment details
            order.redirect_url = payment_result["redirectLink"]
            order.save(ignore_permissions=True)
            
            # Update invoice with payment reference
            invoice.db_set("seerbit_payment_reference", payment_reference)
            invoice.db_set("seerbit_payment_link", payment_result["redirectLink"])
            invoice.db_set("seerbit_payment_status", "Pending")
            
            return {
                "status": "success",
                "payment_reference": payment_reference,
                "redirect_url": payment_result["redirectLink"],
                "order_id": order.name,
                "amount": payment_amount
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Invoice Payment Link Error for {invoice_name}")
            frappe.throw(_("Failed to create payment link: {0}").format(str(e)))
    
    def create_sales_order_advance_payment(self, sales_order_name, advance_percentage=100):
        """Create advance payment request for Sales Order"""
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        
        if sales_order.advance_paid >= sales_order.grand_total:
            frappe.throw(_("Sales Order is already fully paid"))
        
        # Calculate advance amount
        remaining_amount = sales_order.grand_total - sales_order.advance_paid
        advance_amount = remaining_amount * (advance_percentage / 100)
        
        if advance_amount <= 0:
            frappe.throw(_("Invalid advance amount"))
        
        # Generate unique payment reference
        payment_reference = f"SO-{sales_order.name}-{frappe.generate_hash(length=8)}"
        
        # Prepare payment parameters
        payment_params = {
            "amount": advance_amount,
            "currency": sales_order.currency,
            "email": sales_order.contact_email or "noreply@company.com",
            "full_name": sales_order.customer_name,
            "payment_reference": payment_reference,
            "country": self.settings.get("default_country", "NG"),
            "productId": f"SO-{sales_order.name}",
            "productDescription": f"Advance payment for Sales Order {sales_order.name}",
            "callback_url": get_request_site_address(True) + f"/api/method/payments.seerbit_integration.core.webhooks.payment_callback?type=sales_order&doc={sales_order.name}"
        }
        
        try:
            # Create payment request
            payment_result = self.api_client.create_payment(**payment_params)
            
            # Create SeerBit Order record
            order = self._create_order_record(payment_params, payment_reference, {
                "sales_order_name": sales_order.name,
                "advance_percentage": advance_percentage,
                "advance_amount": advance_amount,
                "document_type": "Sales Order"
            })
            
            # Update order with payment details
            order.redirect_url = payment_result["redirectLink"]
            order.save(ignore_permissions=True)
            
            return {
                "status": "success",
                "payment_reference": payment_reference,
                "redirect_url": payment_result["redirectLink"],
                "order_id": order.name,
                "amount": advance_amount
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Sales Order Payment Error for {sales_order_name}")
            frappe.throw(_("Failed to create advance payment: {0}").format(str(e)))
    
    def send_payment_link_email(self, document_type, document_name, customer_email, custom_message=None):
        """Send payment link email to customer"""
        if document_type == "Sales Invoice":
            doc = frappe.get_doc("Sales Invoice", document_name)
            result = self.create_invoice_payment_link(document_name)
            amount_text = frappe.format_value(doc.outstanding_amount, {"fieldtype": "Currency"})
        elif document_type == "Sales Order":
            doc = frappe.get_doc("Sales Order", document_name)
            result = self.create_sales_order_advance_payment(document_name)
            amount_text = frappe.format_value(result["amount"], {"fieldtype": "Currency"})
        else:
            frappe.throw(_("Unsupported document type: {0}").format(document_type))
        
        payment_url = result["redirect_url"]
        
        # Send email
        subject = f"Payment Link for {document_type} {document_name}"
        message = custom_message or f"""
        <p>Dear {doc.customer_name},</p>
        <p>Please click the link below to pay for {document_type} {document_name}:</p>
        <p><a href="{payment_url}" target="_blank" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Pay Now - {amount_text}</a></p>
        <p>Thank you for your business!</p>
        """
        
        frappe.sendmail(
            recipients=[customer_email],
            subject=subject,
            message=message,
            header="Payment Link"
        )
        
        return {"status": "success", "message": "Payment link sent successfully"}
    
    def _create_order_record(self, payment_data, payment_reference, meta_data):
        """Create SeerBit Order record for tracking"""
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": payment_reference,
            "amount": float(payment_data["amount"]),
            "currency": payment_data["currency"],
            "customer_email": payment_data["email"],
            "customer_name": payment_data["full_name"],
            "callback_url": payment_data.get("callback_url", ""),
            "status": "Pending",
            "meta_data": frappe.as_json(meta_data)
        })
        order.insert(ignore_permissions=True)
        return order


def process_invoice_payment_completion(order_name, payment_data):
    """Process successful invoice payment completion"""
    try:
        order = frappe.get_doc("SeerBit Order", order_name)
        meta_data = frappe.parse_json(order.meta_data or "{}")
        invoice_name = meta_data.get("invoice_name")
        
        if not invoice_name:
            frappe.throw(_("Invoice name not found in order metadata"))
        
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Create Payment Entry
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Receive"
        payment_entry.party_type = "Customer"
        payment_entry.party = invoice.customer
        payment_entry.posting_date = nowdate()
        payment_entry.paid_from = invoice.debit_to
        
        # Get company's default cash/bank account
        company = frappe.get_doc("Company", invoice.company)
        payment_entry.paid_to = company.default_cash_account or company.default_bank_account
        
        payment_entry.paid_amount = float(payment_data.get("amount", order.amount))
        payment_entry.received_amount = payment_entry.paid_amount
        payment_entry.reference_no = payment_data.get("transactionRef") or order.payment_reference
        payment_entry.reference_date = nowdate()
        payment_entry.mode_of_payment = "SeerBit"
        
        # Link to invoice
        payment_entry.append("references", {
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": payment_entry.paid_amount
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update invoice status
        invoice.db_set("seerbit_payment_status", "Paid")
        
        # Update order
        order.payment_entry = payment_entry.name
        order.status = "Completed"
        order.save(ignore_permissions=True)
        
        return payment_entry
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Invoice Payment Completion Error for {order_name}")
        frappe.throw(_("Failed to complete invoice payment: {0}").format(str(e)))


def process_sales_order_payment_completion(order_name, payment_data):
    """Process successful sales order advance payment completion"""
    try:
        order = frappe.get_doc("SeerBit Order", order_name)
        meta_data = frappe.parse_json(order.meta_data or "{}")
        sales_order_name = meta_data.get("sales_order_name")
        
        if not sales_order_name:
            frappe.throw(_("Sales Order name not found in order metadata"))
        
        sales_order = frappe.get_doc("Sales Order", sales_order_name)
        
        # Create Payment Entry for advance
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Receive"
        payment_entry.party_type = "Customer"
        payment_entry.party = sales_order.customer
        payment_entry.posting_date = nowdate()
        
        # Get customer's default receivable account
        payment_entry.paid_from = frappe.get_value("Account", {
            "account_type": "Receivable",
            "company": sales_order.company,
            "is_group": 0
        }, "name")
        
        # Get company's default cash/bank account
        company = frappe.get_doc("Company", sales_order.company)
        payment_entry.paid_to = company.default_cash_account or company.default_bank_account
        
        payment_entry.paid_amount = float(payment_data.get("amount", order.amount))
        payment_entry.received_amount = payment_entry.paid_amount
        payment_entry.reference_no = payment_data.get("transactionRef") or order.payment_reference
        payment_entry.reference_date = nowdate()
        payment_entry.mode_of_payment = "SeerBit"
        payment_entry.is_advance = "Yes"
        
        # Link to sales order
        payment_entry.append("references", {
            "reference_doctype": "Sales Order",
            "reference_name": sales_order.name,
            "allocated_amount": payment_entry.paid_amount
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update sales order
        sales_order.db_set("custom_seerbit_last_payment_reference", order.payment_reference)
        sales_order.db_set("custom_seerbit_last_payment_status", "Completed")
        
        # Update order
        order.payment_entry = payment_entry.name
        order.status = "Completed"
        order.save(ignore_permissions=True)
        
        return payment_entry
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Sales Order Payment Completion Error for {order_name}")
        frappe.throw(_("Failed to complete sales order payment: {0}").format(str(e)))


# API endpoints
@frappe.whitelist()
def create_invoice_payment_link(invoice_name, include_charges=False):
    """API endpoint for creating invoice payment link"""
    selling_ops = SeerBitSellingOperations()
    return selling_ops.create_invoice_payment_link(invoice_name, include_charges)


@frappe.whitelist()
def create_sales_order_advance_payment(sales_order_name, advance_percentage=100):
    """API endpoint for creating sales order advance payment"""
    selling_ops = SeerBitSellingOperations()
    return selling_ops.create_sales_order_advance_payment(sales_order_name, advance_percentage)


@frappe.whitelist()
def send_payment_link_email(document_type, document_name, customer_email, custom_message=None):
    """API endpoint for sending payment link email"""
    selling_ops = SeerBitSellingOperations()
    return selling_ops.send_payment_link_email(document_type, document_name, customer_email, custom_message)
