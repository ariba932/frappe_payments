from . import __version__ as app_version

app_name = "payments"
app_title = "Payments"
app_publisher = "Frappe Technologies"
app_description = "Payments app for frappe"
app_email = "hello@frappe.io"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/pay/css/pay.css"
# app_include_js = "/assets/pay/js/pay.js"

# include js, css files in header of web template
# web_include_css = "/assets/pay/css/pay.css"
# web_include_js = "/assets/pay/js/pay.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "pay/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Sales Invoice": "public/js/sales_invoice.js",
    "Purchase Invoice": "public/js/purchase_invoice.js",
    "Department": "public/js/department.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "pay.utils.jinja_methods",
# 	"filters": "pay.utils.jinja_filters"
# }

# Installation
# ------------

before_install = "payments.utils.before_install"
after_install = [
    "payments.utils.make_custom_fields",
    "payments.utils.create_custom_fields", 
    "payments.utils.create_payment_entry_seerbit_fields",
    "payments.utils.create_sales_invoice_seerbit_fields",
    "payments.seerbit_operations.custom_fields.create_fields.create_seerbit_custom_fields"
]

# Uninstallation
# ------------

before_uninstall = [
    "payments.utils.delete_custom_fields",
    "payments.utils.utils.delete_seerbit_custom_fields",
    "payments.utils.utils.cleanup_seerbit_bank_records"
]
after_uninstall = "payments.utils.delete_seerbit_custom_fields"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "pay.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {"Web Form": "payments.overrides.payment_webform.PaymentWebForm"}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }
doc_events = {
    "Sales Invoice": {
        "on_submit": "payments.seerbit_operations.utils.integration_utils.auto_create_payment_requests",
        "on_payment_complete": "payments.seerbit_integration.selling.invoice_payments.on_payment_complete"
    },
    "Purchase Invoice": {
        "on_submit": "payments.seerbit_operations.utils.integration_utils.auto_create_payout_requests"
    },
    "Department": {
        "after_insert": "payments.seerbit_operations.utils.integration_utils.auto_create_department_pocket"
    },
    "Supplier": {
        "validate": "payments.seerbit_operations.utils.integration_utils.validate_supplier_bank_details"
    }
    # Note: SeerBit Order doctype is commented out until it's properly implemented
    # "SeerBit Order": {
    #     "on_payment_captured": "payments.seerbit_operations.doctype.seerbit_settings.seerbit_settings.on_payment_captured",
    #     "on_payment_failed": "payments.seerbit_operations.doctype.seerbit_settings.seerbit_settings.on_payment_failed"
    # }
}


# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"payments.payment_gateways.doctype.razorpay_settings.razorpay_settings.capture_payment",
	],
    "hourly": [
        "payments.seerbit_integration.utils.dashboard.auto_verify_pending_payments",
        "payments.seerbit_integration.utils.dashboard.auto_verify_pending_payouts",
        "payments.seerbit_operations.utils.integration_utils.auto_verify_pending_payments",
        "payments.seerbit_operations.utils.integration_utils.sync_all_pocket_balances"
    ],
    "daily": [
        "payments.seerbit_integration.utils.bank_management.sync_bank_codes_from_seerbit",
        "payments.seerbit_operations.utils.integration_utils.auto_create_payment_requests"
    ]
}

# Testing
# -------

before_tests = "erpnext.setup.utils.before_tests"  # To setup company and accounts

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.website.doctype.web_form.web_form.accept": "payments.overrides.payment_webform.accept"
}

# Webhook endpoints for SeerBit notifications (Updated for modular structure)
website_route_rules = [
    {"from_route": "/seerbit_payment_success", "to_route": "payment_success"},
    {"from_route": "/seerbit_payment_failed", "to_route": "payment_failed"},
    {"from_route": "/seerbit_payment_error", "to_route": "payment_error"},
    {"from_route": "/api/method/seerbit_webhook", "to_route": "payments.seerbit_integration.core.webhooks.webhook_handler"},
    {"from_route": "/api/method/seerbit_payment_callback", "to_route": "payments.seerbit_integration.core.webhooks.payment_callback"},
]

# Fixtures for installation
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["name", "in", [
                "Web Form-seerbit_payment_gateway",
                "Payment Gateway-seerbit_supported"
            ]]
        ]
    }
]