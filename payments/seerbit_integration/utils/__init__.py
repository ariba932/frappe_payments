# -*- coding: utf-8 -*-
"""
SeerBit Utils Module - Utility functions for SeerBit integration
"""

from .account_verification import (
    verify_beneficiary_account,
    verify_employee_bank_accounts,
    verify_supplier_bank_accounts,
    verify_single_account,
    verify_employee_accounts,
    verify_supplier_accounts
)

from .bank_management import (
    sync_bank_codes_from_seerbit,
    sync_to_erpnext_bank,
    get_bank_code_options,
    validate_bank_code,
    get_bank_name_by_code,
    search_bank_codes,
    sync_banks,
    get_bank_options,
    search_banks,
    validate_bank
)

from .dashboard import (
    get_payment_dashboard_data,
    get_payout_dashboard_data,
    get_comprehensive_dashboard_data,
    get_employee_payout_summary,
    get_supplier_payout_summary,
    get_payment_dashboard,
    get_payout_dashboard,
    get_comprehensive_dashboard,
    get_employee_dashboard,
    get_supplier_dashboard
)

__all__ = [
    # Account verification
    'verify_beneficiary_account',
    'verify_employee_bank_accounts',
    'verify_supplier_bank_accounts',
    'verify_single_account',
    'verify_employee_accounts',
    'verify_supplier_accounts',
    
    # Bank management
    'sync_bank_codes_from_seerbit',
    'sync_to_erpnext_bank',
    'get_bank_code_options',
    'validate_bank_code',
    'get_bank_name_by_code',
    'search_bank_codes',
    'sync_banks',
    'get_bank_options',
    'search_banks',
    'validate_bank',
    
    # Dashboard and reporting
    'get_payment_dashboard_data',
    'get_payout_dashboard_data',
    'get_comprehensive_dashboard_data',
    'get_employee_payout_summary',
    'get_supplier_payout_summary',
    'get_payment_dashboard',
    'get_payout_dashboard',
    'get_comprehensive_dashboard',
    'get_employee_dashboard',
    'get_supplier_dashboard'
]
