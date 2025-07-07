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
# doctype_js = {"doctype" : "public/js/doctype.js"}
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
after_install = ["payments.utils.make_custom_fields","payments.utils.create_custom_fields" ]

# Uninstallation
# ------------

before_uninstall = "payments.utils.delete_custom_fields"
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
# Add SeerBit specific hooks
doc_events = {
    # ... existing doc_events ...
    
    "SeerBit Order": {
        "on_payment_captured": "payments.payment_gateways.doctype.seerbit_settings.seerbit_gateway.on_payment_captured",
        "on_payment_failed": "payments.payment_gateways.doctype.seerbit_settings.seerbit_gateway.on_payment_failed"
    }
}


# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"payments.payment_gateways.doctype.razorpay_settings.razorpay_settings.capture_payment",
	],
    "hourly": [
        "payments.payment_gateways.doctype.seerbit_settings.tasks.verify_pending_payments",
        "payments.payment_gateways.doctype.seerbit_settings.tasks.verify_pending_payouts"
    ],
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

# Webhook endpoints for Seerbit notifications
website_route_rules = [
    {"from_route": "/seerbit_payment_success", "to_route": "payment_success"},
    {"from_route": "/seerbit_payment_failed", "to_route": "payment_failed"},
    {"from_route": "/seerbit_payment_error", "to_route": "payment_error"},
    {"from_route": "/api/method/seerbit_payout_webhook", "to_route": "payments.payment_gateways.doctype.seerbit_payout.seerbit_payout.seerbit_payout_webhook"},
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