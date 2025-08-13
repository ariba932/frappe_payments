# -*- coding: utf-8 -*-
# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt
import unittest
import frappe
from frappe.utils import nowdate


class TestSeerBitSalaryPayout(unittest.TestCase):
    """Test cases for SeerBit Salary Payout"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_employee = self.create_test_employee()
        self.test_salary_slip = self.create_test_salary_slip()
    
    def create_test_employee(self):
        """Create test employee"""
        employee = frappe.new_doc("Employee")
        employee.first_name = "Test"
        employee.last_name = "Employee"
        employee.employee_name = "Test Employee"
        employee.gender = "Male"
        employee.date_of_birth = "1990-01-01"
        employee.date_of_joining = nowdate()
        employee.company = frappe.defaults.get_defaults().company
        employee.bank_ac_no = "1234567890"
        employee.seerbit_bank_code = "044"
        employee.seerbit_payout_enabled = 1
        employee.insert(ignore_permissions=True)
        return employee
    
    def create_test_salary_slip(self):
        """Create test salary slip"""
        salary_slip = frappe.new_doc("Salary Slip")
        salary_slip.employee = self.test_employee.name
        salary_slip.employee_name = self.test_employee.employee_name
        salary_slip.company = self.test_employee.company
        salary_slip.posting_date = nowdate()
        salary_slip.start_date = nowdate()
        salary_slip.end_date = nowdate()
        salary_slip.net_pay = 50000
        salary_slip.gross_pay = 50000
        salary_slip.insert(ignore_permissions=True)
        return salary_slip
    
    def test_create_salary_payout(self):
        """Test creating salary payout"""
        payout = frappe.new_doc("SeerBit Salary Payout")
        payout.payout_type = "Salary"
        payout.salary_slip = self.test_salary_slip.name
        payout.employee = self.test_employee.name
        payout.payout_amount = 50000
        payout.bank_account_number = "1234567890"
        payout.bank_code = "044"
        payout.save()
        
        self.assertEqual(payout.employee_name, "Test Employee")
        self.assertEqual(payout.payout_amount, 50000)
    
    def test_validation_missing_employee(self):
        """Test validation with missing employee"""
        payout = frappe.new_doc("SeerBit Salary Payout")
        payout.payout_type = "Salary"
        payout.payout_amount = 50000
        
        with self.assertRaises(frappe.ValidationError):
            payout.save()
    
    def test_auto_fill_from_salary_slip(self):
        """Test auto-filling data from salary slip"""
        payout = frappe.new_doc("SeerBit Salary Payout")
        payout.payout_type = "Salary"
        payout.salary_slip = self.test_salary_slip.name
        payout.save()
        
        self.assertEqual(payout.employee, self.test_employee.name)
        self.assertEqual(payout.payout_amount, 50000)
    
    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, 'test_salary_slip'):
            frappe.delete_doc("Salary Slip", self.test_salary_slip.name, force=True)
        if hasattr(self, 'test_employee'):
            frappe.delete_doc("Employee", self.test_employee.name, force=True)
