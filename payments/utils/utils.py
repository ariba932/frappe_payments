from contextlib import contextmanager

import click
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def validate_integration_request(docname: str | None):
	if frappe.db.get_value("Integration Request", docname, "status") == "Cancelled":
		frappe.throw(_("Expired Token"))


def get_payment_gateway_controller(payment_gateway):
	"""Return payment gateway controller"""
	gateway = frappe.get_doc("Payment Gateway", payment_gateway)
	if gateway.gateway_controller is None:
		try:
			return frappe.get_doc(f"{payment_gateway} Settings")
		except Exception:
			frappe.throw(_("{0} Settings not found").format(payment_gateway))
	else:
		try:
			return frappe.get_doc(gateway.gateway_settings, gateway.gateway_controller)
		except Exception:
			frappe.throw(_("{0} Settings not found").format(payment_gateway))


@frappe.whitelist(allow_guest=True, xss_safe=True)
def get_checkout_url(**kwargs):
	try:
		if kwargs.get("payment_gateway"):
			doc = frappe.get_doc("{} Settings".format(kwargs.get("payment_gateway")))
			return doc.get_payment_url(**kwargs)
		else:
			raise Exception
	except Exception:
		frappe.respond_as_web_page(
			_("Something went wrong"),
			_(
				"Looks like something is wrong with this site's payment gateway configuration. No payment has been made."
			),
			indicator_color="red",
			http_status_code=frappe.ValidationError.http_status_code,
		)


def create_payment_gateway(gateway, settings=None, controller=None):
	# NOTE: we don't translate Payment Gateway name because it is an internal doctype
	if not frappe.db.exists("Payment Gateway", gateway):
		payment_gateway = frappe.get_doc(
			{
				"doctype": "Payment Gateway",
				"gateway": gateway,
				"gateway_settings": settings,
				"gateway_controller": controller,
			}
		)
		payment_gateway.insert(ignore_permissions=True)


def make_custom_fields():
	if not frappe.get_meta("Web Form").has_field("payments_tab"):
		click.secho("* Installing Payment Custom Fields in Web Form")

		create_custom_fields(
			{
				"Web Form": [
					{
						"fieldname": "payments_tab",
						"fieldtype": "Tab Break",
						"label": "Payments",
						"insert_after": "custom_css",
					},
					{
						"default": "0",
						"fieldname": "accept_payment",
						"fieldtype": "Check",
						"label": "Accept Payment",
						"insert_after": "payments",
					},
					{
						"depends_on": "accept_payment",
						"fieldname": "payment_gateway",
						"fieldtype": "Link",
						"label": "Payment Gateway",
						"options": "Payment Gateway",
						"insert_after": "accept_payment",
					},
					{
						"default": "Buy Now",
						"depends_on": "accept_payment",
						"fieldname": "payment_button_label",
						"fieldtype": "Data",
						"label": "Button Label",
						"insert_after": "payment_gateway",
					},
					{
						"depends_on": "accept_payment",
						"fieldname": "payment_button_help",
						"fieldtype": "Text",
						"label": "Button Help",
						"insert_after": "payment_button_label",
					},
					{
						"fieldname": "payments_cb",
						"fieldtype": "Column Break",
						"insert_after": "payment_button_help",
					},
					{
						"default": "0",
						"depends_on": "accept_payment",
						"fieldname": "amount_based_on_field",
						"fieldtype": "Check",
						"label": "Amount Based On Field",
						"insert_after": "payments_cb",
					},
					{
						"depends_on": "eval:doc.accept_payment && doc.amount_based_on_field",
						"fieldname": "amount_field",
						"fieldtype": "Select",
						"label": "Amount Field",
						"insert_after": "amount_based_on_field",
					},
					{
						"depends_on": "eval:doc.accept_payment && !doc.amount_based_on_field",
						"fieldname": "amount",
						"fieldtype": "Currency",
						"label": "Amount",
						"insert_after": "amount_field",
					},
					{
						"depends_on": "accept_payment",
						"fieldname": "currency",
						"fieldtype": "Link",
						"label": "Currency",
						"options": "Currency",
						"insert_after": "amount",
					},
				]
			}
		)

		frappe.clear_cache(doctype="Web Form")

	if "erpnext" in frappe.get_installed_apps():
		custom_fields = {
			"GoCardless Mandate": [
				{
					"fieldname": "customer",
					"fieldtype": "Link",
					"in_list_view": 1,
					"label": "Customer",
					"options": "Customer",
					"reqd": 1,
					"insert_after": "disabled",
				}
			]
		}

		create_custom_fields(custom_fields)


def delete_custom_fields():
	if frappe.get_meta("Web Form").has_field("payments_tab"):
		click.secho("* Uninstalling Payment Custom Fields from Web Form")

		fieldnames = (
			"payments_tab",
			"accept_payment",
			"payment_gateway",
			"payment_button_label",
			"payment_button_help",
			"payments_cb",
			"amount_field",
			"amount_based_on_field",
			"amount",
			"currency",
		)

		for fieldname in fieldnames:
			frappe.db.delete("Custom Field", {"name": "Web Form-" + fieldname})

		frappe.clear_cache(doctype="Web Form")


def before_install():
	# TODO: remove this
	# This is done for erpnext CI patch test
	#
	# Since we follow a flow like install v14 -> restore v10 site
	# -> migrate to v12, v13 and then v14 again
	#
	# This app fails installing when the site is restored to v10 as
	# a lot of apis don;t exist in v10 and this is a (at the moment) required app for erpnext.
	if not frappe.get_meta("Module Def").has_field("custom"):
		return False


@contextmanager
def erpnext_app_import_guard():
	marketplace_link = '<a href="https://frappecloud.com/marketplace/apps/erpnext">Marketplace</a>'
	github_link = '<a href="https://github.com/frappe/erpnext">GitHub</a>'
	msg = _("erpnext app is not installed. Please install it from {} or {}").format(
		marketplace_link, github_link
	)
	try:
		yield
	except ImportError:
		frappe.throw(msg, title=_("Missing ERPNext App"))


## --- Custom fields to drive Seerbit Payout integrations with Employee, Supplier, etc 
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


def delete_seerbit_custom_fields():
	"""Delete all SeerBit-related custom fields when uninstalling"""
	click.secho("* Uninstalling SeerBit Custom Fields")
	
	# Define all SeerBit custom fields to be removed
	seerbit_custom_fields = {
		"Bank": [
			"seerbit_bank_code",
			"payment_gateway_source"
		],
		"Bank Account": [
			"seerbit_enabled",
			"seerbit_bank_code"
		],
		"Employee": [
			"seerbit_payout_enabled",
			"seerbit_bank_code"
		],
		"Supplier": [
			"seerbit_payout_enabled",
			"seerbit_bank_code"
		],
		"Salary Slip": [
			"seerbit_payout_reference",
			"seerbit_payout_status"
		]
	}
	
	# Delete custom fields
	for doctype, fieldnames in seerbit_custom_fields.items():
		for fieldname in fieldnames:
			custom_field_name = f"{doctype}-{fieldname}"
			if frappe.db.exists("Custom Field", custom_field_name):
				try:
					frappe.db.delete("Custom Field", {"name": custom_field_name})
					click.secho(f"  - Deleted custom field: {custom_field_name}")
				except Exception as e:
					click.secho(f"  - Error deleting {custom_field_name}: {str(e)}", fg="red")
		
		# Clear cache for each doctype
		frappe.clear_cache(doctype=doctype)
	
	# Delete SeerBit Bank Code records if they exist
	if frappe.db.exists("DocType", "SeerBit Bank Code"):
		try:
			# Delete all SeerBit Bank Code records
			frappe.db.sql("DELETE FROM `tabSeerBit Bank Code`")
			click.secho("  - Deleted all SeerBit Bank Code records")
		except Exception as e:
			click.secho(f"  - Error deleting SeerBit Bank Code records: {str(e)}", fg="red")
	
	# Delete SeerBit Payout records if they exist
	if frappe.db.exists("DocType", "SeerBit Payout"):
		try:
			# Delete all SeerBit Payout records
			frappe.db.sql("DELETE FROM `tabSeerBit Payout`")
			click.secho("  - Deleted all SeerBit Payout records")
		except Exception as e:
			click.secho(f"  - Error deleting SeerBit Payout records: {str(e)}", fg="red")
	
	# Delete SeerBit Order records if they exist
	if frappe.db.exists("DocType", "SeerBit Order"):
		try:
			# Delete all SeerBit Order records
			frappe.db.sql("DELETE FROM `tabSeerBit Order`")
			click.secho("  - Deleted all SeerBit Order records")
		except Exception as e:
			click.secho(f"  - Error deleting SeerBit Order records: {str(e)}", fg="red")
	
	# Remove property setters for Bank doctype
	try:
		frappe.db.delete("Property Setter", {
			"doc_type": "Bank",
			"property": "allow_rename",
			"property_type": "Int"
		})
		click.secho("  - Removed Bank property setter")
	except Exception as e:
		click.secho(f"  - Error removing Bank property setter: {str(e)}", fg="red")
	
	# Commit changes
	frappe.db.commit()
	click.secho("* SeerBit Custom Fields uninstallation completed", fg="green")


def cleanup_seerbit_bank_records():
	"""Clean up ERPNext Bank records created by SeerBit"""
	try:
		# Find all Bank records with SeerBit as source
		banks_with_seerbit = frappe.get_all("Bank", 
			filters={"payment_gateway_source": "SeerBit"},
			fields=["name", "bank_name", "seerbit_bank_code"]
		)
		
		for bank in banks_with_seerbit:
			try:
				# Check if this bank has any linked accounts or transactions
				linked_accounts = frappe.get_all("Bank Account", 
					filters={"bank": bank["name"]},
					fields=["name"]
				)
				
				if not linked_accounts:
					# Safe to delete if no linked accounts
					frappe.delete_doc("Bank", bank["name"], ignore_permissions=True)
					click.secho(f"  - Deleted Bank: {bank['bank_name']}")
				else:
					# Just clear SeerBit fields if there are linked accounts
					bank_doc = frappe.get_doc("Bank", bank["name"])
					bank_doc.seerbit_bank_code = ""
					bank_doc.payment_gateway_source = ""
					bank_doc.save(ignore_permissions=True)
					click.secho(f"  - Cleared SeerBit fields from Bank: {bank['bank_name']}")
			except Exception as e:
				click.secho(f"  - Error processing Bank {bank['bank_name']}: {str(e)}", fg="red")
	
	except Exception as e:
		click.secho(f"  - Error cleaning up SeerBit bank records: {str(e)}", fg="red")

def create_sales_invoice_seerbit_fields():
    """Create SeerBit custom fields for Sales Invoice"""
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "seerbit_payment_section",
                "fieldtype": "Section Break",
                "label": "SeerBit Payment Details"
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
    
    create_custom_fields(custom_fields)

def create_payment_entry_seerbit_fields():
    """Create SeerBit custom fields for Payment Entry"""
    custom_fields = {
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
            }
        ]
    }
    
    create_custom_fields(custom_fields)
