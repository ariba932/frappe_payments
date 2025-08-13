# -*- coding: utf-8 -*-
"""
SeerBit Payroll Operations - Salary and Staff Advance Payment Processing
Handles all payroll-related SeerBit operations including salary payouts and staff advances
"""

import frappe
from frappe import _
from frappe.utils import nowdate, getdate, flt
from ..core.api_client import get_api_client
from ..utils.account_verification import verify_beneficiary_account


class SeerBitPayrollOperations:
    """Handles all payroll/HR payout operations"""
    
    def __init__(self):
        self.settings = frappe.get_doc("SeerBit Settings")
        self.api_client = get_api_client(self.settings)
        
        if not self.settings.is_enabled:
            frappe.throw(_("SeerBit is not enabled"))
        
        if not self.settings.enable_payouts:
            frappe.throw(_("SeerBit payouts are not enabled"))
    
    def initiate_salary_payout(self, salary_slip_name, verify_account=True):
        """Initiate salary payout for employee"""
        salary_slip = frappe.get_doc("Salary Slip", salary_slip_name)
        employee = frappe.get_doc("Employee", salary_slip.employee)
        
        # Validate employee setup
        self._validate_employee_payout_setup(employee)
        
        if verify_account:
            # Verify employee bank account
            verification_result = verify_beneficiary_account(
                employee.bank_ac_no,
                employee.seerbit_bank_code,
                employee.employee_name
            )
            
            if not verification_result.get("verified"):
                frappe.throw(_("Employee account verification failed: {0}").format(
                    verification_result.get("message", "Unknown error")
                ))
        
        # Generate payout reference
        payout_reference = f"SAL-{salary_slip.name}-{frappe.generate_hash(length=8)}"
        
        # Prepare payout data
        payout_data = {
            "reference": payout_reference,
            "amount": salary_slip.net_pay,
            "currency": salary_slip.currency or "NGN",
            "bank_account": employee.bank_ac_no,
            "bank_code": employee.seerbit_bank_code,
            "beneficiary_name": employee.employee_name,
            "beneficiary_email": employee.company_email or employee.personal_email or "",
            "narration": f"Salary payment for {salary_slip.employee_name} - {salary_slip.payroll_period}",
            "beneficiary_mobile": employee.cell_number or ""
        }
        
        try:
            # Use enhanced payout if available
            if self.settings.get("use_enhanced_payouts", 0):
                result = self._initiate_enhanced_payout(payout_data)
            else:
                result = self.api_client.initiate_payout(**payout_data)
            
            # Create SeerBit Payout record
            payout_doc = self._create_payout_record(payout_data, result, {
                "salary_slip_name": salary_slip.name,
                "employee_id": employee.name,
                "employee_name": employee.employee_name,
                "department": employee.department,
                "designation": employee.designation,
                "payroll_period": salary_slip.payroll_period,
                "document_type": "Salary Slip"
            })
            
            # Update salary slip
            salary_slip.db_set("seerbit_payout_reference", payout_reference)
            salary_slip.db_set("seerbit_payout_status", "Processing")
            
            return {
                "status": "success",
                "payout_reference": payout_reference,
                "payout_id": payout_doc.name,
                "amount": salary_slip.net_pay,
                "employee": employee.employee_name
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Salary Payout Error for {salary_slip_name}")
            frappe.throw(_("Failed to initiate salary payout: {0}").format(str(e)))
    
    def initiate_staff_advance_payout(self, employee_advance_name, verify_account=True):
        """Initiate payout for employee advance"""
        employee_advance = frappe.get_doc("Employee Advance", employee_advance_name)
        employee = frappe.get_doc("Employee", employee_advance.employee)
        
        # Validate employee setup
        self._validate_employee_payout_setup(employee)
        
        if employee_advance.paid_amount > 0:
            frappe.throw(_("Employee Advance has already been paid"))
        
        if verify_account:
            # Verify employee bank account
            verification_result = verify_beneficiary_account(
                employee.bank_ac_no,
                employee.seerbit_bank_code,
                employee.employee_name
            )
            
            if not verification_result.get("verified"):
                frappe.throw(_("Employee account verification failed: {0}").format(
                    verification_result.get("message", "Unknown error")
                ))
        
        # Generate payout reference
        payout_reference = f"ADV-{employee_advance.name}-{frappe.generate_hash(length=8)}"
        
        # Prepare payout data
        payout_data = {
            "reference": payout_reference,
            "amount": employee_advance.advance_amount,
            "currency": employee_advance.currency or "NGN",
            "bank_account": employee.bank_ac_no,
            "bank_code": employee.seerbit_bank_code,
            "beneficiary_name": employee.employee_name,
            "beneficiary_email": employee.company_email or employee.personal_email or "",
            "narration": f"Staff advance payment for {employee.employee_name} - {employee_advance.purpose}",
            "beneficiary_mobile": employee.cell_number or ""
        }
        
        try:
            # Use enhanced payout if available
            if self.settings.get("use_enhanced_payouts", 0):
                result = self._initiate_enhanced_payout(payout_data)
            else:
                result = self.api_client.initiate_payout(**payout_data)
            
            # Create SeerBit Payout record
            payout_doc = self._create_payout_record(payout_data, result, {
                "employee_advance_name": employee_advance.name,
                "employee_id": employee.name,
                "employee_name": employee.employee_name,
                "department": employee.department,
                "designation": employee.designation,
                "advance_purpose": employee_advance.purpose,
                "document_type": "Employee Advance"
            })
            
            # Update employee advance
            employee_advance.db_set("seerbit_payout_reference", payout_reference)
            employee_advance.db_set("seerbit_payout_status", "Processing")
            
            return {
                "status": "success",
                "payout_reference": payout_reference,
                "payout_id": payout_doc.name,
                "amount": employee_advance.advance_amount,
                "employee": employee.employee_name
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Staff Advance Payout Error for {employee_advance_name}")
            frappe.throw(_("Failed to initiate staff advance payout: {0}").format(str(e)))
    
    def process_bulk_salary_payouts(self, salary_slip_names, verify_accounts=True):
        """Process bulk salary payouts"""
        if isinstance(salary_slip_names, str):
            import json
            salary_slip_names = json.loads(salary_slip_names)
        
        results = []
        successful_count = 0
        failed_count = 0
        
        for slip_name in salary_slip_names:
            try:
                result = self.initiate_salary_payout(slip_name, verify_accounts)
                results.append({
                    "salary_slip": slip_name,
                    "employee": result["employee"],
                    "status": "success",
                    "payout_reference": result["payout_reference"],
                    "amount": result["amount"]
                })
                successful_count += 1
                
            except Exception as e:
                results.append({
                    "salary_slip": slip_name,
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1
                frappe.log_error(f"Bulk salary payout failed for {slip_name}: {str(e)}", "SeerBit Bulk Salary Error")
        
        return {
            "status": "completed",
            "successful_count": successful_count,
            "failed_count": failed_count,
            "results": results,
            "total_processed": len(salary_slip_names)
        }
    
    def get_payroll_summary(self, company, payroll_period=None, department=None):
        """Get payroll payout summary"""
        filters = {
            "company": company
        }
        
        if payroll_period:
            filters["payroll_period"] = payroll_period
        if department:
            filters["department"] = department
        
        # Get salary slips with SeerBit payout data
        summary = frappe.db.sql("""
            SELECT 
                ss.department,
                COUNT(*) as total_employees,
                SUM(ss.net_pay) as total_amount,
                COUNT(CASE WHEN ss.seerbit_payout_status = 'Paid' THEN 1 END) as paid_count,
                SUM(CASE WHEN ss.seerbit_payout_status = 'Paid' THEN ss.net_pay ELSE 0 END) as paid_amount,
                COUNT(CASE WHEN ss.seerbit_payout_status = 'Processing' THEN 1 END) as processing_count,
                COUNT(CASE WHEN ss.seerbit_payout_status = 'Failed' THEN 1 END) as failed_count
            FROM `tabSalary Slip` ss
            INNER JOIN `tabEmployee` e ON ss.employee = e.name
            WHERE ss.company = %(company)s
            AND ss.docstatus = 1
            AND e.seerbit_payout_enabled = 1
            {payroll_filter}
            {department_filter}
            GROUP BY ss.department
            ORDER BY ss.department
        """.format(
            payroll_filter="AND ss.payroll_period = %(payroll_period)s" if payroll_period else "",
            department_filter="AND ss.department = %(department)s" if department else ""
        ), {
            "company": company,
            "payroll_period": payroll_period,
            "department": department
        }, as_dict=True)
        
        return summary
    
    def _validate_employee_payout_setup(self, employee):
        """Validate employee is properly set up for payouts"""
        if not employee.seerbit_payout_enabled:
            frappe.throw(_("SeerBit payouts not enabled for employee {0}").format(employee.name))
        
        if not employee.bank_ac_no:
            frappe.throw(_("Bank account not set for employee {0}").format(employee.name))
        
        if not employee.seerbit_bank_code:
            frappe.throw(_("SeerBit bank code not set for employee {0}").format(employee.name))
    
    def _initiate_enhanced_payout(self, payout_data):
        """Initiate enhanced payout with proper SeerBit flow"""
        try:
            # Step 1: Verify account first
            verification_result = self.api_client.verify_bank_account(
                payout_data["bank_account"],
                payout_data["bank_code"]
            )
            
            frappe.log_error(f"Account verification result: {verification_result}", "SeerBit Enhanced Payout")
            
            # Step 2: Generate OTP
            otp_result = self.api_client.generate_otp_for_payout()
            otp = otp_result.get("otp")
            
            if not otp:
                frappe.throw(_("Failed to generate OTP for payout"))
            
            frappe.log_error(f"OTP generated successfully", "SeerBit Enhanced Payout")
            
            # Step 3: Generate signature
            signature = self.api_client.generate_payout_signature(payout_data, otp)
            
            if not signature:
                frappe.throw(_("Failed to generate signature for payout"))
            
            frappe.log_error(f"Signature generated successfully", "SeerBit Enhanced Payout")
            
            # Step 4: Execute enhanced payout
            result = self.api_client.execute_enhanced_payout(payout_data, otp, signature)
            
            frappe.log_error(f"Enhanced payout executed successfully: {result}", "SeerBit Enhanced Payout")
            
            return result
            
        except Exception as e:
            frappe.log_error(f"Enhanced payout failed: {str(e)}", "SeerBit Enhanced Payout Error")
            # Fallback to legacy payout if enhanced fails
            frappe.log_error("Falling back to legacy payout method", "SeerBit Enhanced Payout")
            return self.api_client.initiate_payout(**payout_data)
    
    def _create_payout_record(self, payout_data, api_result, meta_data):
        """Create SeerBit Payout record for tracking"""
        payout_doc = frappe.get_doc({
            "doctype": "SeerBit Payout",
            "payout_reference": payout_data["reference"],
            "status": "Processing",
            "amount": payout_data["amount"],
            "currency": payout_data["currency"],
            "beneficiary_type": "Employee",
            "beneficiary_name": payout_data["beneficiary_name"],
            "beneficiary_email": payout_data["beneficiary_email"],
            "beneficiary_mobile": payout_data.get("beneficiary_mobile", ""),
            "bank_account": payout_data["bank_account"],
            "bank_code": payout_data["bank_code"],
            "narration": payout_data["narration"],
            "gateway_response": frappe.as_json(api_result),
            "meta_data": frappe.as_json(meta_data),
            "payout_method": "Enhanced" if self.settings.get("use_enhanced_payouts", 0) else "Legacy",
            "linking_reference": meta_data.get("salary_slip_name") or meta_data.get("employee_advance_name", "")
        })
        payout_doc.insert(ignore_permissions=True)
        return payout_doc


def process_salary_payment_completion(payout_reference, payment_data):
    """Process successful salary payment completion"""
    try:
        payout = frappe.get_doc("SeerBit Payout", {"payout_reference": payout_reference})
        meta_data = frappe.parse_json(payout.meta_data or "{}")
        salary_slip_name = meta_data.get("salary_slip_name")
        
        if not salary_slip_name:
            frappe.throw(_("Salary Slip name not found in payout metadata"))
        
        salary_slip = frappe.get_doc("Salary Slip", salary_slip_name)
        
        # Create Journal Entry for salary payment
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Bank Entry"
        je.company = salary_slip.company
        je.posting_date = nowdate()
        je.user_remark = f"SeerBit salary payment for {salary_slip.employee_name} - {salary_slip.payroll_period}"
        je.reference_no = payment_data.get("transactionRef") or payout.payout_reference
        je.reference_date = nowdate()
        
        # Debit salary payable account
        je.append("accounts", {
            "account": salary_slip.payroll_payable_account,
            "debit_in_account_currency": payout.amount,
            "party_type": "Employee",
            "party": salary_slip.employee
        })
        
        # Credit bank/cash account
        company = frappe.get_doc("Company", salary_slip.company)
        bank_account = company.default_cash_account or company.default_bank_account
        
        je.append("accounts", {
            "account": bank_account,
            "credit_in_account_currency": payout.amount
        })
        
        je.insert(ignore_permissions=True)
        je.submit()
        
        # Update salary slip status
        salary_slip.db_set("seerbit_payout_status", "Paid")
        
        # Update payout
        payout.payment_entry = je.name
        payout.status = "Paid"
        payout.save(ignore_permissions=True)
        
        return je
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Salary Payment Completion Error for {payout_reference}")
        frappe.throw(_("Failed to complete salary payment: {0}").format(str(e)))


def process_advance_payment_completion(payout_reference, payment_data):
    """Process successful staff advance payment completion"""
    try:
        payout = frappe.get_doc("SeerBit Payout", {"payout_reference": payout_reference})
        meta_data = frappe.parse_json(payout.meta_data or "{}")
        employee_advance_name = meta_data.get("employee_advance_name")
        
        if not employee_advance_name:
            frappe.throw(_("Employee Advance name not found in payout metadata"))
        
        employee_advance = frappe.get_doc("Employee Advance", employee_advance_name)
        
        # Create Payment Entry for advance
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Pay"
        payment_entry.party_type = "Employee"
        payment_entry.party = employee_advance.employee
        payment_entry.posting_date = nowdate()
        
        # Get company's default cash/bank account
        company = frappe.get_doc("Company", employee_advance.company)
        payment_entry.paid_from = company.default_cash_account or company.default_bank_account
        
        # Get employee advance account
        payment_entry.paid_to = employee_advance.advance_account
        
        payment_entry.paid_amount = float(payment_data.get("amount", payout.amount))
        payment_entry.received_amount = payment_entry.paid_amount
        payment_entry.reference_no = payment_data.get("transactionRef") or payout.payout_reference
        payment_entry.reference_date = nowdate()
        payment_entry.mode_of_payment = "SeerBit"
        
        # Link to employee advance
        payment_entry.append("references", {
            "reference_doctype": "Employee Advance",
            "reference_name": employee_advance.name,
            "allocated_amount": payment_entry.paid_amount
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update employee advance status
        employee_advance.db_set("seerbit_payout_status", "Paid")
        employee_advance.db_set("paid_amount", payout.amount)
        employee_advance.db_set("status", "Paid")
        
        # Update payout
        payout.payment_entry = payment_entry.name
        payout.status = "Paid"
        payout.save(ignore_permissions=True)
        
        return payment_entry
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Advance Payment Completion Error for {payout_reference}")
        frappe.throw(_("Failed to complete advance payment: {0}").format(str(e)))


# API endpoints
@frappe.whitelist()
def initiate_salary_payout(salary_slip_name, verify_account=True):
    """API endpoint for initiating salary payout"""
    payroll_ops = SeerBitPayrollOperations()
    return payroll_ops.initiate_salary_payout(salary_slip_name, verify_account)


@frappe.whitelist()
def initiate_staff_advance_payout(employee_advance_name, verify_account=True):
    """API endpoint for initiating staff advance payout"""
    payroll_ops = SeerBitPayrollOperations()
    return payroll_ops.initiate_staff_advance_payout(employee_advance_name, verify_account)


@frappe.whitelist()
def process_bulk_salary_payouts(salary_slip_names, verify_accounts=True):
    """API endpoint for bulk salary payouts"""
    payroll_ops = SeerBitPayrollOperations()
    return payroll_ops.process_bulk_salary_payouts(salary_slip_names, verify_accounts)


@frappe.whitelist()
def get_payroll_summary(company, payroll_period=None, department=None):
    """API endpoint for payroll summary"""
    payroll_ops = SeerBitPayrollOperations()
    return payroll_ops.get_payroll_summary(company, payroll_period, department)


@frappe.whitelist()
def get_eligible_salary_slips(company, payroll_period, department=None):
    """Get salary slips eligible for SeerBit payout"""
    filters = {
        "company": company,
        "payroll_period": payroll_period,
        "docstatus": 1,
        "net_pay": [">", 0],
        "seerbit_payout_status": ["in", ["Not Initiated", "Failed", ""]]
    }
    
    if department:
        filters["department"] = department
    
    # Get salary slips with SeerBit enabled employees
    slips = frappe.db.sql("""
        SELECT ss.name, ss.employee, ss.employee_name, ss.net_pay, 
               ss.department, ss.designation, ss.payroll_period
        FROM `tabSalary Slip` ss
        INNER JOIN `tabEmployee` e ON ss.employee = e.name
        WHERE ss.company = %(company)s
        AND ss.payroll_period = %(payroll_period)s
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
        "payroll_period": payroll_period,
        "department": department
    }, as_dict=True)
    
    return slips


@frappe.whitelist()
def get_eligible_employee_advances(company, from_date=None, to_date=None, department=None):
    """Get employee advances eligible for SeerBit payout"""
    filters = {
        "company": company,
        "docstatus": 1,
        "paid_amount": 0,
        "seerbit_payout_status": ["in", ["Not Initiated", "Failed", ""]]
    }
    
    if from_date:
        filters["posting_date"] = [">=", from_date]
    if to_date:
        filters.setdefault("posting_date", []).extend(["<=", to_date])
    
    # Get advances with SeerBit enabled employees
    advances = frappe.db.sql("""
        SELECT ea.name, ea.employee, ea.employee_name, ea.advance_amount, 
               ea.purpose, ea.posting_date, e.department
        FROM `tabEmployee Advance` ea
        INNER JOIN `tabEmployee` e ON ea.employee = e.name
        WHERE ea.company = %(company)s
        AND ea.docstatus = 1
        AND ea.paid_amount = 0
        AND (ea.seerbit_payout_status IS NULL OR ea.seerbit_payout_status IN ('Not Initiated', 'Failed'))
        AND e.seerbit_payout_enabled = 1
        AND e.seerbit_bank_code IS NOT NULL
        AND e.bank_ac_no IS NOT NULL
        {department_filter}
        {date_filter}
        ORDER BY ea.posting_date DESC
    """.format(
        department_filter="AND e.department = %(department)s" if department else "",
        date_filter="AND ea.posting_date BETWEEN %(from_date)s AND %(to_date)s" if from_date and to_date else ""
    ), {
        "company": company,
        "department": department,
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)
    
    return advances
