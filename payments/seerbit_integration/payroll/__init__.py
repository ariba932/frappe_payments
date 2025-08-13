# -*- coding: utf-8 -*-
"""
SeerBit Payroll Module - Salary and Staff Advance Payments
"""

from .salary_payments import (
    SeerBitPayrollOperations,
    process_salary_payment_completion,
    process_advance_payment_completion,
    initiate_salary_payout,
    initiate_staff_advance_payout,
    process_bulk_salary_payouts,
    get_payroll_summary,
    get_eligible_salary_slips,
    get_eligible_employee_advances
)

__all__ = [
    'SeerBitPayrollOperations',
    'process_salary_payment_completion',
    'process_advance_payment_completion',
    'initiate_salary_payout',
    'initiate_staff_advance_payout',
    'process_bulk_salary_payouts',
    'get_payroll_summary',
    'get_eligible_salary_slips',
    'get_eligible_employee_advances'
]
