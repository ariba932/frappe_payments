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
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Enable SeerBit Salary Payout",
                "insert_after": "bank_ac_no",
                "default": 0
            },
            {
                "fieldname": "seerbit_bank_code",
                "fieldtype": "Link",
                "label": "SeerBit Bank Code",
                "options": "SeerBit Bank Code",
                "insert_after": "seerbit_payout_enabled",
                                "depends_on": "seerbit_payout_enabled"
            }
        ],
        "Supplier": [
            {
                "fieldname": "seerbit_payout_enabled",
                "fieldtype": "Check",
                "label": "Enable SeerBit Payouts",
                "insert_after": "default_bank_account",
                "default": 0
            },
            {
                "fieldname": "seerbit_bank_code",
                "fieldtype": "Link",
                "label": "SeerBit Bank Code",
                "options": "SeerBit Bank Code",
                "insert_after": "seerbit_payout_enabled",
                "depends_on": "seerbit_payout_enabled"
            }
        ],
        "Salary Slip": [
            {
                "fieldname": "seerbit_payout_reference",
                "fieldtype": "Data",
                "label": "SeerBit Payout Reference",
                "insert_after": "net_pay",
                "read_only": 1
            },
                        {
                "fieldname": "seerbit_payout_status",
                "fieldtype": "Select",
                "label": "SeerBit Payout Status",
                "options": "Not Initiated\nPending\nProcessing\nPaid\nFailed",
                "insert_after": "seerbit_payout_reference",
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
        