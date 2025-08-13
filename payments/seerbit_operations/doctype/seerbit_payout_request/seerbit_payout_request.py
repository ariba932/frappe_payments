# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, flt, add_days, get_url
from payments.seerbit_integration.core.api_client import SeerBitAPIClient
from payments.seerbit_integration.buying.supplier_payments import SeerBitBuyingOperations


class SeerBitPayoutRequest(Document):
    def validate(self):
        """Validate payout request details"""
        if not self.request_date:
            self.request_date = now()
            
        if not self.currency:
            self.currency = "NGN"
            
        if not self.status:
            self.status = "Draft"
            
        if not self.approval_status:
            self.approval_status = "Not Required" if not self.requires_approval else "Pending"
            
        # Calculate net amount
        if self.amount and self.fees:
            self.net_amount = flt(self.amount) - flt(self.fees)
        else:
            self.net_amount = self.amount

    def before_save(self):
        """Update timestamps before saving"""
        self.last_updated = now()

    def on_submit(self):
        """Handle submission workflow"""
        if self.requires_approval and self.approval_status != "Approved":
            self.status = "Pending Approval"
        else:
            if self.auto_approve or not self.requires_approval:
                self.approve_payout()

    @frappe.whitelist()
    def verify_account(self):
        """Verify bank account details"""
        if not self.bank_code or not self.account_number:
            frappe.throw("Bank code and account number are required for verification")
            
        try:
            client = SeerBitAPIClient()
            verification_data = {
                "accountNumber": self.account_number,
                "bankCode": self.bank_code
            }
            
            response = client.verify_account_number(verification_data)
            
            if response.get("status") == "SUCCESS":
                account_info = response.get("data", {})
                
                # Update account details
                self.db_set("account_name", account_info.get("accountName"))
                self.db_set("bank_name", account_info.get("bankName"))
                self.db_set("account_verified", 1)
                
                # Create transaction log
                self.create_transaction_log("Account Verification", response)
                
                frappe.msgprint(f"Account verified: {account_info.get('accountName')}")
                return account_info
                
            else:
                frappe.throw(f"Account verification failed: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Account Verification Error: {str(e)}", "SeerBit Payout Request")
            frappe.throw(f"Error verifying account: {str(e)}")

    @frappe.whitelist()
    def approve_payout(self):
        """Approve the payout request"""
        if self.status in ["Completed", "Processing"]:
            frappe.throw("Payout is already processed or being processed")
            
        # Update approval details
        self.db_set("approval_status", "Approved")
        self.db_set("approved_by", frappe.session.user)
        self.db_set("approved_date", now())
        self.db_set("status", "Approved")
        
        # Auto-process if configured
        if frappe.db.get_single_value("SeerBit Settings", "auto_process_approved_payouts"):
            self.process_payout()
        
        frappe.msgprint("Payout approved successfully")

    @frappe.whitelist()
    def reject_payout(self, reason=""):
        """Reject the payout request"""
        self.db_set("approval_status", "Rejected")
        self.db_set("status", "Cancelled")
        if reason:
            self.db_set("approval_comments", reason)
        
        frappe.msgprint("Payout rejected")

    @frappe.whitelist()
    def process_payout(self):
        """Process the payout using SeerBit Enhanced Payout"""
        if self.status != "Approved":
            frappe.throw("Payout must be approved before processing")
            
        if not self.account_verified:
            frappe.throw("Bank account must be verified before processing payout")
            
        try:
            # Update status to processing
            self.db_set("status", "Processing")
            
            # Initialize Enhanced Payout
            buying_ops = SeerBitBuyingOperations()
            
            # Step 1: Authenticate
            auth_response = buying_ops.authenticate()
            
            # Step 2: Generate OTP
            otp_data = {
                "amount": str(self.amount),
                "currency": self.currency,
                "pocket_id": self.pocket_id
            }
            otp_response = buying_ops.generate_otp(otp_data)
            
            if otp_response.get("status") == "SUCCESS":
                otp_info = otp_response.get("data", {})
                self.db_set("otp_code", otp_info.get("otp"))
                
                # Step 3: Generate Signature
                signature_data = {
                    "amount": str(self.amount),
                    "currency": self.currency,
                    "otp": otp_info.get("otp"),
                    "pocket_id": self.pocket_id
                }
                signature_response = buying_ops.generate_signature(signature_data)
                
                if signature_response.get("status") == "SUCCESS":
                    signature_info = signature_response.get("data", {})
                    self.db_set("signature_hash", signature_info.get("signature"))
                    
                    # Step 4: Execute Enhanced Payout
                    payout_data = {
                        "amount": str(self.amount),
                        "currency": self.currency,
                        "accountNumber": self.account_number,
                        "bankCode": self.bank_code,
                        "accountName": self.account_name,
                        "narration": self.description or f"Payout for {self.payout_type}",
                        "otp": otp_info.get("otp"),
                        "signature": signature_info.get("signature"),
                        "pocket_id": self.pocket_id
                    }
                    
                    final_response = buying_ops.execute_enhanced_payout(payout_data)
                    
                    if final_response.get("status") == "SUCCESS":
                        payout_info = final_response.get("data", {})
                        
                        # Update payout details
                        self.db_set("seerbit_reference", payout_info.get("reference"))
                        self.db_set("status", "Completed")
                        self.db_set("processed_date", now())
                        
                        # Create Payment Entry in ERPNext
                        self.create_payment_entry(payout_info)
                        
                        # Create transaction log
                        self.create_transaction_log("Payout Completed", final_response)
                        
                        frappe.msgprint(f"Payout completed successfully. Reference: {payout_info.get('reference')}")
                        
                    else:
                        self.db_set("status", "Failed")
                        frappe.throw(f"Payout failed: {final_response.get('message', 'Unknown error')}")
                        
                else:
                    self.db_set("status", "Failed")
                    frappe.throw(f"Signature generation failed: {signature_response.get('message', 'Unknown error')}")
                    
            else:
                self.db_set("status", "Failed")
                frappe.throw(f"OTP generation failed: {otp_response.get('message', 'Unknown error')}")
                
        except Exception as e:
            self.db_set("status", "Failed")
            frappe.log_error(f"SeerBit Payout Processing Error: {str(e)}", "SeerBit Payout Request")
            frappe.throw(f"Error processing payout: {str(e)}")

    def create_payment_entry(self, payout_info):
        """Create Payment Entry in ERPNext"""
        try:
            # Determine party details based on beneficiary type
            party_type = "Supplier" if self.beneficiary_type == "Supplier" else "Employee"
            party = self.get_party_for_beneficiary()
            
            if not party:
                frappe.log_error(f"Could not determine party for beneficiary: {self.beneficiary_name}", "SeerBit Payout")
                return
            
            # Create Payment Entry
            payment_entry = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": "Pay",
                "party_type": party_type,
                "party": party,
                "paid_amount": self.amount,
                "received_amount": self.amount,
                "reference_no": payout_info.get("reference", self.seerbit_reference),
                "reference_date": now(),
                "mode_of_payment": "SeerBit",
                "remarks": f"SeerBit payout for {self.payout_type} - {self.name}"
            })
            
            # Add reference if available
            if self.reference_doctype and self.reference_name:
                payment_entry.append("references", {
                    "reference_doctype": self.reference_doctype,
                    "reference_name": self.reference_name,
                    "allocated_amount": self.amount
                })
            
            payment_entry.insert()
            payment_entry.submit()
            
            frappe.msgprint(f"Payment Entry {payment_entry.name} created successfully")
            
        except Exception as e:
            frappe.log_error(f"Payment Entry Creation Error: {str(e)}", "SeerBit Payout Request")

    def get_party_for_beneficiary(self):
        """Get ERPNext party for beneficiary"""
        if self.beneficiary_type == "Supplier":
            # Try to find supplier by name or create one
            supplier = frappe.db.get_value("Supplier", {"supplier_name": self.beneficiary_name})
            if not supplier:
                # Create new supplier
                supplier_doc = frappe.get_doc({
                    "doctype": "Supplier",
                    "supplier_name": self.beneficiary_name,
                    "supplier_group": "Local"
                })
                supplier_doc.insert()
                return supplier_doc.name
            return supplier
            
        elif self.beneficiary_type == "Employee":
            # Find employee by name
            employee = frappe.db.get_value("Employee", {"employee_name": self.beneficiary_name})
            return employee
            
        return None

    def create_transaction_log(self, action, response_data):
        """Create transaction log entry"""
        try:
            log_data = {
                "transaction_type": "Payout",
                "reference_doctype": "SeerBit Payout Request",
                "reference_name": self.name,
                "seerbit_reference": self.seerbit_reference,
                "amount": self.amount,
                "currency": self.currency,
                "status": "Success" if response_data.get("status") == "SUCCESS" else "Failed",
                "action": action,
                "details": str(response_data),
                "timestamp": now()
            }
            
            frappe.get_doc({
                "doctype": "SeerBit Transaction Log",
                **log_data
            }).insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Transaction Log Error: {str(e)}", "SeerBit Payout Request")

    @frappe.whitelist()
    def check_payout_status(self):
        """Check payout status from SeerBit"""
        if not self.seerbit_reference:
            frappe.throw("No SeerBit reference found")
            
        try:
            client = SeerBitAPIClient()
            response = client.get_payout_status(self.seerbit_reference)
            
            if response.get("status") == "SUCCESS":
                payout_data = response.get("data", {})
                status = payout_data.get("status", "").upper()
                
                if status == "SUCCESSFUL" and self.status != "Completed":
                    self.db_set("status", "Completed")
                    self.db_set("processed_date", now())
                elif status == "FAILED" and self.status != "Failed":
                    self.db_set("status", "Failed")
                
                self.create_transaction_log("Status Check", response)
                return payout_data
                
            else:
                frappe.throw(f"Status check failed: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Status Check Error: {str(e)}", "SeerBit Payout Request")
            frappe.throw(f"Error checking status: {str(e)}")


# Utility functions
@frappe.whitelist()
def create_payout_from_purchase_invoice(purchase_invoice):
    """Create payout request from Purchase Invoice"""
    invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
    
    # Get supplier bank details
    supplier_doc = frappe.get_doc("Supplier", invoice.supplier)
    
    payout_request = frappe.get_doc({
        "doctype": "SeerBit Payout Request",
        "payout_type": "Supplier Payment",
        "reference_doctype": "Purchase Invoice",
        "reference_name": purchase_invoice,
        "beneficiary_type": "Supplier",
        "beneficiary_name": supplier_doc.supplier_name,
        "amount": invoice.outstanding_amount,
        "currency": invoice.currency,
        "description": f"Payment for Purchase Invoice {purchase_invoice}",
        "requires_approval": 1
    })
    
    payout_request.insert()
    return payout_request.name


@frappe.whitelist()
def bulk_approve_payouts(payout_requests):
    """Approve multiple payout requests"""
    approved_count = 0
    
    for payout_name in payout_requests:
        try:
            payout = frappe.get_doc("SeerBit Payout Request", payout_name)
            payout.approve_payout()
            approved_count += 1
        except Exception as e:
            frappe.log_error(f"Bulk Approval Error for {payout_name}: {str(e)}", "SeerBit Payout Request")
    
    frappe.msgprint(f"Approved {approved_count} payout requests successfully")
    return approved_count
