# -*- coding: utf-8 -*-
"""
SeerBit Pocket Management Operations - Core pocket functionality
Handles wallet management, balance checking, and pocket details
"""

import frappe
from frappe import _
from frappe.utils import nowdate, flt
from ..core.api_client import get_api_client


class SeerBitPocketManager:
    """Core pocket management operations"""
    
    def __init__(self):
        self.settings = frappe.get_doc("SeerBit Settings")
        self.api_client = get_api_client(self.settings)
        
        if not self.settings.is_enabled:
            frappe.throw(_("SeerBit is not enabled"))
        
        if not self.settings.enable_payouts:
            frappe.throw(_("SeerBit payouts are not enabled"))
    
    def get_pocket_details(self, pocket_id=None):
        """Get detailed information about a specific pocket"""
        bearer_token = self.api_client.get_bearer_token()
        pocket_id = pocket_id or self.settings.pocket_id
        
        if not pocket_id:
            frappe.throw(_("Pocket ID is required"))
        
        url = f"{self.api_client.pocket_base_url}/pocket/pocket-id/{pocket_id}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self.api_client._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get pocket details: {0}").format(response.get("message", "Unknown error")))
    
    def get_all_pockets(self, pocket_id=None):
        """Get all pockets and sub-pockets for the merchant"""
        bearer_token = self.api_client.get_bearer_token()
        pocket_id = pocket_id or self.settings.pocket_id
        
        if not pocket_id:
            frappe.throw(_("Pocket ID is required"))
        
        url = f"{self.api_client.pocket_base_url}/pocket/pocket-id/{pocket_id}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self.api_client._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get all pockets: {0}").format(response.get("message", "Unknown error")))
    
    def get_pocket_balance_summary(self, pocket_id=None):
        """Get merchant balance summation across all pockets"""
        bearer_token = self.api_client.get_bearer_token()
        pocket_id = pocket_id or self.settings.pocket_id
        
        if not pocket_id:
            frappe.throw(_("Pocket ID is required"))
        
        url = f"{self.api_client.pocket_base_url}/pocket/balances-summation/pocket-id/{pocket_id}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self.api_client._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get balance summary: {0}").format(response.get("message", "Unknown error")))
    
    def get_pocket_transactions(self, pocket_id=None, page=0, size=20):
        """Get transaction history for a pocket"""
        bearer_token = self.api_client.get_bearer_token()
        pocket_id = pocket_id or self.settings.pocket_id
        
        if not pocket_id:
            frappe.throw(_("Pocket ID is required"))
        
        url = f"{self.api_client.pocket_base_url}/pocket/transaction/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        params = {
            "pocketId": pocket_id,
            "page": page,
            "size": size
        }
        
        # Add query parameters to URL
        url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        response = self.api_client._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get pocket transactions: {0}").format(response.get("message", "Unknown error")))
    
    def get_transaction_details(self, reference):
        """Get details of a specific transaction by reference"""
        bearer_token = self.api_client.get_bearer_token()
        
        url = f"{self.api_client.pocket_base_url}/pocket/transaction/reference/{reference}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self.api_client._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get transaction details: {0}").format(response.get("message", "Unknown error")))
    
    def sync_pocket_data_to_erpnext(self, pocket_id=None):
        """Sync pocket data with ERPNext for reporting and management"""
        try:
            # Get pocket details
            pocket_details = self.get_pocket_details(pocket_id)
            
            # Create or update SeerBit Pocket record
            pocket_doc = self._create_or_update_pocket_record(pocket_details)
            
            # Get balance
            balance_data = self.api_client.get_wallet_balance(pocket_id)
            
            # Update balance information
            pocket_doc.available_balance = flt(balance_data.get("availableBalanceAmount", 0))
            pocket_doc.ledger_balance = flt(balance_data.get("ledgerBalanceAmount", 0))
            pocket_doc.currency = balance_data.get("availableBalanceCurrency", "NGN")
            pocket_doc.last_balance_update = nowdate()
            
            pocket_doc.save(ignore_permissions=True)
            
            return {
                "status": "success",
                "pocket_id": pocket_details.get("pocketId"),
                "available_balance": pocket_doc.available_balance,
                "message": "Pocket data synced successfully"
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Pocket Sync Error for {pocket_id}")
            frappe.throw(_("Failed to sync pocket data: {0}").format(str(e)))
    
    def _create_or_update_pocket_record(self, pocket_data):
        """Create or update SeerBit Pocket record in ERPNext"""
        pocket_id = pocket_data.get("pocketId")
        
        if frappe.db.exists("SeerBit Pocket", {"pocket_id": pocket_id}):
            pocket_doc = frappe.get_doc("SeerBit Pocket", {"pocket_id": pocket_id})
        else:
            pocket_doc = frappe.new_doc("SeerBit Pocket")
            pocket_doc.pocket_id = pocket_id
        
        # Update pocket information
        pocket_doc.account_number = pocket_data.get("accountNumber", "")
        pocket_doc.status = pocket_data.get("status", "")
        pocket_doc.pocket_function = pocket_data.get("pocketFunction", "")
        pocket_doc.parent_id = pocket_data.get("parentId", "")
        pocket_doc.funding_link = pocket_data.get("fundingLink", "")
        pocket_doc.reference = pocket_data.get("reference", "")
        
        # Owner information
        owner_data = pocket_data.get("pocketOwner", {})
        if owner_data:
            pocket_doc.owner_business_name = owner_data.get("businessName", "")
            pocket_doc.owner_first_name = owner_data.get("firstName", "")
            pocket_doc.owner_last_name = owner_data.get("lastName", "")
            pocket_doc.owner_email = owner_data.get("emailAddress", "")
            pocket_doc.owner_phone = owner_data.get("phoneNumber", "")
        
        # Pocket accounts
        pocket_accounts = pocket_data.get("pocketAccounts", [])
        if pocket_accounts:
            # Clear existing accounts and add new ones
            pocket_doc.set("pocket_accounts", [])
            for account in pocket_accounts:
                pocket_doc.append("pocket_accounts", {
                    "account_id": account.get("accountId", ""),
                    "account_number": account.get("accountNumber", ""),
                    "bank_code": account.get("bankCode", ""),
                    "bank_name": account.get("bankName", ""),
                    "reference": account.get("reference", "")
                })
        
        if not pocket_doc.name:
            pocket_doc.insert(ignore_permissions=True)
        else:
            pocket_doc.save(ignore_permissions=True)
        
        return pocket_doc


# API endpoints
@frappe.whitelist()
def get_pocket_details(pocket_id=None):
    """API endpoint for getting pocket details"""
    pocket_manager = SeerBitPocketManager()
    return pocket_manager.get_pocket_details(pocket_id)


@frappe.whitelist()
def get_all_pockets(pocket_id=None):
    """API endpoint for getting all pockets"""
    pocket_manager = SeerBitPocketManager()
    return pocket_manager.get_all_pockets(pocket_id)


@frappe.whitelist()
def get_pocket_balance_summary(pocket_id=None):
    """API endpoint for getting balance summary"""
    pocket_manager = SeerBitPocketManager()
    return pocket_manager.get_pocket_balance_summary(pocket_id)


@frappe.whitelist()
def get_pocket_transactions(pocket_id=None, page=0, size=20):
    """API endpoint for getting pocket transactions"""
    pocket_manager = SeerBitPocketManager()
    return pocket_manager.get_pocket_transactions(pocket_id, page, size)


@frappe.whitelist()
def get_transaction_details(reference):
    """API endpoint for getting transaction details"""
    pocket_manager = SeerBitPocketManager()
    return pocket_manager.get_transaction_details(reference)


@frappe.whitelist()
def sync_pocket_data(pocket_id=None):
    """API endpoint for syncing pocket data"""
    pocket_manager = SeerBitPocketManager()
    return pocket_manager.sync_pocket_data_to_erpnext(pocket_id)
