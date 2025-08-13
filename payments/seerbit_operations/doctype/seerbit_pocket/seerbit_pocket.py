# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now, get_datetime
from payments.seerbit_integration.core.api_client import SeerBitAPIClient


class SeerBitPocket(Document):
    def validate(self):
        """Validate pocket details"""
        if not self.currency:
            self.currency = "NGN"  # Default to Nigerian Naira
            
        if not self.status:
            self.status = "Active"
            
        # Set default flags
        if self.is_new():
            self.is_active = 1
            self.can_receive_transfers = 1
            self.can_send_transfers = 1
            self.auto_sync_enabled = 1

    def before_save(self):
        """Update timestamps before saving"""
        self.last_updated = now()

    def after_insert(self):
        """Create pocket on SeerBit after ERPNext record creation"""
        if not self.pocket_id:
            self.create_seerbit_pocket()

    def create_seerbit_pocket(self):
        """Create a new pocket on SeerBit platform"""
        try:
            client = SeerBitAPIClient()
            
            # Prepare pocket data
            pocket_data = {
                "name": self.pocket_name,
                "description": self.description or f"ERPNext {self.pocket_type} - {self.pocket_name}",
                "currency": self.currency
            }
            
            # Add department or cost center reference if available
            if self.linked_department:
                pocket_data["reference"] = f"DEPT_{self.linked_department}"
            elif self.linked_cost_center:
                pocket_data["reference"] = f"CC_{self.linked_cost_center}"
            
            # Create pocket via API
            response = client.create_sub_pocket(pocket_data)
            
            if response.get("status") == "SUCCESS":
                pocket_info = response.get("data", {})
                
                # Update ERPNext record with SeerBit pocket ID
                self.db_set("pocket_id", pocket_info.get("pocketId"))
                self.db_set("current_balance", flt(pocket_info.get("balance", 0)))
                self.db_set("last_sync_time", now())
                
                frappe.msgprint(f"SeerBit pocket created successfully: {pocket_info.get('pocketId')}")
                
                # Log creation
                self.create_pocket_log("Created", f"Pocket created on SeerBit with ID: {pocket_info.get('pocketId')}")
                
            else:
                frappe.throw(f"Failed to create SeerBit pocket: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Pocket Creation Error: {str(e)}", "SeerBit Pocket")
            frappe.throw(f"Error creating SeerBit pocket: {str(e)}")

    @frappe.whitelist()
    def sync_balance(self):
        """Sync balance from SeerBit"""
        if not self.pocket_id:
            frappe.throw("No SeerBit Pocket ID found. Please create the pocket first.")
            
        try:
            client = SeerBitAPIClient()
            response = client.get_pocket_details(self.pocket_id)
            
            if response.get("status") == "SUCCESS":
                pocket_data = response.get("data", {})
                old_balance = self.current_balance
                new_balance = flt(pocket_data.get("balance", 0))
                
                # Update balance
                self.db_set("current_balance", new_balance)
                self.db_set("last_sync_time", now())
                
                # Log balance change
                balance_change = new_balance - old_balance
                if balance_change != 0:
                    self.create_pocket_log(
                        "Balance Sync", 
                        f"Balance updated from {old_balance} to {new_balance} (Change: {balance_change})"
                    )
                
                frappe.msgprint(f"Balance synced successfully. Current balance: {new_balance}")
                return new_balance
                
            else:
                frappe.throw(f"Failed to sync balance: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Balance Sync Error: {str(e)}", "SeerBit Pocket")
            frappe.throw(f"Error syncing balance: {str(e)}")

    @frappe.whitelist()
    def transfer_to_pocket(self, target_pocket_id, amount, description=""):
        """Transfer funds to another pocket"""
        if not self.pocket_id:
            frappe.throw("No SeerBit Pocket ID found.")
            
        if not self.can_send_transfers:
            frappe.throw("This pocket is not allowed to send transfers.")
            
        try:
            client = SeerBitAPIClient()
            
            transfer_data = {
                "from_pocket": self.pocket_id,
                "to_pocket": target_pocket_id,
                "amount": flt(amount),
                "description": description or f"Transfer from {self.pocket_name}",
                "currency": self.currency
            }
            
            response = client.transfer_between_pockets(transfer_data)
            
            if response.get("status") == "SUCCESS":
                transfer_info = response.get("data", {})
                
                # Create transfer log
                self.create_pocket_log(
                    "Transfer Out",
                    f"Transferred {amount} to pocket {target_pocket_id}. Reference: {transfer_info.get('reference')}"
                )
                
                # Sync balance after transfer
                self.sync_balance()
                
                frappe.msgprint(f"Transfer successful. Reference: {transfer_info.get('reference')}")
                return transfer_info
                
            else:
                frappe.throw(f"Transfer failed: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Transfer Error: {str(e)}", "SeerBit Pocket")
            frappe.throw(f"Error processing transfer: {str(e)}")

    def create_pocket_log(self, action, details):
        """Create a log entry for pocket activities"""
        try:
            # Create SeerBit Transaction Log entry
            log_doc = frappe.get_doc({
                "doctype": "SeerBit Transaction Log",
                "transaction_type": "Pocket Operation",
                "reference_doctype": "SeerBit Pocket",
                "reference_name": self.name,
                "action": action,
                "details": details,
                "pocket_id": self.pocket_id,
                "amount": 0,  # Will be updated by specific operations
                "status": "Success",
                "timestamp": now()
            })
            log_doc.insert(ignore_permissions=True)
            
        except Exception as e:
            frappe.log_error(f"Pocket Log Error: {str(e)}", "SeerBit Pocket Log")

    @frappe.whitelist()
    def get_transaction_history(self, limit=50):
        """Get transaction history for this pocket"""
        if not self.pocket_id:
            return []
            
        try:
            client = SeerBitAPIClient()
            response = client.get_pocket_transactions(self.pocket_id, limit=limit)
            
            if response.get("status") == "SUCCESS":
                return response.get("data", {}).get("transactions", [])
            else:
                frappe.throw(f"Failed to get transaction history: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.log_error(f"SeerBit Transaction History Error: {str(e)}", "SeerBit Pocket")
            frappe.throw(f"Error getting transaction history: {str(e)}")

    @frappe.whitelist()
    def deactivate_pocket(self):
        """Deactivate the pocket"""
        self.db_set("status", "Inactive")
        self.db_set("is_active", 0)
        self.create_pocket_log("Deactivated", "Pocket deactivated by user")
        frappe.msgprint("Pocket deactivated successfully")

    @frappe.whitelist()
    def activate_pocket(self):
        """Activate the pocket"""
        self.db_set("status", "Active")
        self.db_set("is_active", 1)
        self.create_pocket_log("Activated", "Pocket activated by user")
        frappe.msgprint("Pocket activated successfully")


# Utility functions for SeerBit Pocket management
@frappe.whitelist()
def get_pocket_balance(pocket_name):
    """Get current balance for a pocket"""
    pocket = frappe.get_doc("SeerBit Pocket", pocket_name)
    return pocket.sync_balance()


@frappe.whitelist()
def create_department_pocket(department, description=""):
    """Create a pocket for a department"""
    dept_doc = frappe.get_doc("Department", department)
    
    pocket_name = f"DEPT_{dept_doc.name}"
    
    # Check if pocket already exists
    if frappe.db.exists("SeerBit Pocket", pocket_name):
        frappe.throw(f"Pocket already exists for department {department}")
    
    # Create pocket
    pocket_doc = frappe.get_doc({
        "doctype": "SeerBit Pocket",
        "pocket_name": pocket_name,
        "pocket_type": "Department Pocket",
        "linked_department": department,
        "linked_company": dept_doc.company,
        "description": description or f"Department pocket for {dept_doc.department_name}",
        "currency": "NGN"
    })
    
    pocket_doc.insert()
    return pocket_doc.name


@frappe.whitelist()
def transfer_between_pockets(from_pocket, to_pocket, amount, description=""):
    """Transfer funds between two pockets"""
    from_pocket_doc = frappe.get_doc("SeerBit Pocket", from_pocket)
    return from_pocket_doc.transfer_to_pocket(to_pocket, amount, description)


@frappe.whitelist()
def get_available_pockets(pocket_type=None):
    """Get list of available active pockets"""
    filters = {"status": "Active", "is_active": 1}
    if pocket_type:
        filters["pocket_type"] = pocket_type
        
    return frappe.get_all(
        "SeerBit Pocket",
        filters=filters,
        fields=["name", "pocket_name", "pocket_type", "current_balance", "currency"]
    )
