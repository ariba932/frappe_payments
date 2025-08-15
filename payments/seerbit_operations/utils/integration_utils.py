# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, now


@frappe.whitelist()
def create_payment_request_from_sales_invoice(sales_invoice):
    """Create SeerBit payment request from Sales Invoice"""
    
    invoice = frappe.get_doc("Sales Invoice", sales_invoice)
    
    # Check if payment request already exists
    existing_request = frappe.db.exists("SeerBit Payment Request", {
        "reference_doctype": "Sales Invoice",
        "reference_name": sales_invoice,
        "status": ["not in", ["Cancelled", "Failed"]]
    })
    
    if existing_request:
        return {"status": "error", "message": f"Payment request already exists: {existing_request}"}
    
    try:
        # Create payment request
        payment_request = frappe.get_doc({
            "doctype": "SeerBit Payment Request",
            "reference_doctype": "Sales Invoice",
            "reference_name": sales_invoice,
            "payment_type": "One-time",
            "customer": invoice.customer,
            "customer_name": invoice.customer_name,
            "customer_email": invoice.contact_email or frappe.get_value("Customer", invoice.customer, "email_id"),
            "customer_phone": invoice.contact_mobile or frappe.get_value("Customer", invoice.customer, "mobile_no"),
            "amount": invoice.outstanding_amount,
            "currency": invoice.currency,
            "description": f"Payment for Sales Invoice {sales_invoice}"
        })
        
        payment_request.insert()
        
        # Update invoice with payment request link
        invoice.db_set("seerbit_payment_request", payment_request.name)
        invoice.db_set("enable_seerbit_payment", 1)
        invoice.db_set("seerbit_payment_status", "Link Created")
        
        return {
            "status": "success",
            "payment_request": payment_request.name,
            "message": f"Payment request created: {payment_request.name}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating payment request: {str(e)}", "SeerBit Integration")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def create_payout_request_from_purchase_invoice(purchase_invoice):
    """Create SeerBit payout request from Purchase Invoice"""
    
    invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
    supplier = frappe.get_doc("Supplier", invoice.supplier)
    
    try:
        # Create payout request
        payout_request = frappe.get_doc({
            "doctype": "SeerBit Payout Request",
            "payout_type": "Supplier Payment",
            "reference_doctype": "Purchase Invoice",
            "reference_name": purchase_invoice,
            "beneficiary_type": "Supplier",
            "beneficiary_name": supplier.supplier_name,
            "beneficiary_email": supplier.email_id,
            "beneficiary_phone": supplier.mobile_no,
            "bank_code": supplier.bank_code,
            "account_number": supplier.account_number,
            "account_name": supplier.account_name,
            "amount": invoice.outstanding_amount,
            "currency": invoice.currency,
            "description": f"Payment for Purchase Invoice {purchase_invoice}",
            "requires_approval": 1
        })
        
        payout_request.insert()
        
        # Update invoice with payout request link
        invoice.db_set("seerbit_payout_request", payout_request.name)
        invoice.db_set("enable_seerbit_payout", 1)
        
        return {
            "status": "success",
            "payout_request": payout_request.name,
            "message": f"Payout request created: {payout_request.name}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating payout request: {str(e)}", "SeerBit Integration")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def create_department_pocket(department):
    """Create SeerBit pocket for department"""
    
    dept_doc = frappe.get_doc("Department", department)
    
    if not dept_doc.enable_seerbit_pocket:
        return {"status": "error", "message": "SeerBit pocket not enabled for this department"}
    
    # Check if pocket already exists
    existing_pocket = frappe.db.exists("SeerBit Pocket", {
        "linked_department": department,
        "status": "Active"
    })
    
    if existing_pocket:
        return {"status": "error", "message": f"Active pocket already exists: {existing_pocket}"}
    
    try:
        pocket_name = f"DEPT_{dept_doc.name}"
        
        # Create pocket
        pocket_doc = frappe.get_doc({
            "doctype": "SeerBit Pocket",
            "pocket_name": pocket_name,
            "pocket_type": "Department Pocket",
            "linked_department": department,
            "linked_company": dept_doc.company,
            "description": f"Department pocket for {dept_doc.department_name}",
            "currency": "NGN"
        })
        
        pocket_doc.insert()
        
        # Update department with pocket link
        dept_doc.db_set("seerbit_pocket", pocket_doc.name)
        
        return {
            "status": "success",
            "pocket": pocket_doc.name,
            "message": f"Department pocket created: {pocket_doc.name}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating department pocket: {str(e)}", "SeerBit Integration")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def verify_supplier_bank_account(supplier):
    """Verify supplier bank account with SeerBit"""
    
    supplier_doc = frappe.get_doc("Supplier", supplier)
    
    if not supplier_doc.bank_code or not supplier_doc.account_number:
        return {"status": "error", "message": "Bank code and account number are required"}
    
    try:
        from payments.seerbit_integration.core.api_client import SeerBitAPIClient
        
        client = SeerBitAPIClient()
        verification_data = {
            "accountNumber": supplier_doc.account_number,
            "bankCode": supplier_doc.bank_code
        }
        
        response = client.verify_account_number(verification_data)
        
        if response.get("status") == "SUCCESS":
            account_info = response.get("data", {})
            
            # Update supplier details
            supplier_doc.db_set("account_name", account_info.get("accountName"))
            supplier_doc.db_set("bank_name", account_info.get("bankName"))
            supplier_doc.db_set("account_verified", 1)
            
            return {
                "status": "success",
                "account_name": account_info.get("accountName"),
                "bank_name": account_info.get("bankName"),
                "message": "Account verified successfully"
            }
        else:
            return {"status": "error", "message": response.get("message", "Verification failed")}
            
    except Exception as e:
        frappe.log_error(f"Error verifying account: {str(e)}", "SeerBit Integration")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_seerbit_dashboard_data():
    """Get dashboard data for SeerBit operations"""
    
    try:
        # Payment Collections
        payment_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_requests,
                SUM(CASE WHEN status = 'Paid' THEN 1 ELSE 0 END) as successful_payments,
                SUM(CASE WHEN status = 'Paid' THEN amount ELSE 0 END) as total_collections,
                SUM(CASE WHEN DATE(request_date) = CURDATE() THEN 1 ELSE 0 END) as today_requests
            FROM `tabSeerBit Payment Request`
            WHERE status != 'Cancelled'
        """, as_dict=1)[0]
        
        # Payout Stats
        payout_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_payouts,
                SUM(CASE WHEN status = 'Pending Approval' THEN 1 ELSE 0 END) as pending_approvals,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_payouts,
                SUM(CASE WHEN status = 'Completed' THEN amount ELSE 0 END) as total_payouts_amount
            FROM `tabSeerBit Payout Request`
            WHERE status != 'Cancelled'
        """, as_dict=1)[0]
        
        # Pocket Stats
        pocket_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_pockets,
                SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_pockets,
                SUM(CASE WHEN status = 'Active' THEN current_balance ELSE 0 END) as total_balance
            FROM `tabSeerBit Pocket`
        """, as_dict=1)[0]
        
        # Recent Transactions
        recent_transactions = frappe.db.sql("""
            SELECT 
                name, transaction_type, amount, status, timestamp
            FROM `tabSeerBit Transaction Log`
            ORDER BY timestamp DESC
            LIMIT 10
        """, as_dict=1)
        
        return {
            "status": "success",
            "data": {
                "payments": payment_stats,
                "payouts": payout_stats,
                "pockets": pocket_stats,
                "recent_transactions": recent_transactions
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting dashboard data: {str(e)}", "SeerBit Dashboard")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def sync_all_pocket_balances():
    """Sync all active pocket balances"""
    
    try:
        active_pockets = frappe.get_all("SeerBit Pocket", 
            filters={"status": "Active", "auto_sync_enabled": 1},
            fields=["name"]
        )
        
        synced_count = 0
        for pocket in active_pockets:
            try:
                pocket_doc = frappe.get_doc("SeerBit Pocket", pocket.name)
                pocket_doc.sync_balance()
                synced_count += 1
            except Exception as e:
                frappe.log_error(f"Error syncing pocket {pocket.name}: {str(e)}", "SeerBit Pocket Sync")
        
        return {
            "status": "success",
            "synced_count": synced_count,
            "total_pockets": len(active_pockets),
            "message": f"Synced {synced_count} out of {len(active_pockets)} pockets"
        }
        
    except Exception as e:
        frappe.log_error(f"Error syncing pockets: {str(e)}", "SeerBit Pocket Sync")
        return {"status": "error", "message": str(e)}


def auto_create_payment_requests(doc=None, method=None):
    """Auto create payment requests for eligible invoices or specific document"""
    
    if doc and doc.doctype == "Sales Invoice":
        # Create payment request for specific invoice
        try:
            if doc.enable_seerbit_payment and doc.outstanding_amount > 0:
                result = create_payment_request_from_sales_invoice(doc.name)
                if result.get("status") == "success":
                    frappe.msgprint(f"SeerBit payment request created: {result.get('payment_request')}")
        except Exception as e:
            frappe.log_error(f"Error creating payment request for {doc.name}: {str(e)}", "SeerBit Integration")
    else:
        # Bulk create for all eligible invoices (scheduled task)
        # Get invoices with SeerBit enabled but no payment request
        invoices = frappe.db.sql("""
            SELECT name, outstanding_amount
            FROM `tabSales Invoice`
            WHERE docstatus = 1
            AND enable_seerbit_payment = 1
            AND (seerbit_payment_request IS NULL OR seerbit_payment_request = '')
            AND outstanding_amount > 0
            AND DATEDIFF(CURDATE(), posting_date) <= 30
        """, as_dict=1)
        
        created_count = 0
        for invoice in invoices:
            try:
                result = create_payment_request_from_sales_invoice(invoice.name)
                if result.get("status") == "success":
                    created_count += 1
            except Exception as e:
                frappe.log_error(f"Auto payment request creation error for {invoice.name}: {str(e)}", "SeerBit Auto Creation")
        
        if created_count > 0:
            frappe.log_error(f"Auto created {created_count} payment requests", "SeerBit Auto Creation")


def auto_verify_pending_payments():
    """Auto verify pending payment requests"""
    
    # Get pending payment requests
    pending_payments = frappe.get_all("SeerBit Payment Request",
        filters={
            "status": "Active",
            "seerbit_payment_reference": ["!=", ""]
        },
        fields=["name"]
    )
    
    verified_count = 0
    for payment in pending_payments:
        try:
            payment_doc = frappe.get_doc("SeerBit Payment Request", payment.name)
            payment_doc.verify_payment()
            verified_count += 1
        except Exception as e:
            frappe.log_error(f"Auto verification error for {payment.name}: {str(e)}", "SeerBit Auto Verification")
    
def auto_verify_pending_payments():
    """Auto verify pending payment requests"""
    
    # Get pending payment requests
    pending_payments = frappe.get_all("SeerBit Payment Request",
        filters={
            "status": "Active",
            "seerbit_payment_reference": ["!=", ""]
        },
        fields=["name"]
    )
    
    verified_count = 0
    for payment in pending_payments:
        try:
            payment_doc = frappe.get_doc("SeerBit Payment Request", payment.name)
            payment_doc.verify_payment()
            verified_count += 1
        except Exception as e:
            frappe.log_error(f"Auto verification error for {payment.name}: {str(e)}", "SeerBit Auto Verification")
    
    return verified_count


def auto_create_payout_requests(doc, method):
    """Auto create payout requests for Purchase Invoices"""
    
    if not doc.enable_seerbit_payout:
        return
    
    if doc.outstanding_amount <= 0:
        return
    
    try:
        result = create_payout_request_from_purchase_invoice(doc.name)
        if result.get("status") == "success":
            frappe.msgprint(f"SeerBit payout request created: {result.get('payout_request')}")
    except Exception as e:
        frappe.log_error(f"Error creating payout request for {doc.name}: {str(e)}", "SeerBit Integration")


def auto_create_department_pocket(doc, method):
    """Auto create pocket for department if enabled"""
    
    if not doc.enable_seerbit_pocket:
        return
    
    if not doc.auto_create_pocket:
        return
    
    try:
        result = create_department_pocket(doc.name)
        if result.get("status") == "success":
            frappe.msgprint(f"SeerBit department pocket created: {result.get('pocket')}")
    except Exception as e:
        frappe.log_error(f"Error creating department pocket for {doc.name}: {str(e)}", "SeerBit Integration")


def validate_supplier_bank_details(doc, method):
    """Validate supplier bank details for SeerBit payout eligibility"""
    
    if not doc.seerbit_payout_enabled:
        return
    
    if not doc.default_bank_account:
        frappe.msgprint("Default bank account is required for SeerBit payouts", alert=True)
        return
    
    if not doc.seerbit_bank_code:
        frappe.msgprint("SeerBit bank code is required for payouts", alert=True)
        return
    
    # Auto-verify account if both bank account and code are set
    if doc.default_bank_account and doc.seerbit_bank_code and not doc.account_verification_status:
        try:
            result = verify_supplier_bank_account(doc.name)
            if result.get("status") == "success":
                doc.account_verification_status = "Verified"
                doc.account_verification_date = now()
        except Exception as e:
            frappe.log_error(f"Error verifying supplier account for {doc.name}: {str(e)}", "SeerBit Validation")
