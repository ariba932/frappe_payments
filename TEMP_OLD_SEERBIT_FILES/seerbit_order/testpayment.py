# Example: Create payment from Python code
import frappe
# Example: Create a SeerBit order from Python code

payment_result = frappe.call(
    "payments.payment_gateways.seerbit_api.create_seerbit_order",
    amount=1000,
    currency="NGN",
    email="customer@example.com",
    full_name="John Doe",
    callback_url="/payment-callback"
)

redirect_url = payment_result["redirect_url"]
