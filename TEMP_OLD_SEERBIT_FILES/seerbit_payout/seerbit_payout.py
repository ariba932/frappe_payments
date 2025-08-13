# SeerBit Payout Document for tracking payouts via SeerBit
import frappe
from frappe.model.document import Document
from frappe import _

class SeerBitPayout(Document):
    def before_insert(self):
        self.created_at = frappe.utils.now()
    
    def on_update(self):
        self.updated_at = frappe.utils.now()
        if self.has_value_changed("status"):
            self.handle_status_change()
    
    def handle_status_change(self):
        if self.status in ("Paid", "PAID", "SUCCESS"):  # Seerbit may use uppercase
            self.on_payout_success()
        elif self.status in ("Failed", "FAILED", "FAILURE"):  # Seerbit may use uppercase
            self.on_payout_failure()
    
    def on_payout_success(self):
        # Update linked ERPNext doc (e.g. mark Salary Slip/Payment Entry as paid)
        if self.erpnext_linked_doc:
            try:
                doc = frappe.get_doc(self.beneficiary_type, self.erpnext_linked_doc)
                if hasattr(doc, "set_paid"):
                    doc.set_paid()
                elif hasattr(doc, "status"):
                    doc.status = "Paid"
                    doc.save(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to update ERPNext doc for payout {self.name}")
        
        # Log success without sensitive data
        frappe.log_error(f"SeerBit payout successful for reference: {self.payout_reference[:10]}***", "SeerBit Payout Success")
    
    def on_payout_failure(self):
        # Update linked ERPNext doc (e.g. mark as failed)
        if self.erpnext_linked_doc:
            try:
                doc = frappe.get_doc(self.beneficiary_type, self.erpnext_linked_doc)
                if hasattr(doc, "set_failed"):
                    doc.set_failed()
                elif hasattr(doc, "status"):
                    doc.status = "Failed"
                    doc.save(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to update ERPNext doc for payout {self.name}")
        
        # Log failure without sensitive data
        frappe.log_error(f"SeerBit payout failed for reference: {self.payout_reference[:10]}***", "SeerBit Payout Failure")

# Webhook handler for Seerbit payout notifications (to be registered in hooks.py)
@frappe.whitelist(allow_guest=True)
def seerbit_payout_webhook():
    try:
        data = frappe.local.form_dict or frappe.request.get_json() or {}
        
        # Handle bulk payout webhooks
        if isinstance(data, list):
            results = []
            for payout_data in data:
                result = process_single_payout_webhook(payout_data)
                results.append(result)
            return {"status": "success", "processed": len(results), "results": results}
        else:
            # Handle single payout webhook
            result = process_single_payout_webhook(data)
            return result
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Payout Webhook Error")
        return {"status": "failed", "reason": str(e)}

def process_single_payout_webhook(data):
    """Process a single payout webhook notification"""
    try:
        payout_ref = data.get("reference")
        status = data.get("status")
        
        if not payout_ref or not status:
            frappe.log_error(f"Missing data in webhook: {str(data)[:200]}...", "SeerBit Payout Webhook Missing Data")
            return {"status": "failed", "reason": "Missing reference or status"}
        
        # Find the payout record
        payout = frappe.get_doc("SeerBit Payout", {"payout_reference": payout_ref})
        
        # Update status and store response (without sensitive data)
        payout.status = status
        sanitized_data = {k: v for k, v in data.items() if k not in ["bankAccount", "beneficiaryEmail", "bankCode"]}
        payout.gateway_response = frappe.as_json(sanitized_data)
        payout.meta_data = frappe.as_json(sanitized_data)
        payout.save(ignore_permissions=True)
        
        return {"status": "success", "reference": payout_ref}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Single Payout Webhook Processing Error: {str(e)}")
        return {"status": "failed", "reason": str(e)}


# Add these methods to integrate with ERPNext payroll
@frappe.whitelist()
def initiate_salary_payout(salary_slip_name):
    """Initiate SeerBit payout for salary slip"""
    salary_slip = frappe.get_doc("Salary Slip", salary_slip_name)
    employee = frappe.get_doc("Employee", salary_slip.employee)
    
    if not employee.seerbit_payout_enabled:
        frappe.throw(_("SeerBit payout not enabled for employee {0}").format(employee.name))
    
    if not employee.seerbit_bank_code:
        frappe.throw(_("SeerBit bank code not set for employee {0}").format(employee.name))
    
    settings = frappe.get_doc("SeerBit Settings")
    
    try:
        result = settings.initiate_payout(
            beneficiary_name=employee.employee_name,
            beneficiary_email=employee.company_email or employee.personal_email,
            amount=salary_slip.net_pay,
            currency="NGN",
            bank_account=employee.bank_ac_no,
            bank_code=employee.seerbit_bank_code,
            narration=f"Salary payment for {salary_slip.employee_name}",
            beneficiary_type="Employee",
            meta_data={"salary_slip": salary_slip_name}
        )
        # Update salary slip
        salary_slip.seerbit_payout_reference = result["payout_reference"]
        salary_slip.seerbit_payout_status = "Processing"
        salary_slip.save(ignore_permissions=True)
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Salary Payout Error for {salary_slip_name}")
        frappe.throw(_("Failed to initiate salary payout: {0}").format(str(e)))

@frappe.whitelist()
def initiate_supplier_payout(payment_entry_name):
    """Initiate SeerBit payout for supplier payment"""
    payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
    supplier = frappe.get_doc("Supplier", payment_entry.party)
    
    if not supplier.seerbit_payout_enabled:
        frappe.throw(_("SeerBit payout not enabled for supplier {0}").format(supplier.name))
    
    if not supplier.seerbit_bank_code:
        frappe.throw(_("SeerBit bank code not set for supplier {0}").format(supplier.name))
    
    # Get supplier bank account
    bank_account = frappe.get_doc("Bank Account", supplier.default_bank_account)
    
    settings = frappe.get_doc("SeerBit Settings")
    try:
        result = settings.initiate_payout(
            beneficiary_name=supplier.supplier_name,
            beneficiary_email=supplier.email_id,
            amount=payment_entry.paid_amount,
            currency=payment_entry.paid_to_account_currency,
            bank_account=bank_account.bank_account_no,
            bank_code=supplier.seerbit_bank_code,
            narration=f"Payment to {supplier.supplier_name}",
            beneficiary_type="Supplier",
            meta_data={"payment_entry": payment_entry_name}
        )
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Supplier Payout Error for {payment_entry_name}")
        frappe.throw(_("Failed to initiate supplier payout: {0}").format(str(e)))        
