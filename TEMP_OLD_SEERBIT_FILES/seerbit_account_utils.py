# SeerBit Account Enquiry and Bank Verification
import frappe
from frappe import _
import requests

@frappe.whitelist()
def verify_bank_account(account_number, bank_code):
    """
    Verify bank account details using SeerBit Account Enquiry API
    """
    settings = frappe.get_doc("SeerBit Settings")
    
    if not settings.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    if not settings.enable_payouts:
        frappe.throw(_("SeerBit payouts are not enabled"))
    
    # Get bearer token for account enquiry
    from payments.payment_gateways.doctype.seerbit_settings.seerbit_payout_enhanced import SeerBitPayoutEnhanced
    payout_handler = SeerBitPayoutEnhanced(settings)
    payout_handler.authenticate_with_credentials()
    
    base_url = "https://pocket.seerbitapi.com" if not settings.sandbox_mode else "https://sandbox.seerbitapi.com"
    url = f"{base_url}/pocket/payout/account-enquiry"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {payout_handler.bearer_token}"
    }
    
    data = {
        "accountnumber": account_number,
        "bankcode": bank_code
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("responseCode") == "00":
                return {
                    "status": "success",
                    "account_name": result.get("data", {}).get("accountName"),
                    "account_number": account_number,
                    "bank_code": bank_code,
                    "verified": True
                }
            else:
                return {
                    "status": "failed",
                    "message": result.get("message", "Account verification failed"),
                    "verified": False
                }
        else:
            frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Account Enquiry HTTP Error")
            return {
                "status": "failed",
                "message": f"API request failed with status: {response.status_code}",
                "verified": False
            }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Account Enquiry Network Error")
        return {
            "status": "failed",
            "message": f"Network error: {str(e)}",
            "verified": False
        }

@frappe.whitelist()
def sync_bank_list():
    """
    Sync Nigerian bank list from SeerBit API
    """
    settings = frappe.get_doc("SeerBit Settings")
    
    if not settings.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    # Get bearer token for bank list
    from payments.payment_gateways.doctype.seerbit_settings.seerbit_payout_enhanced import SeerBitPayoutEnhanced
    payout_handler = SeerBitPayoutEnhanced(settings)
    payout_handler.authenticate_with_credentials()
    
    base_url = "https://pocket.seerbitapi.com" if not settings.sandbox_mode else "https://sandbox.seerbitapi.com"
    url = f"{base_url}/pocket/banks"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {payout_handler.bearer_token}",
        "Public-Key": settings.public_key
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "SUCCESS":
                banks = result.get("data", [])
                settings.sync_bank_codes(banks)
                return {
                    "status": "success",
                    "message": f"Successfully synced {len(banks)} banks",
                    "count": len(banks)
                }
            else:
                frappe.throw(_("Failed to fetch bank list: {0}").format(result.get("message", "Unknown error")))
        else:
            frappe.throw(_("API request failed with status: {0}").format(response.status_code))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Bank List Sync Error")
        frappe.throw(_("Error syncing bank list: {0}").format(str(e)))

@frappe.whitelist()
def bulk_verify_accounts(account_data):
    """
    Bulk verify multiple bank accounts
    account_data: list of dict with keys: account_number, bank_code, reference_id
    """
    if isinstance(account_data, str):
        import json
        account_data = json.loads(account_data)
    
    results = []
    for account in account_data:
        try:
            result = verify_bank_account(
                account.get("account_number"),
                account.get("bank_code")
            )
            result["reference_id"] = account.get("reference_id")
            results.append(result)
        except Exception as e:
            results.append({
                "status": "failed",
                "message": str(e),
                "reference_id": account.get("reference_id"),
                "verified": False
            })
    
    return {
        "status": "completed",
        "results": results,
        "total_processed": len(results)
    }
