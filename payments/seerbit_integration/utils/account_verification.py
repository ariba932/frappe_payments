# -*- coding: utf-8 -*-
"""
SeerBit Account Verification Utilities
Handles bank account verification and validation
"""

import frappe
from frappe import _
from ..core.api_client import get_api_client


def verify_beneficiary_account(account_number, bank_code, beneficiary_name=None):
    """
    Verify a beneficiary bank account using SeerBit API
    
    Args:
        account_number (str): Bank account number
        bank_code (str): Bank code (e.g., "044" for Access Bank)
        beneficiary_name (str, optional): Expected account holder name
    
    Returns:
        dict: Verification result with account details
    """
    try:
        from ..core.api_client import get_seerbit_settings, get_api_client
        settings = get_seerbit_settings()
        if not settings.is_active:
            frappe.throw(_("SeerBit is not enabled"))
        
        # Check if account verification is enabled
        if not settings.get("enable_account_verification", 1):
            return {
                "verified": True,
                "message": "Account verification is disabled",
                "status": "skipped",
                "account_name": expected_name or "Not verified"
            }
        
        api_client = get_api_client(settings)
        
        # Make account verification request using correct endpoint
        verification_result = api_client.verify_bank_account(account_number, bank_code)
        
        account_name = verification_result.get("accountName", "")
        
        # Validate account name if provided
        name_match = True
        if expected_name and account_name:
            name_match = _compare_names(expected_name, account_name)
        
        return {
            "verified": verification_result.get("responseCode") == "00" and name_match,
            "account_name": account_name,
            "account_number": account_number,
            "bank_code": bank_code,
            "name_match": name_match,
            "expected_name": expected_name,
            "status": "success",
            "message": "Account verified successfully" if name_match else "Account name mismatch",
            "raw_response": verification_result
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Account Verification Error for {account_number}")
        return {
            "verified": False,
            "account_number": account_number,
            "bank_code": bank_code,
            "expected_name": expected_name,
            "status": "error",
            "message": str(e)
        }


def verify_employee_bank_accounts(employee_list, update_records=True):
    """
    Bulk verify employee bank accounts
    
    Args:
        employee_list (list): List of employee IDs
        update_records (bool): Whether to update employee records with verification status
    
    Returns:
        dict: Bulk verification results
    """
    if isinstance(employee_list, str):
        import json
        employee_list = json.loads(employee_list)
    
    verification_results = []
    
    for employee_id in employee_list:
        try:
            employee = frappe.get_doc("Employee", employee_id)
            
            if not employee.bank_ac_no or not employee.seerbit_bank_code:
                verification_results.append({
                    "employee_id": employee_id,
                    "employee_name": employee.employee_name,
                    "status": "failed",
                    "message": "Missing bank account or bank code",
                    "verified": False
                })
                continue
            
            result = verify_beneficiary_account(
                employee.bank_ac_no,
                employee.seerbit_bank_code,
                employee.employee_name
            )
            
            result.update({
                "employee_id": employee_id,
                "employee_name": employee.employee_name
            })
            
            verification_results.append(result)
            
            # Update employee record if requested
            if update_records:
                if result.get("verified"):
                    employee.db_set("account_verification_status", "Verified")
                    employee.db_set("verified_account_name", result.get("account_name"))
                else:
                    employee.db_set("account_verification_status", "Failed")
                    employee.db_set("verification_failure_reason", result.get("message"))
                
        except Exception as e:
            verification_results.append({
                "employee_id": employee_id,
                "status": "failed",
                "message": str(e),
                "verified": False
            })
            frappe.log_error(f"Employee verification error for {employee_id}: {str(e)}", "Bulk Employee Verification")
    
    return {
        "status": "completed",
        "results": verification_results,
        "total_processed": len(verification_results),
        "verified_count": len([r for r in verification_results if r.get("verified")]),
        "failed_count": len([r for r in verification_results if not r.get("verified")])
    }


def verify_supplier_bank_accounts(supplier_list, update_records=True):
    """
    Bulk verify supplier bank accounts
    
    Args:
        supplier_list (list): List of supplier IDs
        update_records (bool): Whether to update supplier records with verification status
    
    Returns:
        dict: Bulk verification results
    """
    if isinstance(supplier_list, str):
        import json
        supplier_list = json.loads(supplier_list)
    
    verification_results = []
    
    for supplier_id in supplier_list:
        try:
            supplier = frappe.get_doc("Supplier", supplier_id)
            
            if not supplier.default_bank_account or not supplier.seerbit_bank_code:
                verification_results.append({
                    "supplier_id": supplier_id,
                    "supplier_name": supplier.supplier_name,
                    "status": "failed",
                    "message": "Missing bank account or bank code",
                    "verified": False
                })
                continue
            
            bank_account = frappe.get_doc("Bank Account", supplier.default_bank_account)
            
            if not bank_account.bank_account_no:
                verification_results.append({
                    "supplier_id": supplier_id,
                    "supplier_name": supplier.supplier_name,
                    "status": "failed",
                    "message": "Bank account number not found",
                    "verified": False
                })
                continue
            
            result = verify_beneficiary_account(
                bank_account.bank_account_no,
                supplier.seerbit_bank_code,
                supplier.supplier_name
            )
            
            result.update({
                "supplier_id": supplier_id,
                "supplier_name": supplier.supplier_name,
                "bank_account_id": bank_account.name
            })
            
            verification_results.append(result)
            
            # Update supplier record if requested
            if update_records:
                if result.get("verified"):
                    supplier.db_set("account_verification_status", "Verified")
                    supplier.db_set("verified_account_name", result.get("account_name"))
                else:
                    supplier.db_set("account_verification_status", "Failed")
                    supplier.db_set("verification_failure_reason", result.get("message"))
                
        except Exception as e:
            verification_results.append({
                "supplier_id": supplier_id,
                "status": "failed",
                "message": str(e),
                "verified": False
            })
            frappe.log_error(f"Supplier verification error for {supplier_id}: {str(e)}", "Bulk Supplier Verification")
    
    return {
        "status": "completed",
        "results": verification_results,
        "total_processed": len(verification_results),
        "verified_count": len([r for r in verification_results if r.get("verified")]),
        "failed_count": len([r for r in verification_results if not r.get("verified")])
    }


def _compare_names(expected_name, actual_name, threshold=0.8):
    """
    Compare two names with fuzzy matching
    
    Args:
        expected_name (str): Expected name
        actual_name (str): Actual name from bank
        threshold (float): Similarity threshold (0.0 to 1.0)
    
    Returns:
        bool: True if names are similar enough
    """
    if not expected_name or not actual_name:
        return False
    
    # Simple preprocessing
    expected_clean = _clean_name(expected_name)
    actual_clean = _clean_name(actual_name)
    
    # Exact match
    if expected_clean == actual_clean:
        return True
    
    # Check if one name contains the other
    if expected_clean in actual_clean or actual_clean in expected_clean:
        return True
    
    # Fuzzy matching using Levenshtein distance
    try:
        import difflib
        similarity = difflib.SequenceMatcher(None, expected_clean, actual_clean).ratio()
        return similarity >= threshold
    except:
        # Fallback to simple word matching
        expected_words = set(expected_clean.split())
        actual_words = set(actual_clean.split())
        common_words = expected_words.intersection(actual_words)
        
        if len(common_words) >= min(len(expected_words), len(actual_words)) * threshold:
            return True
    
    return False


def _clean_name(name):
    """Clean name for comparison"""
    if not name:
        return ""
    
    # Remove common prefixes/suffixes and normalize
    import re
    
    # Convert to lowercase and remove special characters
    cleaned = re.sub(r'[^\w\s]', '', name.lower())
    
    # Remove common titles
    titles = ['mr', 'mrs', 'miss', 'dr', 'prof', 'chief', 'hon', 'sir', 'dame']
    words = cleaned.split()
    words = [word for word in words if word not in titles]
    
    # Remove common business suffixes
    business_suffixes = ['ltd', 'limited', 'plc', 'inc', 'corp', 'company', 'co']
    words = [word for word in words if word not in business_suffixes]
    
    return ' '.join(words).strip()


# API endpoints
@frappe.whitelist()
def verify_single_account(account_number, bank_code, expected_name=None):
    """API endpoint for single account verification"""
    return verify_beneficiary_account(account_number, bank_code, expected_name)


@frappe.whitelist()
def verify_employee_accounts(employee_list, update_records=True):
    """API endpoint for bulk employee account verification"""
    return verify_employee_bank_accounts(employee_list, update_records)


@frappe.whitelist()
def verify_supplier_accounts(supplier_list, update_records=True):
    """API endpoint for bulk supplier account verification"""
    return verify_supplier_bank_accounts(supplier_list, update_records)
