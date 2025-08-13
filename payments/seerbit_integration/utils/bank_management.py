# -*- coding: utf-8 -*-
"""
SeerBit Bank Management Utilities
Handles bank code synchronization and management
"""

import frappe
from frappe import _
from ..core.api_client import get_api_client


def sync_bank_codes_from_seerbit():
    """Sync bank codes from SeerBit API to local database"""
    try:
        settings = frappe.get_doc("SeerBit Settings")
        if not settings.is_enabled:
            frappe.throw(_("SeerBit is not enabled"))
        
        api_client = get_api_client(settings)
        
        # Get bank list from SeerBit
        banks = api_client.get_bank_list()
        
        # Sync banks to local database
        synced_count = 0
        for bank_data in banks:
            bank_code = bank_data.get("code")
            bank_name = bank_data.get("name")
            
            if not bank_code or not bank_name:
                continue
            
            # Create/Update SeerBit Bank Code
            if frappe.db.exists("SeerBit Bank Code", bank_code):
                doc = frappe.get_doc("SeerBit Bank Code", bank_code)
                doc.bank_name = bank_name
                doc.is_active = bank_data.get("is_active", 1)
                doc.save(ignore_permissions=True)
            else:
                doc = frappe.get_doc({
                    "doctype": "SeerBit Bank Code",
                    "bank_code": bank_code,
                    "bank_name": bank_name,
                    "is_active": bank_data.get("is_active", 1)
                })
                doc.insert(ignore_permissions=True)
            
            # Sync to ERPNext Bank if enabled
            if settings.get("sync_to_erpnext_banks", 1):
                sync_to_erpnext_bank(bank_code, bank_name)
            
            synced_count += 1
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} bank codes"
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Bank Sync Error")
        frappe.throw(_("Failed to sync bank codes: {0}").format(str(e)))


def sync_to_erpnext_bank(bank_code, bank_name):
    """Sync bank to ERPNext Bank doctype"""
    try:
        bank_name_clean = clean_bank_name(bank_name)
        
        if not frappe.db.exists("Bank", bank_name_clean):
            # Create new bank
            bank_doc = frappe.get_doc({
                "doctype": "Bank",
                "bank_name": bank_name_clean,
                "seerbit_bank_code": bank_code,
                "payment_gateway_source": "SeerBit"
            })
            bank_doc.insert(ignore_permissions=True)
        else:
            # Update existing bank
            bank_doc = frappe.get_doc("Bank", bank_name_clean)
            if not bank_doc.seerbit_bank_code:
                bank_doc.seerbit_bank_code = bank_code
                bank_doc.payment_gateway_source = "SeerBit"
                bank_doc.save(ignore_permissions=True)
                
    except Exception as e:
        frappe.log_error(f"Failed to sync Bank {bank_name}: {str(e)}", "Bank Sync Error")


def clean_bank_name(bank_name):
    """Clean bank name for ERPNext compatibility"""
    if not bank_name:
        return ""
    
    # Common replacements
    replacements = {
        "Limited": "Ltd",
        "PLC": "Plc",
        "MICROFINANCE": "MFB",
        "Microfinance": "MFB",
        "BANK": "Bank"
    }
    
    cleaned_name = bank_name
    for old, new in replacements.items():
        cleaned_name = cleaned_name.replace(old, new)
    
    return cleaned_name.strip()


def get_bank_code_options():
    """Get bank code options for dropdowns"""
    bank_codes = frappe.get_all("SeerBit Bank Code", 
        filters={"is_active": 1},
        fields=["bank_code", "bank_name"],
        order_by="bank_name"
    )
    
    return [{"value": bc.bank_code, "label": f"{bc.bank_name} ({bc.bank_code})"} for bc in bank_codes]


def validate_bank_code(bank_code):
    """Validate if bank code exists and is active"""
    if not bank_code:
        return False, "Bank code is required"
    
    bank_record = frappe.db.get_value("SeerBit Bank Code", bank_code, 
        ["bank_name", "is_active"], as_dict=True)
    
    if not bank_record:
        return False, f"Bank code {bank_code} not found"
    
    if not bank_record.is_active:
        return False, f"Bank code {bank_code} is inactive"
    
    return True, bank_record.bank_name


def get_bank_name_by_code(bank_code):
    """Get bank name by bank code"""
    return frappe.db.get_value("SeerBit Bank Code", bank_code, "bank_name")


def search_bank_codes(search_term):
    """Search bank codes by name or code"""
    if not search_term:
        return []
    
    search_term = f"%{search_term}%"
    
    results = frappe.db.sql("""
        SELECT bank_code, bank_name
        FROM `tabSeerBit Bank Code`
        WHERE is_active = 1
        AND (bank_name LIKE %(search_term)s OR bank_code LIKE %(search_term)s)
        ORDER BY bank_name
        LIMIT 20
    """, {"search_term": search_term}, as_dict=True)
    
    return [{"value": r.bank_code, "label": f"{r.bank_name} ({r.bank_code})"} for r in results]


# API endpoints
@frappe.whitelist()
def sync_banks():
    """API endpoint for syncing bank codes"""
    return sync_bank_codes_from_seerbit()


@frappe.whitelist()
def get_bank_options():
    """API endpoint for getting bank code options"""
    return get_bank_code_options()


@frappe.whitelist()
def search_banks(search_term):
    """API endpoint for searching bank codes"""
    return search_bank_codes(search_term)


@frappe.whitelist()
def validate_bank(bank_code):
    """API endpoint for validating bank code"""
    is_valid, message = validate_bank_code(bank_code)
    return {"valid": is_valid, "message": message}
