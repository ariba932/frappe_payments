# SeerBit Role-based Permission Manager
import frappe
from frappe import _

def has_role_based_payout_access(doctype=None, action="initiate"):
    """Check if user has role-based access for SeerBit payout operations"""
    user_roles = frappe.get_roles()
    
    # Define role access matrix for different doctypes and actions
    role_access_matrix = {
        "Salary Slip": {
            "initiate": ["HR Manager", "Payroll Manager", "System Manager"],
            "approve": ["HR Manager", "System Manager"],
            "bulk": ["HR Manager", "System Manager"]
        },
        "Payment Entry": {
            "initiate": ["Account Manager", "Accounts Manager", "Finance Manager", "System Manager"],
            "approve": ["Accounts Manager", "Finance Manager", "System Manager"],
            "bulk": ["Accounts Manager", "Finance Manager", "System Manager"]
        },
        "Purchase Invoice": {
            "initiate": ["Account Manager", "Accounts Manager", "Finance Manager", "System Manager"],
            "approve": ["Accounts Manager", "Finance Manager", "System Manager"],
            "bulk": ["Accounts Manager", "Finance Manager", "System Manager"]
        },
        "Sales Invoice": {
            "initiate": ["Sales Manager", "Account Manager", "Accounts Manager", "System Manager"],
            "approve": ["Sales Manager", "Accounts Manager", "System Manager"],
            "bulk": ["Sales Manager", "Accounts Manager", "System Manager"]
        }
    }
    
    if doctype and doctype in role_access_matrix:
        required_roles = role_access_matrix[doctype].get(action, [])
        return any(role in user_roles for role in required_roles)
    
    # Default fallback - check for any financial/admin role
    financial_roles = ["System Manager", "Accounts Manager", "Finance Manager", "HR Manager", "Account Manager"]
    return any(role in user_roles for role in financial_roles)

@frappe.whitelist()
def check_user_payout_permissions(doctype, action="initiate"):
    """Whitelist method to check user permissions for SeerBit operations"""
    return {
        "has_access": has_role_based_payout_access(doctype, action),
        "user_roles": frappe.get_roles(),
        "message": "User access checked successfully"
    }

def get_seerbit_enabled_companies():
    """Get companies that have SeerBit enabled"""
    companies = []
    settings = frappe.get_single("SeerBit Settings")
    
    if settings.is_enabled:
        # If company-specific settings exist, filter by those
        if hasattr(settings, 'company_settings'):
            for company_setting in settings.company_settings:
                if company_setting.enabled:
                    companies.append(company_setting.company)
        else:
            # Return all companies if no company-specific restriction
            companies = [d.name for d in frappe.get_all("Company", fields=["name"])]
    
    return companies

@frappe.whitelist()
def get_user_accessible_documents(doctype, company=None):
    """Get documents user can access for SeerBit operations based on roles"""
    if not has_role_based_payout_access(doctype):
        return []
    
    filters = {"docstatus": 1}
    if company:
        filters["company"] = company
    
    # Add SeerBit-specific filters based on doctype
    if doctype == "Salary Slip":
        filters["net_pay"] = [">", 0]
        # Only get slips where employee has SeerBit enabled
        sql = """
            SELECT ss.name, ss.employee, ss.employee_name, ss.net_pay, ss.company
            FROM `tabSalary Slip` ss
            INNER JOIN `tabEmployee` e ON ss.employee = e.name
            WHERE ss.docstatus = 1 
            AND ss.net_pay > 0
            AND e.seerbit_payout_enabled = 1
            {company_filter}
            ORDER BY ss.posting_date DESC
            LIMIT 50
        """.format(
            company_filter="AND ss.company = %(company)s" if company else ""
        )
        return frappe.db.sql(sql, {"company": company}, as_dict=True)
    
    elif doctype == "Payment Entry":
        filters.update({
            "payment_type": "Pay",
            "party_type": "Supplier",
            "paid_amount": [">", 0]
        })
        # Only get entries where supplier has SeerBit enabled
        sql = """
            SELECT pe.name, pe.party, pe.paid_amount, pe.company, pe.posting_date
            FROM `tabPayment Entry` pe
            INNER JOIN `tabSupplier` s ON pe.party = s.name
            WHERE pe.docstatus = 1 
            AND pe.payment_type = 'Pay'
            AND pe.party_type = 'Supplier'
            AND pe.paid_amount > 0
            AND s.seerbit_payout_enabled = 1
            {company_filter}
            ORDER BY pe.posting_date DESC
            LIMIT 50
        """.format(
            company_filter="AND pe.company = %(company)s" if company else ""
        )
        return frappe.db.sql(sql, {"company": company}, as_dict=True)
    
    # Default return for other doctypes
    return frappe.get_all(doctype, filters=filters, limit=50, order_by="creation desc")

@frappe.whitelist()
def validate_bulk_operation_access(doctype, document_names):
    """Validate user has access to perform bulk operations"""
    if not has_role_based_payout_access(doctype, "bulk"):
        frappe.throw(_("You don't have permission to perform bulk SeerBit operations"))
    
    # Additional validation based on document count
    if isinstance(document_names, str):
        import json
        document_names = json.loads(document_names)
    
    max_bulk_limit = frappe.db.get_single_value("SeerBit Settings", "max_bulk_payout_limit") or 100
    
    if len(document_names) > max_bulk_limit:
        frappe.throw(_("Bulk operation limit exceeded. Maximum allowed: {0}").format(max_bulk_limit))
    
    return True

def log_payout_activity(action, doctype, document_name, details=None):
    """Log SeerBit payout activities for audit trail"""
    try:
        activity_log = frappe.get_doc({
            "doctype": "Activity Log",
            "subject": f"SeerBit {action} - {doctype}: {document_name}",
            "content": frappe.as_json(details) if details else "",
            "communication_date": frappe.utils.now(),
            "reference_doctype": doctype,
            "reference_name": document_name,
            "user": frappe.session.user,
            "full_name": frappe.get_value("User", frappe.session.user, "full_name")
        })
        activity_log.insert(ignore_permissions=True)
    except Exception:
        # Don't fail the main operation if logging fails
        pass

@frappe.whitelist() 
def get_seerbit_settings_for_user():
    """Get SeerBit settings relevant to current user's permissions"""
    if not has_role_based_payout_access():
        return {"error": "No access to SeerBit settings"}
    
    settings = frappe.get_single("SeerBit Settings")
    
    # Return limited settings for security
    return {
        "is_enabled": settings.is_enabled,
        "sandbox_mode": getattr(settings, 'sandbox_mode', False),
        "supported_currencies": getattr(settings, 'supported_currencies', ["NGN"]),
        "max_bulk_limit": getattr(settings, 'max_bulk_payout_limit', 100),
        "webhook_enabled": getattr(settings, 'webhook_enabled', False)
    }
