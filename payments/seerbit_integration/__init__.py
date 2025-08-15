# -*- coding: utf-8 -*-
"""
SeerBit Integration Module - Complete modularized SeerBit integration for ERPNext
Provides unified interface for all SeerBit operations including:
- Selling operations (Invoice & Sales Order payments)
- Buying operations (Supplier payments & general payouts)
- Payroll operations (Salary payments & staff advances)
- Core API client and gateway functionality
- Utility functions for account verification, bank management, and reporting
"""

# Core functionality
from .core import (
    SeerBitAPIClient,
    get_api_client,
    SeerBitGateway,
    get_gateway,
    SeerBitWebhookHandler
)

# Selling operations (payments)
from .selling import (
    SeerBitSellingOperations,
    create_invoice_payment_link,
    create_sales_order_advance_payment,
    send_payment_link_email,
    get_sales_order_payment_status,
    create_balance_payment_link
)

# Buying operations (payouts)
from .buying import (
    SeerBitBuyingOperations,
    initiate_supplier_payment,
    initiate_general_payout,
    process_bulk_supplier_payments,
    get_payout_status,
    get_eligible_purchase_invoices
)

# Payroll operations
from .payroll import (
    SeerBitPayrollOperations,
    initiate_salary_payout,
    initiate_staff_advance_payout,
    process_bulk_salary_payouts,
    get_payroll_summary,
    get_eligible_salary_slips,
    get_eligible_employee_advances
)

# Utilities
from .utils import (
    verify_beneficiary_account,
    verify_employee_bank_accounts,
    verify_supplier_bank_accounts,
    sync_bank_codes_from_seerbit,
    get_bank_code_options,
    get_comprehensive_dashboard_data
)

__version__ = "2.0.0"
__title__ = "SeerBit Integration for ERPNext"
__description__ = "Complete modularized SeerBit payment gateway integration"

__all__ = [
    # Core
    'SeerBitAPIClient',
    'get_api_client',
    'SeerBitGateway', 
    'get_gateway',
    'SeerBitWebhookHandler',
    
    # Selling
    'SeerBitSellingOperations',
    'create_invoice_payment_link',
    'create_sales_order_advance_payment',
    'send_payment_link_email',
    'get_sales_order_payment_status',
    'create_balance_payment_link',
    
    # Buying
    'SeerBitBuyingOperations',
    'initiate_supplier_payment',
    'initiate_general_payout',
    'process_bulk_supplier_payments',
    'get_payout_status',
    'get_eligible_purchase_invoices',
    
    # Payroll
    'SeerBitPayrollOperations',
    'initiate_salary_payout',
    'initiate_staff_advance_payout',
    'process_bulk_salary_payouts',
    'get_payroll_summary',
    'get_eligible_salary_slips',
    'get_eligible_employee_advances',
    
    # Utilities
    'verify_beneficiary_account',
    'verify_employee_bank_accounts',
    'verify_supplier_bank_accounts',
    'sync_bank_codes_from_seerbit',
    'get_bank_code_options',
    'get_comprehensive_dashboard_data'
]


def get_integration_info():
    """Get integration information and status"""
    import frappe
    
    try:
        from .core.api_client import get_seerbit_settings
        settings = get_seerbit_settings()
        
        return {
            "version": __version__,
            "title": __title__,
            "description": __description__,
            "enabled": settings.is_active,
            "sandbox_mode": settings.sandbox_mode,
            "payouts_enabled": settings.get("enable_payouts", 0),
            "modules": {
                "core": "API Client, Gateway, Webhooks",
                "selling": "Invoice & Sales Order Payments",
                "buying": "Supplier Payments & General Payouts", 
                "payroll": "Salary & Staff Advance Payments",
                "utils": "Account Verification, Bank Management, Reporting"
            },
            "api_endpoints": {
                "core": [
                    "/api/method/payments.seerbit_integration.core.gateway.create_payment_request",
                    "/api/method/payments.seerbit_integration.core.gateway.verify_payment_status",
                    "/api/method/payments.seerbit_integration.core.webhooks.webhook_handler"
                ],
                "selling": [
                    "/api/method/payments.seerbit_integration.selling.create_invoice_payment_link",
                    "/api/method/payments.seerbit_integration.selling.create_sales_order_advance_payment"
                ],
                "buying": [
                    "/api/method/payments.seerbit_integration.buying.initiate_supplier_payment",
                    "/api/method/payments.seerbit_integration.buying.initiate_general_payout"
                ],
                "payroll": [
                    "/api/method/payments.seerbit_integration.payroll.initiate_salary_payout",
                    "/api/method/payments.seerbit_integration.payroll.process_bulk_salary_payouts"
                ]
            }
        }
        
    except Exception as e:
        return {
            "version": __version__,
            "title": __title__,
            "description": __description__,
            "error": str(e),
            "enabled": False
        }


# API endpoint for getting integration info
import frappe

@frappe.whitelist()
def get_seerbit_integration_info():
    """API endpoint to get SeerBit integration information"""
    return get_integration_info()
