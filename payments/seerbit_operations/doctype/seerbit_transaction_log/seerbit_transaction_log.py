# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, flt


class SeerBitTransactionLog(Document):
    def validate(self):
        """Validate transaction log details"""
        if not self.timestamp:
            self.timestamp = now()
            
        if not self.currency:
            self.currency = "NGN"
            
        # Calculate net amount if not provided
        if self.amount and self.fees and not self.net_amount:
            self.net_amount = flt(self.amount) - flt(self.fees)

    def before_save(self):
        """Update processed time for completed transactions"""
        if self.status in ["Success", "Failed", "Error", "Cancelled", "Refunded"] and not self.processed_at:
            self.processed_at = now()

    @frappe.whitelist()
    def retry_transaction(self):
        """Retry failed transaction"""
        if self.status not in ["Failed", "Error"]:
            frappe.throw("Only failed transactions can be retried")
            
        # Update retry count
        self.retry_count = (self.retry_count or 0) + 1
        self.last_retry_at = now()
        self.status = "Pending"
        self.save()
        
        frappe.msgprint(f"Transaction marked for retry. Retry count: {self.retry_count}")

    @staticmethod
    def create_log(transaction_data):
        """Create a new transaction log entry"""
        log_doc = frappe.get_doc({
            "doctype": "SeerBit Transaction Log",
            **transaction_data
        })
        log_doc.insert(ignore_permissions=True)
        return log_doc.name

    @staticmethod
    def update_log(log_name, update_data):
        """Update existing transaction log"""
        if frappe.db.exists("SeerBit Transaction Log", log_name):
            log_doc = frappe.get_doc("SeerBit Transaction Log", log_name)
            for field, value in update_data.items():
                setattr(log_doc, field, value)
            log_doc.save(ignore_permissions=True)
            return True
        return False

    @staticmethod
    def get_transaction_statistics(from_date=None, to_date=None):
        """Get transaction statistics for dashboard"""
        filters = {}
        if from_date:
            filters["timestamp"] = [">=", from_date]
        if to_date:
            if "timestamp" in filters:
                filters["timestamp"] = ["between", [from_date, to_date]]
            else:
                filters["timestamp"] = ["<=", to_date]
        
        # Get status-wise counts
        status_stats = frappe.db.sql("""
            SELECT status, COUNT(*) as count, SUM(IFNULL(amount, 0)) as total_amount
            FROM `tabSeerBit Transaction Log`
            WHERE {conditions}
            GROUP BY status
        """.format(
            conditions=frappe.db.get_conditions(filters) if filters else "1=1"
        ), as_dict=True)
        
        # Get transaction type wise stats
        type_stats = frappe.db.sql("""
            SELECT transaction_type, COUNT(*) as count, SUM(IFNULL(amount, 0)) as total_amount
            FROM `tabSeerBit Transaction Log`
            WHERE {conditions}
            GROUP BY transaction_type
        """.format(
            conditions=frappe.db.get_conditions(filters) if filters else "1=1"
        ), as_dict=True)
        
        return {
            "status_wise": status_stats,
            "type_wise": type_stats
        }
