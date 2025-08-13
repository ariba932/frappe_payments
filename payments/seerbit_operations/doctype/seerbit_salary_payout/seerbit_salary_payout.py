# -*- coding: utf-8 -*-
# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, flt, nowdate
from payments.seerbit_integration.payroll.salary_payments import SeerBitPayrollOperations


class SeerBitSalaryPayout(Document):
    def validate(self):
        """Validate salary payout request"""
        if not self.employee:
            frappe.throw("Employee is required")
            
        if not self.payout_amount or self.payout_amount <= 0:
            frappe.throw("Payout amount must be greater than 0")
            
        # Auto-fill employee details if not set
        if self.employee and not self.employee_name:
            employee = frappe.get_doc("Employee", self.employee)
            self.employee_name = employee.employee_name
            self.department = employee.department
            self.designation = employee.designation
            
            # Auto-fill bank details from employee
            if not self.bank_account_number and employee.bank_ac_no:
                self.bank_account_number = employee.bank_ac_no
            if not self.bank_code and employee.seerbit_bank_code:
                self.bank_code = employee.seerbit_bank_code
                
        # Auto-fill amount from linked documents
        if self.payout_type == "Salary" and self.salary_slip:
            salary_slip = frappe.get_doc("Salary Slip", self.salary_slip)
            if not self.payout_amount:
                self.payout_amount = salary_slip.net_pay
            if not self.employee:
                self.employee = salary_slip.employee
                
        elif self.payout_type == "Advance" and self.employee_advance:
            advance = frappe.get_doc("Employee Advance", self.employee_advance)
            if not self.payout_amount:
                self.payout_amount = advance.advance_amount
            if not self.employee:
                self.employee = advance.employee
    
    def on_submit(self):
        """Process payout on submission"""
        if self.status != "Draft":
            frappe.throw("Can only submit payout requests in Draft status")
            
        # Verify account if required
        if self.verify_account and not self.account_verified:
            self.verify_bank_account()
            
        # Initiate payout
        self.initiate_payout()
    
    def verify_bank_account(self):
        """Verify beneficiary bank account"""
        try:
            from payments.seerbit_integration.utils.account_verification import verify_beneficiary_account
            
            result = verify_beneficiary_account(
                self.bank_account_number,
                self.bank_code,
                self.employee_name
            )
            
            if result.get("verified"):
                self.account_verified = 1
                self.verification_date = now()
                self.account_name = result.get("account_name", "")
                self.bank_name = result.get("bank_name", "")
                frappe.msgprint("Bank account verified successfully", alert=True)
            else:
                frappe.throw(f"Account verification failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            frappe.throw(f"Account verification failed: {str(e)}")
    
    def initiate_payout(self):
        """Initiate salary/advance payout"""
        try:
            payroll_ops = SeerBitPayrollOperations()
            
            if self.payout_type == "Salary" and self.salary_slip:
                result = payroll_ops.initiate_salary_payout(
                    self.salary_slip, 
                    verify_account=False  # Already verified if needed
                )
            elif self.payout_type == "Advance" and self.employee_advance:
                result = payroll_ops.initiate_staff_advance_payout(
                    self.employee_advance,
                    verify_account=False  # Already verified if needed
                )
            else:
                frappe.throw("Invalid payout configuration")
            
            # Update payout details
            self.payout_reference = result.get("payout_reference")
            self.status = "Processing"
            self.initiated_date = now()
            
            frappe.msgprint(f"Payout initiated successfully. Reference: {self.payout_reference}", alert=True)
            
        except Exception as e:
            self.status = "Failed"
            self.failure_reason = str(e)
            frappe.log_error(frappe.get_traceback(), f"Salary Payout Error - {self.name}")
            frappe.throw(f"Failed to initiate payout: {str(e)}")
    
    def update_payout_status(self, status, transaction_id=None, payment_entry=None, journal_entry=None):
        """Update payout status from webhook/external source"""
        self.status = status
        
        if transaction_id:
            self.seerbit_transaction_id = transaction_id
            
        if status == "Completed":
            self.completed_date = now()
            
        if payment_entry:
            self.payment_entry = payment_entry
            
        if journal_entry:
            self.journal_entry = journal_entry
            
        self.save(ignore_permissions=True)
    
    @frappe.whitelist()
    def retry_payout(self):
        """Retry failed payout"""
        if self.status not in ["Failed", "Cancelled"]:
            frappe.throw("Can only retry failed or cancelled payouts")
            
        self.status = "Draft"
        self.failure_reason = ""
        self.save()
        
        # Re-submit
        self.submit()


@frappe.whitelist()
def create_salary_payout_from_slip(salary_slip_name):
    """Create salary payout request from salary slip"""
    salary_slip = frappe.get_doc("Salary Slip", salary_slip_name)
    employee = frappe.get_doc("Employee", salary_slip.employee)
    
    # Check if payout already exists
    existing = frappe.db.exists("SeerBit Salary Payout", {
        "salary_slip": salary_slip_name,
        "docstatus": ["!=", 2]
    })
    
    if existing:
        frappe.throw(f"Salary payout already exists: {existing}")
    
    # Create new payout request
    payout = frappe.new_doc("SeerBit Salary Payout")
    payout.payout_type = "Salary"
    payout.salary_slip = salary_slip.name
    payout.employee = salary_slip.employee
    payout.employee_name = salary_slip.employee_name
    payout.department = employee.department
    payout.designation = employee.designation
    payout.payout_amount = salary_slip.net_pay
    payout.currency = salary_slip.currency or "NGN"
    payout.bank_account_number = employee.bank_ac_no
    payout.bank_code = employee.seerbit_bank_code
    payout.narration = f"Salary payment for {salary_slip.employee_name} - {salary_slip.payroll_period}"
    
    payout.insert()
    
    return payout.name


@frappe.whitelist()
def create_advance_payout_from_advance(employee_advance_name):
    """Create advance payout request from employee advance"""
    advance = frappe.get_doc("Employee Advance", employee_advance_name)
    employee = frappe.get_doc("Employee", advance.employee)
    
    # Check if payout already exists
    existing = frappe.db.exists("SeerBit Salary Payout", {
        "employee_advance": employee_advance_name,
        "docstatus": ["!=", 2]
    })
    
    if existing:
        frappe.throw(f"Advance payout already exists: {existing}")
    
    # Create new payout request
    payout = frappe.new_doc("SeerBit Salary Payout")
    payout.payout_type = "Advance"
    payout.employee_advance = advance.name
    payout.employee = advance.employee
    payout.employee_name = advance.employee_name
    payout.department = employee.department
    payout.designation = employee.designation
    payout.payout_amount = advance.advance_amount
    payout.currency = advance.currency or "NGN"
    payout.bank_account_number = employee.bank_ac_no
    payout.bank_code = employee.seerbit_bank_code
    payout.narration = f"Staff advance payment for {advance.employee_name} - {advance.purpose}"
    
    payout.insert()
    
    return payout.name


@frappe.whitelist()
def bulk_create_salary_payouts(salary_slip_names):
    """Create bulk salary payout requests"""
    if isinstance(salary_slip_names, str):
        import json
        salary_slip_names = json.loads(salary_slip_names)
    
    created_payouts = []
    failed_slips = []
    
    for slip_name in salary_slip_names:
        try:
            payout_name = create_salary_payout_from_slip(slip_name)
            created_payouts.append(payout_name)
        except Exception as e:
            failed_slips.append({
                "salary_slip": slip_name,
                "error": str(e)
            })
    
    return {
        "success_count": len(created_payouts),
        "failed_count": len(failed_slips),
        "created_payouts": created_payouts,
        "failed_slips": failed_slips
    }


@frappe.whitelist()
def get_eligible_salary_slips_for_payout(company, payroll_period, department=None):
    """Get salary slips eligible for SeerBit payout"""
    from payments.seerbit_integration.payroll.salary_payments import get_eligible_salary_slips
    return get_eligible_salary_slips(company, payroll_period, department)


@frappe.whitelist()
def get_eligible_advances_for_payout(company, from_date=None, to_date=None, department=None):
    """Get employee advances eligible for SeerBit payout"""
    from payments.seerbit_integration.payroll.salary_payments import get_eligible_employee_advances
    return get_eligible_employee_advances(company, from_date, to_date, department)
