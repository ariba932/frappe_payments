# -*- coding: utf-8 -*-
"""
SeerBit Pocket Transfer Operations
Handles transfers between pockets, sub-pockets, and internal wallet management
"""

import frappe
from frappe import _
from frappe.utils import nowdate, flt
from ..core.api_client import get_api_client


class SeerBitPocketTransfers:
    """Pocket-to-pocket transfer operations"""
    
    def __init__(self):
        from ..core.api_client import get_seerbit_settings
        self.settings = get_seerbit_settings()
        self.api_client = get_api_client(self.settings)
        
        if not self.settings.is_enabled:
            frappe.throw(_("SeerBit is not enabled"))
        
        if not self.settings.enable_payouts:
            frappe.throw(_("SeerBit payouts are not enabled"))
    
    def transfer_between_pockets(self, from_pocket_id, to_pocket_id, amount, currency="NGN", 
                                reference=None, description=None):
        """
        Transfer funds between two pockets
        
        Args:
            from_pocket_id (str): Source pocket ID
            to_pocket_id (str): Destination pocket ID
            amount (float): Transfer amount
            currency (str): Currency (default: NGN)
            reference (str, optional): Unique reference for the transfer
            description (str, optional): Transfer description
        """
        bearer_token = self.api_client.get_bearer_token()
        
        if not from_pocket_id or not to_pocket_id:
            frappe.throw(_("Both source and destination pocket IDs are required"))
        
        if flt(amount) <= 0:
            frappe.throw(_("Transfer amount must be greater than zero"))
        
        # Generate unique reference if not provided
        reference = reference or f"TXN-{frappe.generate_hash(length=12)}"
        description = description or f"Transfer from {from_pocket_id} to {to_pocket_id}"
        
        url = f"{self.api_client.pocket_base_url}/pocket/transfer/from-pocket/{from_pocket_id}/to-pocket/{to_pocket_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        data = {
            "amount": flt(amount),
            "currency": currency,
            "reference": reference,
            "description": description
        }
        
        try:
            response = self.api_client._make_request("POST", url, headers=headers, json_data=data)
            
            if response.get("responseCode") == "00":
                # Create transfer record in ERPNext
                transfer_doc = self._create_transfer_record(
                    from_pocket_id, to_pocket_id, amount, currency, reference, description, response
                )
                
                return {
                    "status": "success",
                    "transfer_reference": reference,
                    "transfer_id": transfer_doc.name,
                    "amount": amount,
                    "currency": currency,
                    "from_pocket": from_pocket_id,
                    "to_pocket": to_pocket_id,
                    "message": "Transfer completed successfully"
                }
            else:
                frappe.throw(_("Transfer failed: {0}").format(response.get("message", "Unknown error")))
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Pocket Transfer Error")
            frappe.throw(_("Failed to process transfer: {0}").format(str(e)))
    
    def transfer_to_department(self, department_name, amount, currency="NGN", 
                              reference=None, description=None):
        """Transfer funds to a department's sub-pocket"""
        # Get department sub-pocket
        sub_pocket = frappe.db.get_value("SeerBit Sub-Pocket", 
                                        {"department": department_name, "status": "Active"}, 
                                        "sub_pocket_id")
        
        if not sub_pocket:
            frappe.throw(_("No active sub-pocket found for department: {0}").format(department_name))
        
        # Use main pocket as source
        from_pocket_id = self.settings.pocket_id
        description = description or f"Fund allocation to {department_name} department"
        
        return self.transfer_between_pockets(
            from_pocket_id, sub_pocket, amount, currency, reference, description
        )
    
    def transfer_to_cost_center(self, cost_center_name, amount, currency="NGN", 
                               reference=None, description=None):
        """Transfer funds to a cost center's sub-pocket"""
        # Get cost center sub-pocket
        sub_pocket = frappe.db.get_value("SeerBit Sub-Pocket", 
                                        {"cost_center": cost_center_name, "status": "Active"}, 
                                        "sub_pocket_id")
        
        if not sub_pocket:
            frappe.throw(_("No active sub-pocket found for cost center: {0}").format(cost_center_name))
        
        # Use main pocket as source
        from_pocket_id = self.settings.pocket_id
        description = description or f"Fund allocation to {cost_center_name} cost center"
        
        return self.transfer_between_pockets(
            from_pocket_id, sub_pocket, amount, currency, reference, description
        )
    
    def department_to_department_transfer(self, from_department, to_department, amount, 
                                        currency="NGN", reference=None, description=None):
        """Transfer funds between department sub-pockets"""
        # Get source department sub-pocket
        from_pocket = frappe.db.get_value("SeerBit Sub-Pocket", 
                                         {"department": from_department, "status": "Active"}, 
                                         "sub_pocket_id")
        
        if not from_pocket:
            frappe.throw(_("No active sub-pocket found for source department: {0}").format(from_department))
        
        # Get destination department sub-pocket
        to_pocket = frappe.db.get_value("SeerBit Sub-Pocket", 
                                       {"department": to_department, "status": "Active"}, 
                                       "sub_pocket_id")
        
        if not to_pocket:
            frappe.throw(_("No active sub-pocket found for destination department: {0}").format(to_department))
        
        description = description or f"Inter-department transfer from {from_department} to {to_department}"
        
        return self.transfer_between_pockets(
            from_pocket, to_pocket, amount, currency, reference, description
        )
    
    def bulk_department_allocation(self, allocations):
        """
        Bulk fund allocation to multiple departments
        
        Args:
            allocations (list): List of allocation dictionaries with keys:
                - department: Department name
                - amount: Allocation amount
                - description: Optional description
        """
        if isinstance(allocations, str):
            import json
            allocations = json.loads(allocations)
        
        results = []
        successful_count = 0
        failed_count = 0
        total_amount = 0
        
        for allocation in allocations:
            try:
                department = allocation.get("department")
                amount = flt(allocation.get("amount", 0))
                description = allocation.get("description", "")
                
                if not department or amount <= 0:
                    results.append({
                        "department": department,
                        "amount": amount,
                        "status": "failed",
                        "error": "Invalid department or amount"
                    })
                    failed_count += 1
                    continue
                
                result = self.transfer_to_department(department, amount, "NGN", None, description)
                results.append({
                    "department": department,
                    "amount": amount,
                    "status": "success",
                    "transfer_reference": result["transfer_reference"],
                    "transfer_id": result["transfer_id"]
                })
                successful_count += 1
                total_amount += amount
                
            except Exception as e:
                results.append({
                    "department": allocation.get("department", "Unknown"),
                    "amount": allocation.get("amount", 0),
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1
                frappe.log_error(f"Bulk allocation failed for {allocation}: {str(e)}", 
                               "Bulk Department Allocation Error")
        
        return {
            "status": "completed",
            "successful_count": successful_count,
            "failed_count": failed_count,
            "total_allocated": total_amount,
            "results": results,
            "total_processed": len(allocations)
        }
    
    def get_transfer_history(self, pocket_id=None, limit=50):
        """Get transfer history for a pocket"""
        filters = {}
        if pocket_id:
            filters = {
                "$or": [
                    {"from_pocket_id": pocket_id},
                    {"to_pocket_id": pocket_id}
                ]
            }
        
        transfers = frappe.get_all("SeerBit Pocket Transfer",
                                  filters=filters,
                                  fields=["name", "transfer_reference", "from_pocket_id", "to_pocket_id",
                                         "amount", "currency", "description", "status", "creation"],
                                  order_by="creation desc",
                                  limit=limit)
        
        return transfers
    
    def _create_transfer_record(self, from_pocket_id, to_pocket_id, amount, currency, 
                               reference, description, api_response):
        """Create SeerBit Pocket Transfer record in ERPNext"""
        transfer_doc = frappe.get_doc({
            "doctype": "SeerBit Pocket Transfer",
            "transfer_reference": reference,
            "from_pocket_id": from_pocket_id,
            "to_pocket_id": to_pocket_id,
            "amount": flt(amount),
            "currency": currency,
            "description": description,
            "status": "Completed",
            "api_response": frappe.as_json(api_response),
            "transfer_date": nowdate()
        })
        
        # Try to link to department/cost center if sub-pockets are involved
        self._link_transfer_to_erpnext_entities(transfer_doc, from_pocket_id, to_pocket_id)
        
        transfer_doc.insert(ignore_permissions=True)
        return transfer_doc
    
    def _link_transfer_to_erpnext_entities(self, transfer_doc, from_pocket_id, to_pocket_id):
        """Link transfer to ERPNext departments/cost centers"""
        # Check if from_pocket is a sub-pocket
        from_sub_pocket = frappe.db.get_value("SeerBit Sub-Pocket", 
                                             {"sub_pocket_id": from_pocket_id},
                                             ["department", "cost_center"], as_dict=True)
        if from_sub_pocket:
            transfer_doc.from_department = from_sub_pocket.get("department", "")
            transfer_doc.from_cost_center = from_sub_pocket.get("cost_center", "")
        
        # Check if to_pocket is a sub-pocket
        to_sub_pocket = frappe.db.get_value("SeerBit Sub-Pocket", 
                                           {"sub_pocket_id": to_pocket_id},
                                           ["department", "cost_center"], as_dict=True)
        if to_sub_pocket:
            transfer_doc.to_department = to_sub_pocket.get("department", "")
            transfer_doc.to_cost_center = to_sub_pocket.get("cost_center", "")


# API endpoints
@frappe.whitelist()
def transfer_between_pockets(from_pocket_id, to_pocket_id, amount, currency="NGN", 
                            reference=None, description=None):
    """API endpoint for pocket-to-pocket transfer"""
    pocket_transfers = SeerBitPocketTransfers()
    return pocket_transfers.transfer_between_pockets(
        from_pocket_id, to_pocket_id, amount, currency, reference, description
    )


@frappe.whitelist()
def transfer_to_department(department_name, amount, currency="NGN", reference=None, description=None):
    """API endpoint for transferring to department"""
    pocket_transfers = SeerBitPocketTransfers()
    return pocket_transfers.transfer_to_department(department_name, amount, currency, reference, description)


@frappe.whitelist()
def transfer_to_cost_center(cost_center_name, amount, currency="NGN", reference=None, description=None):
    """API endpoint for transferring to cost center"""
    pocket_transfers = SeerBitPocketTransfers()
    return pocket_transfers.transfer_to_cost_center(cost_center_name, amount, currency, reference, description)


@frappe.whitelist()
def department_to_department_transfer(from_department, to_department, amount, 
                                    currency="NGN", reference=None, description=None):
    """API endpoint for inter-department transfer"""
    pocket_transfers = SeerBitPocketTransfers()
    return pocket_transfers.department_to_department_transfer(
        from_department, to_department, amount, currency, reference, description
    )


@frappe.whitelist()
def bulk_department_allocation(allocations):
    """API endpoint for bulk department allocation"""
    pocket_transfers = SeerBitPocketTransfers()
    return pocket_transfers.bulk_department_allocation(allocations)


@frappe.whitelist()
def get_transfer_history(pocket_id=None, limit=50):
    """API endpoint for getting transfer history"""
    pocket_transfers = SeerBitPocketTransfers()
    return pocket_transfers.get_transfer_history(pocket_id, limit)


@frappe.whitelist()
def get_department_pocket_balance(department_name):
    """Get balance for a department's sub-pocket"""
    sub_pocket_id = frappe.db.get_value("SeerBit Sub-Pocket", 
                                       {"department": department_name, "status": "Active"}, 
                                       "sub_pocket_id")
    
    if not sub_pocket_id:
        frappe.throw(_("No active sub-pocket found for department: {0}").format(department_name))
    
    # Get balance using API client
    from ..core.api_client import get_seerbit_settings, get_api_client
    settings = get_seerbit_settings()
    api_client = get_api_client(settings)
    
    try:
        balance_data = api_client.get_wallet_balance(sub_pocket_id)
        return {
            "department": department_name,
            "sub_pocket_id": sub_pocket_id,
            "available_balance": balance_data.get("availableBalanceAmount", "0.00"),
            "currency": balance_data.get("availableBalanceCurrency", "NGN"),
            "last_transaction": balance_data.get("lastTransactionAt", ""),
            "balance_at": balance_data.get("balanceAt", "")
        }
    except Exception as e:
        frappe.throw(_("Failed to get department balance: {0}").format(str(e)))


@frappe.whitelist()
def get_all_department_balances(company=None):
    """Get balances for all department sub-pockets"""
    filters = {"department": ["!=", ""], "status": "Active"}
    
    if company:
        # Filter by departments of the company
        dept_filters = {"company": company} if company else {}
        departments = frappe.get_all("Department", filters=dept_filters, pluck="name")
        if departments:
            filters["department"] = ["in", departments]
        else:
            return []
    
    sub_pockets = frappe.get_all("SeerBit Sub-Pocket", 
                                filters=filters,
                                fields=["department", "sub_pocket_id", "business_name"])
    
    balances = []
    from ..core.api_client import get_seerbit_settings, get_api_client
    settings = get_seerbit_settings()
    api_client = get_api_client(settings)
    
    for sub_pocket in sub_pockets:
        try:
            balance_data = api_client.get_wallet_balance(sub_pocket.sub_pocket_id)
            balances.append({
                "department": sub_pocket.department,
                "business_name": sub_pocket.business_name,
                "sub_pocket_id": sub_pocket.sub_pocket_id,
                "available_balance": balance_data.get("availableBalanceAmount", "0.00"),
                "currency": balance_data.get("availableBalanceCurrency", "NGN")
            })
        except Exception as e:
            balances.append({
                "department": sub_pocket.department,
                "business_name": sub_pocket.business_name,
                "sub_pocket_id": sub_pocket.sub_pocket_id,
                "available_balance": "Error",
                "currency": "NGN",
                "error": str(e)
            })
    
    return balances
