# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_seerbit_custom_fields():
    """Create custom fields for SeerBit integration"""
    
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "seerbit_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payment",
                "insert_after": "payment_schedule",
                "collapsible": 1
            },
            {
                "fieldname": "enable_seerbit_payment",
                "fieldtype": "Check",
                "label": "Enable SeerBit Payment",
                "insert_after": "seerbit_section",
                "default": 0
            },
            {
                "fieldname": "seerbit_payment_request",
                "fieldtype": "Link",
                "label": "SeerBit Payment Request",
                "options": "SeerBit Payment Request",
                "insert_after": "enable_seerbit_payment",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_payment_link",
                "fieldtype": "Long Text",
                "label": "Payment Link",
                "insert_after": "seerbit_payment_request",
                "read_only": 1
            },
            {
                "fieldname": "column_break_seerbit",
                "fieldtype": "Column Break",
                "insert_after": "seerbit_payment_link"
            },
            {
                "fieldname": "seerbit_payment_status",
                "fieldtype": "Select",
                "label": "Payment Status",
                "options": "Not Initiated\nLink Created\nPending\nPaid\nFailed",
                "insert_after": "column_break_seerbit",
                "read_only": 1,
                "default": "Not Initiated"
            },
            {
                "fieldname": "seerbit_reference",
                "fieldtype": "Data",
                "label": "SeerBit Reference",
                "insert_after": "seerbit_payment_status",
                "read_only": 1
            }
        ],
        
        "Sales Order": [
            {
                "fieldname": "seerbit_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payment",
                "insert_after": "payment_schedule",
                "collapsible": 1
            },
            {
                "fieldname": "enable_seerbit_payment",
                "fieldtype": "Check",
                "label": "Enable SeerBit Payment",
                "insert_after": "seerbit_section",
                "default": 0
            },
            {
                "fieldname": "seerbit_payment_request",
                "fieldtype": "Link",
                "label": "SeerBit Payment Request",
                "options": "SeerBit Payment Request",
                "insert_after": "enable_seerbit_payment",
                "read_only": 1
            },
            {
                "fieldname": "advance_payment_amount",
                "fieldtype": "Currency",
                "label": "Advance Payment Amount",
                "insert_after": "seerbit_payment_request"
            }
        ],
        
        "Purchase Invoice": [
            {
                "fieldname": "seerbit_payout_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout",
                "insert_after": "payment_schedule",
                "collapsible": 1
            },
            {
                "fieldname": "enable_seerbit_payout",
                "fieldtype": "Check",
                "label": "Enable SeerBit Payout",
                "insert_after": "seerbit_payout_section",
                "default": 0
            },
            {
                "fieldname": "seerbit_payout_request",
                "fieldtype": "Link",
                "label": "SeerBit Payout Request",
                "options": "SeerBit Payout Request",
                "insert_after": "enable_seerbit_payout",
                "read_only": 1
            },
            {
                "fieldname": "auto_create_payout",
                "fieldtype": "Check",
                "label": "Auto Create Payout Request",
                "insert_after": "seerbit_payout_request",
                "default": 0
            }
        ],
        
        "Payment Entry": [
            {
                "fieldname": "seerbit_details_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Details",
                "insert_after": "reference_no",
                "collapsible": 1
            },
            {
                "fieldname": "is_seerbit_payment",
                "fieldtype": "Check",
                "label": "Is SeerBit Payment",
                "insert_after": "seerbit_details_section",
                "default": 0
            },
            {
                "fieldname": "seerbit_reference_id",
                "fieldtype": "Data",
                "label": "SeerBit Reference ID",
                "insert_after": "is_seerbit_payment",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_transaction_log",
                "fieldtype": "Link",
                "label": "SeerBit Transaction Log",
                "options": "SeerBit Transaction Log",
                "insert_after": "seerbit_reference_id",
                "read_only": 1
            }
        ],
        
        "Supplier": [
            {
                "fieldname": "seerbit_bank_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Bank Details",
                "insert_after": "accounts",
                "collapsible": 1
            },
            {
                "fieldname": "bank_code",
                "fieldtype": "Data",
                "label": "Bank Code",
                "insert_after": "seerbit_bank_section"
            },
            {
                "fieldname": "account_number",
                "fieldtype": "Data",
                "label": "Account Number",
                "insert_after": "bank_code"
            },
            {
                "fieldname": "account_name",
                "fieldtype": "Data",
                "label": "Account Name",
                "insert_after": "account_number"
            },
            {
                "fieldname": "column_break_bank",
                "fieldtype": "Column Break",
                "insert_after": "account_name"
            },
            {
                "fieldname": "bank_name",
                "fieldtype": "Data",
                "label": "Bank Name",
                "insert_after": "column_break_bank",
                "read_only": 1
            },
            {
                "fieldname": "account_verified",
                "fieldtype": "Check",
                "label": "Account Verified",
                "insert_after": "bank_name",
                "default": 0
            }
        ],
        
        "Department": [
            {
                "fieldname": "seerbit_pocket_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Pocket",
                "insert_after": "parent_department",
                "collapsible": 1
            },
            {
                "fieldname": "enable_seerbit_pocket",
                "fieldtype": "Check",
                "label": "Enable SeerBit Pocket",
                "insert_after": "seerbit_pocket_section",
                "default": 0
            },
            {
                "fieldname": "seerbit_pocket",
                "fieldtype": "Link",
                "label": "SeerBit Pocket",
                "options": "SeerBit Pocket",
                "insert_after": "enable_seerbit_pocket",
                "read_only": 1
            },
            {
                "fieldname": "auto_create_pocket",
                "fieldtype": "Check",
                "label": "Auto Create Pocket",
                "insert_after": "seerbit_pocket",
                "default": 0
            }
        ],
        
        "Employee": [
            {
                "fieldname": "seerbit_section_break",
                "fieldtype": "Section Break",
                "label": "SeerBit Payment Configuration",
                "insert_after": "bank_ac_no",
                "collapsible": 1
            },
            {
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Enable SeerBit Payouts",
                "default": 0,
                "insert_after": "seerbit_section_break"
            },
            {
                "fieldname": "seerbit_bank_code",
                "fieldtype": "Data",
                "label": "SeerBit Bank Code",
                "description": "Bank code for SeerBit payouts (e.g. 044 for Access Bank)",
                "insert_after": "seerbit_payout_enabled"
            },
            {
                "fieldname": "seerbit_payout_currency",
                "fieldtype": "Link",
                "label": "Default Payout Currency",
                "options": "Currency",
                "default": "NGN",
                "insert_after": "seerbit_bank_code"
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break",
                "insert_after": "seerbit_payout_currency"
            },
            {
                "fieldname": "seerbit_last_payout_date",
                "fieldtype": "Date",
                "label": "Last SeerBit Payout Date",
                "read_only": 1,
                "insert_after": "seerbit_column_break"
            },
            {
                "fieldname": "seerbit_total_payouts",
                "fieldtype": "Currency",
                "label": "Total SeerBit Payouts",
                "read_only": 1,
                "insert_after": "seerbit_last_payout_date"
            }
        ],
        
        "Salary Slip": [
            {
                "fieldname": "seerbit_payout_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout Information",
                "insert_after": "net_pay",
                "collapsible": 1
            },
            {
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Process via SeerBit",
                "default": 0,
                "insert_after": "seerbit_payout_section"
            },
            {
                "fieldname": "seerbit_payout_reference",
                "fieldtype": "Data",
                "label": "SeerBit Payout Reference",
                "read_only": 1,
                "insert_after": "seerbit_payout_enabled"
            },
            {
                "fieldname": "seerbit_payout_status",
                "fieldtype": "Select",
                "label": "SeerBit Payout Status",
                "options": "Not Initiated\nProcessing\nCompleted\nFailed",
                "default": "Not Initiated",
                "read_only": 1,
                "insert_after": "seerbit_payout_reference"
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break",
                "insert_after": "seerbit_payout_status"
            },
            {
                "fieldname": "seerbit_transaction_id",
                "fieldtype": "Data",
                "label": "SeerBit Transaction ID",
                "read_only": 1,
                "insert_after": "seerbit_column_break"
            },
            {
                "fieldname": "seerbit_payout_date",
                "fieldtype": "Datetime",
                "label": "SeerBit Payout Date",
                "read_only": 1,
                "insert_after": "seerbit_transaction_id"
            }
        ],
        
        "Employee Advance": [
            {
                "fieldname": "seerbit_payout_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout Information",
                "insert_after": "advance_amount",
                "collapsible": 1
            },
            {
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Process via SeerBit",
                "default": 0,
                "insert_after": "seerbit_payout_section"
            },
            {
                "fieldname": "seerbit_payout_reference",
                "fieldtype": "Data",
                "label": "SeerBit Payout Reference",
                "read_only": 1,
                "insert_after": "seerbit_payout_enabled"
            },
            {
                "fieldname": "seerbit_payout_status",
                "fieldtype": "Select",
                "label": "SeerBit Payout Status",
                "options": "Not Initiated\nProcessing\nCompleted\nFailed",
                "default": "Not Initiated",
                "read_only": 1,
                "insert_after": "seerbit_payout_reference"
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break",
                "insert_after": "seerbit_payout_status"
            },
            {
                "fieldname": "seerbit_transaction_id",
                "fieldtype": "Data",
                "label": "SeerBit Transaction ID",
                "read_only": 1,
                "insert_after": "seerbit_column_break"
            },
            {
                "fieldname": "seerbit_payout_date",
                "fieldtype": "Datetime",
                "label": "SeerBit Payout Date",
                "read_only": 1,
                "insert_after": "seerbit_transaction_id"
            }
        ],
        
        "Expense Claim": [
            {
                "fieldname": "seerbit_payout_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout Information",
                "insert_after": "total_claimed_amount",
                "collapsible": 1
            },
            {
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Process via SeerBit",
                "default": 0,
                "insert_after": "seerbit_payout_section"
            },
            {
                "fieldname": "seerbit_payout_reference",
                "fieldtype": "Data",
                "label": "SeerBit Payout Reference",
                "read_only": 1,
                "insert_after": "seerbit_payout_enabled"
            },
            {
                "fieldname": "seerbit_payout_status",
                "fieldtype": "Select",
                "label": "SeerBit Payout Status",
                "options": "Not Initiated\nProcessing\nCompleted\nFailed",
                "default": "Not Initiated",
                "read_only": 1,
                "insert_after": "seerbit_payout_reference"
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break",
                "insert_after": "seerbit_payout_status"
            },
            {
                "fieldname": "seerbit_transaction_id",
                "fieldtype": "Data",
                "label": "SeerBit Transaction ID",
                "read_only": 1,
                "insert_after": "seerbit_column_break"
            },
            {
                "fieldname": "seerbit_payout_date",
                "fieldtype": "Datetime",
                "label": "SeerBit Payout Date",
                "read_only": 1,
                "insert_after": "seerbit_transaction_id"
            }
        ],
        
        "Cost Center": [
            {
                "fieldname": "seerbit_pocket_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Pocket",
                "insert_after": "parent_cost_center",
                "collapsible": 1
            },
            {
                "fieldname": "enable_seerbit_pocket",
                "fieldtype": "Check",
                "label": "Enable SeerBit Pocket",
                "insert_after": "seerbit_pocket_section",
                "default": 0
            },
            {
                "fieldname": "seerbit_pocket",
                "fieldtype": "Link",
                "label": "SeerBit Pocket",
                "options": "SeerBit Pocket",
                "insert_after": "enable_seerbit_pocket",
                "read_only": 1
            }
        ]
    }
    
    create_custom_fields(custom_fields)


def execute():
    """Execute the custom fields creation"""
    try:
        create_seerbit_custom_fields()
        print("✅ SeerBit custom fields created successfully!")
    except Exception as e:
        print(f"❌ Error creating SeerBit custom fields: {str(e)}")
        raise


if __name__ == "__main__":
    execute()
