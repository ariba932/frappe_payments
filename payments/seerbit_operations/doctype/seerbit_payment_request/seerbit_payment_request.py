# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, flt, add_days, get_url
from payments.seerbit_integration.core.api_client import SeerBitAPIClient
from payments.seerbit_integration.selling.invoice_payments import SeerBitInvoicePayment


class SeerBitPaymentRequest(Document):
    def validate(self):
        """Validate payment request details"""
        if not self.request_date:
            self.request_date = now()
            
        if not self.currency:
            self.currency = "NGN"
            
        if not self.status:
            self.status = "Draft"
            
        # Calculate total amount
        if self.amount and self.fees:
            self.total_amount = flt(self.amount) + flt(self.fees)
        else:
            self.total_amount = self.amount
            
        # Set expiry date if not provided (7 days from request date)
        if not self.expiry_date:
            self.expiry_date = add_days(self.request_date, 7)

    def before_save(self):
        """Update timestamps before saving"""
        self.last_updated = now()
        
        # Generate callback and redirect URLs
        if not self.callback_url:
            self.callback_url = get_url(f"/api/method/payments.seerbit_integration.core.webhooks.payment_callback")
        
        if not self.redirect_url:
            self.redirect_url = get_url("/payment_success")

    def on_submit(self):
        """Create payment link on SeerBit when submitting"""
        self.create_payment_link()

    def create_payment_link(self):
        """Create payment link on SeerBit"""
        try:
            # Prepare payment data
            payment_data = {
                "publicKey": frappe.conf.get("seerbit_public_key"),
                "amount": str(self.total_amount or self.amount),
                "currency": self.currency,
                "country": "NG",
                "email": self.customer_email,
                "productId": self.name,
                "productDescription": self.description or f"Payment for {self.reference_doctype} {self.reference_name}",
                "callbackUrl": self.callback_url,
                "redirectUrl": self.redirect_url
            }
            
            # Add customer details
            if self.customer_name:
                payment_data["fullName"] = self.customer_name
            if self.customer_phone:
                payment_data["mobileNumber"] = self.customer_phone
            
            # Create payment via SeerBit
            client = SeerBitAPIClient()
            response = client.create_payment_link(payment_data)
            
            if response.get("status") == "SUCCESS":
                payment_info = response.get("data", {})
                
                # Update payment request with SeerBit details
                self.db_set("seerbit_payment_reference", payment_info.get("reference"))
                self.db_set("payment_link", payment_info.get("redirectLink"))
                self.db_set("status", "Active")
                
                # Create transaction log
                self.create_transaction_log("Payment Link Created", response)
                
                frappe.msgprint(f"Payment link created successfully: {payment_info.get('redirectLink')}")
                
            else:
                frappe.throw(f"Failed to create payment link: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Payment Link Creation Error: {str(e)}", "SeerBit Payment Request")
            frappe.throw(f"Error creating payment link: {str(e)}")

    @frappe.whitelist()
    def verify_payment(self):
        """Verify payment status from SeerBit"""
        if not self.seerbit_payment_reference:
            frappe.throw("No SeerBit payment reference found")
            
        try:
            client = SeerBitAPIClient()
            response = client.verify_payment(self.seerbit_payment_reference)
            
            if response.get("status") == "SUCCESS":
                payment_data = response.get("data", {})
                payment_status = payment_data.get("paymentStatus", "").upper()
                
                if payment_status == "SUCCESSFUL":
                    self.db_set("status", "Paid")
                    self.db_set("payment_date", now())
                    
                    # Process the payment in ERPNext
                    self.process_successful_payment(payment_data)
                    
                    frappe.msgprint("Payment verified and processed successfully")
                    
                elif payment_status == "FAILED":
                    self.db_set("status", "Failed")
                    frappe.msgprint("Payment failed")
                    
                else:
                    frappe.msgprint(f"Payment status: {payment_status}")
                
                # Create transaction log
                self.create_transaction_log("Payment Verification", response)
                
                return payment_data
                
            else:
                frappe.throw(f"Payment verification failed: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Payment Verification Error: {str(e)}", "SeerBit Payment Request")
            frappe.throw(f"Error verifying payment: {str(e)}")

    def process_successful_payment(self, payment_data):
        """Process successful payment in ERPNext"""
        try:
            if self.reference_doctype == "Sales Invoice":
                self.create_payment_entry(payment_data)
            elif self.reference_doctype == "Sales Order":
                self.create_sales_invoice_and_payment(payment_data)
                
        except Exception as e:
            frappe.log_error(f"Payment Processing Error: {str(e)}", "SeerBit Payment Request")
            frappe.throw(f"Error processing payment: {str(e)}")

    def create_payment_entry(self, payment_data):
        """Create Payment Entry for Sales Invoice"""
        if not frappe.db.exists("Sales Invoice", self.reference_name):
            frappe.throw(f"Sales Invoice {self.reference_name} not found")
            
        invoice = frappe.get_doc("Sales Invoice", self.reference_name)
        
        # Create Payment Entry
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": invoice.customer,
            "paid_amount": flt(payment_data.get("amount", self.amount)),
            "received_amount": flt(payment_data.get("amount", self.amount)),
            "reference_no": payment_data.get("reference", self.seerbit_payment_reference),
            "reference_date": now(),
            "paid_to": invoice.debit_to,  # Default receivable account
            "mode_of_payment": "SeerBit",
            "references": [{
                "reference_doctype": "Sales Invoice",
                "reference_name": self.reference_name,
                "allocated_amount": flt(payment_data.get("amount", self.amount))
            }]
        })
        
        payment_entry.insert()
        payment_entry.submit()
        
        frappe.msgprint(f"Payment Entry {payment_entry.name} created successfully")

    def create_sales_invoice_and_payment(self, payment_data):
        """Create Sales Invoice and Payment Entry for Sales Order"""
        if not frappe.db.exists("Sales Order", self.reference_name):
            frappe.throw(f"Sales Order {self.reference_name} not found")
            
        # Create Sales Invoice from Sales Order
        sales_order = frappe.get_doc("Sales Order", self.reference_name)
        
        sales_invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": sales_order.customer,
            "posting_date": now(),
            "items": []
        })
        
        # Copy items from Sales Order
        for item in sales_order.items:
            sales_invoice.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "rate": item.rate,
                "amount": item.amount
            })
        
        sales_invoice.insert()
        sales_invoice.submit()
        
        # Update reference to Sales Invoice
        self.db_set("reference_doctype", "Sales Invoice")
        self.db_set("reference_name", sales_invoice.name)
        
        # Create Payment Entry
        self.create_payment_entry(payment_data)

    def create_transaction_log(self, action, response_data):
        """Create transaction log entry"""
        try:
            log_data = {
                "transaction_type": "Payment Collection",
                "reference_doctype": "SeerBit Payment Request",
                "reference_name": self.name,
                "seerbit_reference": self.seerbit_payment_reference,
                "amount": self.total_amount or self.amount,
                "currency": self.currency,
                "status": "Success" if response_data.get("status") == "SUCCESS" else "Failed",
                "action": action,
                "details": str(response_data),
                "customer_email": self.customer_email,
                "customer_phone": self.customer_phone,
                "timestamp": now()
            }
            
            frappe.get_doc({
                "doctype": "SeerBit Transaction Log",
                **log_data
            }).insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Transaction Log Error: {str(e)}", "SeerBit Payment Request")

    @frappe.whitelist()
    def cancel_payment_request(self):
        """Cancel the payment request"""
        if self.status == "Paid":
            frappe.throw("Cannot cancel a paid payment request")
            
        self.db_set("status", "Cancelled")
        self.create_transaction_log("Payment Request Cancelled", {"status": "CANCELLED"})
        frappe.msgprint("Payment request cancelled successfully")

    @frappe.whitelist()
    def resend_payment_link(self):
        """Resend payment link to customer"""
        if not self.payment_link:
            frappe.throw("No payment link found. Please create the payment request first.")
            
        # Send email with payment link
        frappe.sendmail(
            recipients=[self.customer_email],
            subject=f"Payment Request - {self.name}",
            message=f"""
            Dear {self.customer_name},
            
            Please use the following link to complete your payment:
            {self.payment_link}
            
            Amount: {self.currency} {self.total_amount or self.amount}
            Reference: {self.name}
            
            Thank you!
            """
        )
        
        frappe.msgprint("Payment link sent successfully")


# Utility functions
@frappe.whitelist()
def create_payment_request_from_invoice(sales_invoice):
    """Create payment request from Sales Invoice"""
    invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    
    # Check if payment request already exists
    existing_request = frappe.db.exists("SeerBit Payment Request", {
        "reference_doctype": "Sales Invoice",
        "reference_name": sales_invoice,
        "status": ["not in", ["Cancelled", "Failed"]]
    })
    
    if existing_request:
        frappe.throw(f"Payment request already exists: {existing_request}")
    
    payment_request = frappe.get_doc({
        "doctype": "SeerBit Payment Request",
        "reference_doctype": "Sales Invoice",
        "reference_name": sales_invoice,
        "payment_type": "One-time",
        "customer": invoice.customer,
        "customer_name": invoice.customer_name,
        "customer_email": invoice.contact_email,
        "customer_phone": invoice.contact_mobile,
        "amount": invoice.outstanding_amount,
        "currency": invoice.currency,
        "description": f"Payment for Sales Invoice {sales_invoice}"
    })
    
    payment_request.insert()
    return payment_request.name


@frappe.whitelist()
def get_payment_request_status(payment_request):
    """Get status of payment request"""
    doc = frappe.get_doc("SeerBit Payment Request", payment_request)
    return {
        "status": doc.status,
        "amount": doc.total_amount or doc.amount,
        "payment_link": doc.payment_link,
        "seerbit_reference": doc.seerbit_payment_reference
    }
