# Extended SeerBit Payout functionality for bulk operations
import frappe
from frappe import _
from payments.payment_gateways.doctype.seerbit_payout.seerbit_payout import initiate_salary_payout

@frappe.whitelist()
def get_salary_slips_for_bulk_payout(company, payroll_period, salary_month, department=None):
    """Get salary slips eligible for SeerBit bulk payout"""
    filters = {
        "company": company,
        "start_date": ["like", f"{salary_month}%"],
        "docstatus": 1,
        "seerbit_payout_status": ["in", ["Not Initiated", "Failed"]]
    }
    
    if department:
        filters["department"] = department
    
    # Get salary slips with SeerBit enabled employees
    salary_slips = frappe.db.sql("""
        SELECT ss.name, ss.employee, ss.employee_name, ss.net_pay, ss.department
        FROM `tabSalary Slip` ss
        INNER JOIN `tabEmployee` e ON ss.employee = e.name
        WHERE ss.company = %(company)s
        AND ss.start_date LIKE %(salary_month)s
        AND ss.docstatus = 1
        AND ss.net_pay > 0
        AND (ss.seerbit_payout_status IS NULL OR ss.seerbit_payout_status IN ('Not Initiated', 'Failed'))
        AND e.seerbit_payout_enabled = 1
        AND e.seerbit_bank_code IS NOT NULL
        AND e.bank_ac_no IS NOT NULL
        {department_filter}
        ORDER BY ss.employee_name
    """.format(
        department_filter="AND ss.department = %(department)s" if department else ""
    ), {
        "company": company,
        "salary_month": f"{salary_month}%",
        "department": department
    }, as_dict=True)
    
    return salary_slips

@frappe.whitelist()
def process_bulk_salary_payouts(salary_slip_names):
    """Process bulk salary payouts via SeerBit"""
    if isinstance(salary_slip_names, str):
        import json
        salary_slip_names = json.loads(salary_slip_names)
    
    successful_count = 0
    failed_count = 0
    failed_slips = []
    
    settings = frappe.get_doc("SeerBit Settings")
    if not settings.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    for slip_name in salary_slip_names:
        try:
            result = initiate_salary_payout(slip_name)
            if result.get("status") == "success":
                successful_count += 1
            else:
                failed_count += 1
                failed_slips.append({"slip": slip_name, "error": "Payout initiation failed"})
        except Exception as e:
            failed_count += 1
            failed_slips.append({"slip": slip_name, "error": str(e)})
            frappe.log_error(f"Bulk payout failed for {slip_name}: {str(e)}", "SeerBit Bulk Payout Error")
    
    return {
        "successful_count": successful_count,
        "failed_count": failed_count,
        "failed_slips": failed_slips
    }

@frappe.whitelist()
def get_payout_dashboard_data(company=None):
    """Get SeerBit payout dashboard data"""
    filters = {}
    if company:
        filters["company"] = company
    
    # Get payout statistics
    stats = frappe.db.sql("""
        SELECT 
            status,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM `tabSeerBit Payout`
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY status
    """, as_dict=True)
    
    # Get recent payouts
    recent_payouts = frappe.db.sql("""
        SELECT 
            name, beneficiary_name, amount, currency, status, created_at,
            beneficiary_type, payout_reference
        FROM `tabSeerBit Payout`
        ORDER BY created_at DESC
        LIMIT 10
    """, as_dict=True)
    
    return {
        "stats": stats,
        "recent_payouts": recent_payouts
    }

def validate_payout_eligibility(beneficiary_type, beneficiary_name):
    """Validate if beneficiary is eligible for SeerBit payout"""
    if beneficiary_type == "Employee":
        employee = frappe.get_doc("Employee", beneficiary_name)
        if not employee.seerbit_payout_enabled:
            return False, "SeerBit payout not enabled for employee"
        if not employee.seerbit_bank_code:
            return False, "SeerBit bank code not set for employee"
        if not employee.bank_ac_no:
            return False, "Bank account number not set for employee"
    
    elif beneficiary_type == "Supplier":
        supplier = frappe.get_doc("Supplier", beneficiary_name)
        if not supplier.seerbit_payout_enabled:
            return False, "SeerBit payout not enabled for supplier"
        if not supplier.seerbit_bank_code:
            return False, "SeerBit bank code not set for supplier"
        if not supplier.default_bank_account:
            return False, "Default bank account not set for supplier"
    
    return True, "Eligible for payout"

@frappe.whitelist()
def retry_failed_payout(payout_name):
    """Retry a failed SeerBit payout"""
    payout = frappe.get_doc("SeerBit Payout", payout_name)
    
    if payout.status not in ["Failed", "Pending"]:
        frappe.throw(_("Only failed or pending payouts can be retried"))
    
    settings = frappe.get_doc("SeerBit Settings")
    
    try:
        result = settings.initiate_payout(
            beneficiary_name=payout.beneficiary_name,
            beneficiary_email=payout.beneficiary_email,
            amount=payout.amount,
            currency=payout.currency,
            bank_account=payout.bank_account,
            bank_code=payout.bank_code,
            bank_name=payout.bank_name,
            narration=payout.narration,
            beneficiary_type=payout.beneficiary_type,
            beneficiary_mobile=payout.beneficiary_mobile
        )
        
        if result.get("status") == "success":
            payout.status = "Processing"
            payout.gateway_response = frappe.as_json(result)
            payout.save(ignore_permissions=True)
            
            return {"status": "success", "message": "Payout retry initiated successfully"}
        else:
            return {"status": "error", "message": "Payout retry failed"}
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Payout Retry Error for {payout_name}")
        return {"status": "error", "message": str(e)}
