# SeerBit Bank Code Document
import frappe
from frappe.model.document import Document
from frappe import _

class SeerBitBankCode(Document):
    def before_insert(self):
        self.last_updated = frappe.utils.now()
    
    def on_update(self):
        self.last_updated = frappe.utils.now()
        # Sync with ERPNext Bank if needed
        self.sync_with_erpnext_bank()
    
    def sync_with_erpnext_bank(self):
        """Sync this bank code with ERPNext Bank doctype"""
        try:
            # Check if Bank already exists
            existing_bank = frappe.db.get_value("Bank", {"bank_name": self.bank_name}, "name")
            
            if existing_bank:
                # Update existing bank
                bank_doc = frappe.get_doc("Bank", existing_bank)
                bank_doc.seerbit_bank_code = self.bank_code
                bank_doc.payment_gateway_source = "SeerBit"
                bank_doc.save(ignore_permissions=True)
            else:
                # Create new bank
                bank_doc = frappe.get_doc({
                    "doctype": "Bank",
                    "bank_name": self.bank_name,
                    "seerbit_bank_code": self.bank_code,
                    "payment_gateway_source": "SeerBit",
                    "country": self.country
                })
                bank_doc.insert(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Failed to sync SeerBit Bank Code {self.name} with ERPNext Bank")
