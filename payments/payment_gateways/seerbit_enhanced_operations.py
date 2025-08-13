# Enhanced Bulk SeerBit Operations for ERPNext Integration
import frappe
from frappe import _
from payments.payment_gateways.seerbit_account_utils import verify_bank_account

@frappe.whitelist()
def get_payroll_eligible_employees(company, payroll_period=None, department=None):
    """
    Get employees eligible for SeerBit salary payouts with account verification
    """
    filters = {
        "company": company,
        "status": "Active",
        "seerbit_payout_enabled": 1
    }
    
    if department:
        filters["department"] = department
    
    sql_query = """
        SELECT 
            e.name as employee_id,
            e.employee_name,
            e.department,
            e.designation,
            e.bank_ac_no,
            e.seerbit_bank_code,
            e.company_email,
            e.personal_email,
            COALESCE(sbc.bank_name, 'Unknown Bank') as bank_name,
            CASE 
                WHEN e.bank_ac_no IS NULL OR e.bank_ac_no = '' THEN 'Missing Bank Account'
                WHEN e.seerbit_bank_code IS NULL OR e.seerbit_bank_code = '' THEN 'Missing Bank Code'
                ELSE 'Ready'
            END as readiness_status
        FROM 
            `tabEmployee` e
        LEFT JOIN 
            `tabSeerBit Bank Code` sbc ON e.seerbit_bank_code = sbc.name
        WHERE 
            e.company = %(company)s
            AND e.status = 'Active'
            AND e.seerbit_payout_enabled = 1
            {department_filter}
        ORDER BY 
            e.employee_name
    """.format(
        department_filter="AND e.department = %(department)s" if department else ""
    )
    
    employees = frappe.db.sql(sql_query, {
        "company": company,
        "department": department
    }, as_dict=True)
    
    return {
        "employees": employees,
        "total_count": len(employees),
        "ready_count": len([e for e in employees if e.readiness_status == "Ready"]),
        "missing_bank_account": len([e for e in employees if e.readiness_status == "Missing Bank Account"]),
        "missing_bank_code": len([e for e in employees if e.readiness_status == "Missing Bank Code"])
    }

@frappe.whitelist()
def get_supplier_eligible_for_payouts(company, supplier_group=None):
    """
    Get suppliers eligible for SeerBit payouts
    """
    filters = {
        "company": company,
        "disabled": 0,
        "seerbit_payout_enabled": 1
    }
    
    if supplier_group:
        filters["supplier_group"] = supplier_group
    
    sql_query = """
        SELECT 
            s.name as supplier_id,
            s.supplier_name,
            s.supplier_group,
            s.email_id,
            s.mobile_no,
            s.default_bank_account,
            s.seerbit_bank_code,
            ba.bank_account_no,
            ba.bank,
            COALESCE(sbc.bank_name, 'Unknown Bank') as seerbit_bank_name,
            CASE 
                WHEN s.default_bank_account IS NULL OR s.default_bank_account = '' THEN 'Missing Bank Account'
                WHEN s.seerbit_bank_code IS NULL OR s.seerbit_bank_code = '' THEN 'Missing Bank Code'
                WHEN ba.bank_account_no IS NULL OR ba.bank_account_no = '' THEN 'Missing Account Number'
                ELSE 'Ready'
            END as readiness_status
        FROM 
            `tabSupplier` s
        LEFT JOIN 
            `tabBank Account` ba ON s.default_bank_account = ba.name
        LEFT JOIN 
            `tabSeerBit Bank Code` sbc ON s.seerbit_bank_code = sbc.name
        WHERE 
            s.company = %(company)s
            AND s.disabled = 0
            AND s.seerbit_payout_enabled = 1
            {supplier_group_filter}
        ORDER BY 
            s.supplier_name
    """.format(
        supplier_group_filter="AND s.supplier_group = %(supplier_group)s" if supplier_group else ""
    )
    
    suppliers = frappe.db.sql(sql_query, {
        "company": company,
        "supplier_group": supplier_group
    }, as_dict=True)
    
    return {
        "suppliers": suppliers,
        "total_count": len(suppliers),
        "ready_count": len([s for s in suppliers if s.readiness_status == "Ready"]),
        "missing_bank_account": len([s for s in suppliers if s.readiness_status == "Missing Bank Account"]),
        "missing_bank_code": len([s for s in suppliers if s.readiness_status == "Missing Bank Code"])
    }

@frappe.whitelist()
def verify_employee_bank_accounts(employee_list):
    """
    Bulk verify employee bank accounts using SeerBit Account Enquiry
    """
    if isinstance(employee_list, str):
        import json
        employee_list = json.loads(employee_list)
    
    verification_results = []
    
    for employee_id in employee_list:
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
        
        try:
            result = verify_bank_account(employee.bank_ac_no, employee.seerbit_bank_code)
            verification_results.append({
                "employee_id": employee_id,
                "employee_name": employee.employee_name,
                "account_number": employee.bank_ac_no,
                "bank_code": employee.seerbit_bank_code,
                **result
            })
            
            # Update employee record with verification status
            if result.get("verified"):
                employee.db_set("account_verification_status", "Verified")
                employee.db_set("verified_account_name", result.get("account_name"))
            else:
                employee.db_set("account_verification_status", "Failed")
                
        except Exception as e:
            verification_results.append({
                "employee_id": employee_id,
                "employee_name": employee.employee_name,
                "status": "failed",
                "message": str(e),
                "verified": False
            })
    
    return {
        "status": "completed",
        "results": verification_results,
        "total_processed": len(verification_results),
        "verified_count": len([r for r in verification_results if r.get("verified")])
    }

@frappe.whitelist()
def process_bulk_salary_payouts_enhanced(salary_slip_names, verify_accounts=True):
    """
    Process bulk salary payouts with enhanced SeerBit flow
    """
    if isinstance(salary_slip_names, str):
        import json
        salary_slip_names = json.loads(salary_slip_names)
    
    results = []
    successful_count = 0
    failed_count = 0
    
    settings = frappe.get_doc("SeerBit Settings")
    
    if not settings.is_enabled or not settings.enable_payouts:
        frappe.throw(_("SeerBit enhanced payouts are not enabled"))
    
    for slip_name in salary_slip_names:
        try:
            salary_slip = frappe.get_doc("Salary Slip", slip_name)
            employee = frappe.get_doc("Employee", salary_slip.employee)
            
            # Verify account if requested
            if verify_accounts:
                verification_result = verify_bank_account(employee.bank_ac_no, employee.seerbit_bank_code)
                if not verification_result.get("verified"):
                    results.append({
                        "slip_name": slip_name,
                        "employee_name": employee.employee_name,
                        "status": "failed",
                        "message": f"Account verification failed: {verification_result.get('message')}",
                        "stage": "verification"
                    })
                    failed_count += 1
                    continue
            
            # Initiate enhanced payout
            from payments.payment_gateways.doctype.seerbit_payout.seerbit_payout import initiate_salary_payout
            
            # Use enhanced version if available
            try:
                from payments.payment_gateways.doctype.seerbit_settings.seerbit_payout_enhanced import initiate_salary_payout_enhanced
                payout_result = initiate_salary_payout_enhanced(slip_name)
            except ImportError:
                # Fallback to regular method
                payout_result = initiate_salary_payout(slip_name)
            
            if payout_result.get("status") == "success":
                results.append({
                    "slip_name": slip_name,
                    "employee_name": employee.employee_name,
                    "status": "success",
                    "payout_reference": payout_result.get("payout_reference"),
                    "amount": salary_slip.net_pay,
                    "stage": "payout_initiated"
                })
                successful_count += 1
            else:
                results.append({
                    "slip_name": slip_name,
                    "employee_name": employee.employee_name,
                    "status": "failed",
                    "message": "Payout initiation failed",
                    "stage": "payout_initiation"
                })
                failed_count += 1
                
        except Exception as e:
            results.append({
                "slip_name": slip_name,
                "status": "failed",
                "message": str(e),
                "stage": "processing"
            })
            failed_count += 1
            frappe.log_error(f"Bulk payout error for {slip_name}: {str(e)}", "SeerBit Bulk Payout Error")
    
    return {
        "status": "completed",
        "successful_count": successful_count,
        "failed_count": failed_count,
        "results": results,
        "total_processed": len(salary_slip_names)
    }

@frappe.whitelist()
def get_payout_dashboard_enhanced():
    """
    Enhanced payout dashboard with method breakdown
    """
    # Get payout statistics by method
    stats = frappe.db.sql("""
        SELECT 
            status,
            payout_method,
            COUNT(*) as count,
            SUM(amount) as total_amount,
            AVG(amount) as avg_amount
        FROM `tabSeerBit Payout`
        WHERE created >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY status, payout_method
        ORDER BY status, payout_method
    """, as_dict=True)
    
    # Get recent payouts with enhanced details
    recent_payouts = frappe.db.sql("""
        SELECT 
            name, beneficiary_name, amount, currency, status, created_at,
            beneficiary_type, payout_reference, payout_method,
            account_verified, linking_reference
        FROM `tabSeerBit Payout`
        ORDER BY created_at DESC
        LIMIT 20
    """, as_dict=True)
    
    # Get pending verifications
    pending_verifications = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabSeerBit Payout`
        WHERE status IN ('Pending', 'Processing')
        AND created >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """, as_dict=True)
    
    # Get method adoption
    method_adoption = frappe.db.sql("""
        SELECT 
            payout_method,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM `tabSeerBit Payout`
        WHERE created >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY payout_method
    """, as_dict=True)
    
    return {
        "stats": stats,
        "recent_payouts": recent_payouts,
        "pending_verifications": pending_verifications[0]["count"] if pending_verifications else 0,
        "method_adoption": method_adoption,
        "dashboard_generated_at": frappe.utils.now()
    }

@frappe.whitelist()
def validate_payout_prerequisites(beneficiary_type, beneficiary_name):
    """
    Validate all prerequisites for SeerBit payout
    """
    validation_results = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "beneficiary_details": {}
    }
    
    try:
        if beneficiary_type == "Employee":
            employee = frappe.get_doc("Employee", beneficiary_name)
            validation_results["beneficiary_details"] = {
                "name": employee.employee_name,
                "email": employee.company_email or employee.personal_email,
                "bank_account": employee.bank_ac_no,
                "bank_code": employee.seerbit_bank_code,
                "payout_enabled": employee.seerbit_payout_enabled
            }
            
            if not employee.seerbit_payout_enabled:
                validation_results["errors"].append("SeerBit payout not enabled for employee")
                validation_results["is_valid"] = False
            
            if not employee.bank_ac_no:
                validation_results["errors"].append("Bank account number not set")
                validation_results["is_valid"] = False
            
            if not employee.seerbit_bank_code:
                validation_results["errors"].append("SeerBit bank code not set")
                validation_results["is_valid"] = False
            
            if not employee.company_email and not employee.personal_email:
                validation_results["warnings"].append("No email address configured")
                
        elif beneficiary_type == "Supplier":
            supplier = frappe.get_doc("Supplier", beneficiary_name)
            bank_account = None
            
            if supplier.default_bank_account:
                bank_account = frappe.get_doc("Bank Account", supplier.default_bank_account)
            
            validation_results["beneficiary_details"] = {
                "name": supplier.supplier_name,
                "email": supplier.email_id,
                "bank_account": bank_account.bank_account_no if bank_account else None,
                "bank_code": supplier.seerbit_bank_code,
                "payout_enabled": supplier.seerbit_payout_enabled
            }
            
            if not supplier.seerbit_payout_enabled:
                validation_results["errors"].append("SeerBit payout not enabled for supplier")
                validation_results["is_valid"] = False
            
            if not supplier.default_bank_account:
                validation_results["errors"].append("Default bank account not set")
                validation_results["is_valid"] = False
            elif not bank_account or not bank_account.bank_account_no:
                validation_results["errors"].append("Bank account number not found")
                validation_results["is_valid"] = False
            
            if not supplier.seerbit_bank_code:
                validation_results["errors"].append("SeerBit bank code not set")
                validation_results["is_valid"] = False
            
            if not supplier.email_id:
                validation_results["warnings"].append("No email address configured")
        
        # Verify account if all basic requirements are met
        if (validation_results["is_valid"] and 
            validation_results["beneficiary_details"].get("bank_account") and 
            validation_results["beneficiary_details"].get("bank_code")):
            
            try:
                verification_result = verify_bank_account(
                    validation_results["beneficiary_details"]["bank_account"],
                    validation_results["beneficiary_details"]["bank_code"]
                )
                validation_results["account_verification"] = verification_result
                
                if not verification_result.get("verified"):
                    validation_results["errors"].append(f"Account verification failed: {verification_result.get('message')}")
                    validation_results["is_valid"] = False
                    
            except Exception as e:
                validation_results["warnings"].append(f"Could not verify account: {str(e)}")
        
    except Exception as e:
        validation_results["errors"].append(f"Error validating beneficiary: {str(e)}")
        validation_results["is_valid"] = False
    
    return validation_results
