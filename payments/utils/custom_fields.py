import frappe
from frappe import _

def create_custom_fields():
    """Create custom fields for SeerBit integration"""
    
    # Bank custom fields
    frappe.make_property_setter("Bank", None, "allow_rename", 0, "Int")
    
    custom_fields = {
        "Bank": [
            {
                "fieldname": "seerbit_bank_code",
                "fieldtype": "Data",
                "label": "SeerBit Bank Code",
                "insert_after": "bank_name"
            },
            {
                "fieldname": "payment_gateway_source",
                "fieldtype": "Data",
                "label": "Payment Gateway Source",
                "insert_after": "seerbit_bank_code",
                "read_only": 1
            }
        ],
        "Bank Account": [
            {
                "fieldname": "seerbit_enabled",
                "fieldtype": "Check",
                "label": "Enable SeerBit Payouts",
                "insert_after": "is_default",
                "default": 0
            },
            {
                "fieldname": "seerbit_bank_code",
                "fieldtype": "Link",
                "label": "SeerBit Bank Code",
                "options": "SeerBit Bank Code",
                "insert_after": "seerbit_enabled",
                "depends_on": "seerbit_enabled"
            }
        ],
        "Employee": [
            {
                "fieldname": "seerbit_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout Settings",
                "insert_after": "bank_ac_no"
            },
            {
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Enable SeerBit Salary Payout",
                "default": 0
            },
            {
                "fieldname": "seerbit_bank_code",
                "fieldtype": "Link",
                "label": "SeerBit Bank Code",
                "options": "SeerBit Bank Code",
                "depends_on": "seerbit_payout_enabled"
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "account_verification_status",
                "fieldtype": "Select",
                "label": "Account Verification Status",
                "options": "Not Verified\nVerified\nFailed",
                "default": "Not Verified",
                "read_only": 1
            },
            {
                "fieldname": "verified_account_name",
                "fieldtype": "Data",
                "label": "Verified Account Name",
                "read_only": 1
            }
        ],
        "Supplier": [
            {
                "fieldname": "seerbit_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout Settings",
                "insert_after": "default_bank_account"
            },
            {
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Enable SeerBit Payouts",
                "default": 0
            },
            {
                "fieldname": "seerbit_bank_code",
                "fieldtype": "Link",
                "label": "SeerBit Bank Code",
                "options": "SeerBit Bank Code",
                "depends_on": "seerbit_payout_enabled"
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "account_verification_status",
                "fieldtype": "Select",
                "label": "Account Verification Status",
                "options": "Not Verified\nVerified\nFailed",
                "default": "Not Verified",
                "read_only": 1
            },
            {
                "fieldname": "verified_account_name",
                "fieldtype": "Data",
                "label": "Verified Account Name",
                "read_only": 1
            }
        ],
        "Salary Slip": [
            {
                "fieldname": "seerbit_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout Details",
                "depends_on": "eval:doc.net_pay > 0"
            },
            {
                "fieldname": "seerbit_payout_reference",
                "fieldtype": "Data",
                "label": "SeerBit Payout Reference",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_payout_status",
                "fieldtype": "Select",
                "label": "SeerBit Payout Status",
                "options": "Not Initiated\nPending\nProcessing\nPaid\nFailed",
                "default": "Not Initiated",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "seerbit_payout_method",
                "fieldtype": "Select",
                "label": "Payout Method",
                "options": "Enhanced\nLegacy",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_linking_reference",
                "fieldtype": "Data",
                "label": "SeerBit Linking Reference",
                "read_only": 1
            }
        ],
        "Payment Entry": [
            {
                "fieldname": "seerbit_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payout Details",
                "depends_on": "eval:doc.payment_type=='Pay'"
            },
            {
                "fieldname": "seerbit_payout_reference",
                "fieldtype": "Data",
                "label": "SeerBit Payout Reference",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_payout_status",
                "fieldtype": "Select",
                "label": "SeerBit Payout Status",
                "options": "Not Initiated\nPending\nProcessing\nPaid\nFailed\nCancelled",
                "default": "Not Initiated",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_column_break",
                "fieldtype": "Column Break"
            },
            {
                "fieldname": "seerbit_payout_method",
                "fieldtype": "Select",
                "label": "Payout Method",
                "options": "Enhanced\nLegacy",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_payout_date",
                "fieldtype": "Datetime",
                "label": "SeerBit Payout Date",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_payout_fee",
                "fieldtype": "Currency",
                "label": "SeerBit Payout Fee",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_linking_reference",
                "fieldtype": "Data",
                "label": "SeerBit Linking Reference",
                "read_only": 1
            }
        ],
        "Sales Invoice": [
            {
                "fieldname": "seerbit_payment_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payment Details",
                "depends_on": "eval:doc.outstanding_amount > 0"
            },
            {
                "fieldname": "seerbit_payment_link",
                "fieldtype": "Data",
                "label": "SeerBit Payment Link",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_payment_reference",
                "fieldtype": "Data",
                "label": "SeerBit Payment Reference",
                "read_only": 1
            },
            {
                "fieldname": "seerbit_payment_status",
                "fieldtype": "Select",
                "label": "SeerBit Payment Status",
                "options": "Not Initiated\nPending\nPaid\nFailed\nPartially Paid",
                "default": "Not Initiated",
                "read_only": 1
            }
        ]
    }
    
    for doctype, fields in custom_fields.items():
        for field in fields:
            create_custom_field(doctype, field)

def create_custom_field(doctype, field_dict):
    """Create custom field if it doesn't exist"""
    field_name = field_dict["fieldname"]
    if not frappe.db.exists("Custom Field", f"{doctype}-{field_name}"):
        field_dict["dt"] = doctype
        field_dict["doctype"] = "Custom Field"
        doc = frappe.get_doc(field_dict)
        doc.insert(ignore_permissions=True)

def delete_custom_fields():
    """Delete SeerBit custom fields during uninstall"""
    custom_fields_to_delete = [
        "Bank-seerbit_bank_code",
        "Bank-payment_gateway_source",
        "Bank Account-seerbit_enabled",
        "Bank Account-seerbit_bank_code",
        "Employee-seerbit_section",
        "Employee-seerbit_payout_enabled",
        "Employee-seerbit_bank_code",
        "Employee-seerbit_column_break",
        "Employee-account_verification_status",
        "Employee-verified_account_name",
        "Supplier-seerbit_section",
        "Supplier-seerbit_payout_enabled",
        "Supplier-seerbit_bank_code",
        "Supplier-seerbit_column_break",
        "Supplier-account_verification_status",
        "Supplier-verified_account_name",
        "Salary Slip-seerbit_section",
        "Salary Slip-seerbit_payout_reference",
        "Salary Slip-seerbit_payout_status",
        "Salary Slip-seerbit_column_break",
        "Salary Slip-seerbit_payout_method",
        "Salary Slip-seerbit_linking_reference",
        "Payment Entry-seerbit_section",
        "Payment Entry-seerbit_payout_reference",
        "Payment Entry-seerbit_payout_status",
        "Payment Entry-seerbit_column_break",
        "Payment Entry-seerbit_payout_method",
        "Payment Entry-seerbit_payout_date",
        "Payment Entry-seerbit_payout_fee",
        "Payment Entry-seerbit_linking_reference",
        "Sales Invoice-seerbit_payment_section",
        "Sales Invoice-seerbit_payment_link",
        "Sales Invoice-seerbit_payment_reference",
        "Sales Invoice-seerbit_payment_status"
    ]
    
    for field_name in custom_fields_to_delete:
        if frappe.db.exists("Custom Field", field_name):
            frappe.delete_doc("Custom Field", field_name, ignore_permissions=True)
