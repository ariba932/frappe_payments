# -*- coding: utf-8 -*-
"""
SeerBit Buying Operations - Supplier Payment and Payout Processing
Handles all payout operations for suppliers, purchase invoices, and general payouts
"""

import frappe
from frappe import _
from frappe.utils import nowdate, flt
from ..core.api_client import get_api_client
from ..utils.account_verification import verify_beneficiary_account


class SeerBitBuyingOperations:
    """Handles all buying/payout operations"""
    
    def __init__(self):
        from ..core.api_client import get_seerbit_settings
        self.settings = get_seerbit_settings()
        self.api_client = get_api_client(self.settings)
        
        if not self.settings.is_enabled:
            frappe.throw(_("SeerBit is not enabled"))
        
        if not self.settings.enable_payouts:
            frappe.throw(_("SeerBit payouts are not enabled"))
    
    def initiate_supplier_payment(self, purchase_invoice_name, verify_account=True):
        """Initiate payment to supplier for purchase invoice"""
        purchase_invoice = frappe.get_doc("Purchase Invoice", purchase_invoice_name)
        supplier = frappe.get_doc("Supplier", purchase_invoice.supplier)
        
        # Validate supplier setup
        self._validate_supplier_payout_setup(supplier)
        
        # Get bank account details
        bank_account = frappe.get_doc("Bank Account", supplier.default_bank_account)
        
        if verify_account:
            # Verify account before proceeding
            verification_result = verify_beneficiary_account(
                bank_account.bank_account_no,
                supplier.seerbit_bank_code,
                supplier.supplier_name
            )
            
            if not verification_result.get("verified"):
                frappe.throw(_("Supplier account verification failed: {0}").format(
                    verification_result.get("message", "Unknown error")
                ))
        
        # Generate payout reference
        payout_reference = f"PI-{purchase_invoice.name}-{frappe.generate_hash(length=8)}"
        
        # Prepare payout data
        payout_data = {
            "reference": payout_reference,
            "amount": purchase_invoice.outstanding_amount,
            "currency": purchase_invoice.currency,
            "bank_account": bank_account.bank_account_no,
            "bank_code": supplier.seerbit_bank_code,
            "beneficiary_name": supplier.supplier_name,
            "beneficiary_email": supplier.email_id or "",
            "narration": f"Payment for Purchase Invoice {purchase_invoice.name}",
            "beneficiary_mobile": supplier.mobile_no or ""
        }
        
        try:
            # Use enhanced payout if available
            if self.settings.get("use_enhanced_payouts", 0):
                result = self._initiate_enhanced_payout(payout_data)
            else:
                result = self.api_client.initiate_payout(**payout_data)
            
            # Create SeerBit Payout record
            payout_doc = self._create_payout_record(payout_data, result, {
                "purchase_invoice_name": purchase_invoice.name,
                "supplier_name": supplier.name,
                "document_type": "Purchase Invoice"
            })
            
            # Update purchase invoice
            purchase_invoice.db_set("seerbit_payout_reference", payout_reference)
            purchase_invoice.db_set("seerbit_payout_status", "Processing")
            
            return {
                "status": "success",
                "payout_reference": payout_reference,
                "payout_id": payout_doc.name,
                "amount": purchase_invoice.outstanding_amount
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Supplier Payment Error for {purchase_invoice_name}")
            frappe.throw(_("Failed to initiate supplier payment: {0}").format(str(e)))
    
    def initiate_general_payout(self, **kwargs):
        """Initiate general payout to any beneficiary"""
        required_params = ["beneficiary_name", "amount", "currency", "bank_account", "bank_code"]
        for param in required_params:
            if not kwargs.get(param):
                frappe.throw(_("Missing required parameter: {0}").format(param))
        
        # Verify account if requested
        if kwargs.get("verify_account", True):
            verification_result = verify_beneficiary_account(
                kwargs["bank_account"],
                kwargs["bank_code"],
                kwargs["beneficiary_name"]
            )
            
            if not verification_result.get("verified"):
                frappe.throw(_("Account verification failed: {0}").format(
                    verification_result.get("message", "Unknown error")
                ))
        
        # Generate payout reference
        payout_reference = kwargs.get("reference") or frappe.generate_hash(length=20)
        
        # Prepare payout data
        payout_data = {
            "reference": payout_reference,
            "amount": kwargs["amount"],
            "currency": kwargs["currency"],
            "bank_account": kwargs["bank_account"],
            "bank_code": kwargs["bank_code"],
            "beneficiary_name": kwargs["beneficiary_name"],
            "beneficiary_email": kwargs.get("beneficiary_email", ""),
            "narration": kwargs.get("narration", f"Payout to {kwargs['beneficiary_name']}"),
            "beneficiary_mobile": kwargs.get("beneficiary_mobile", "")
        }
        
        try:
            # Use enhanced payout if available
            if self.settings.get("use_enhanced_payouts", 0):
                result = self._initiate_enhanced_payout(payout_data)
            else:
                result = self.api_client.initiate_payout(**payout_data)
            
            # Create SeerBit Payout record
            payout_doc = self._create_payout_record(payout_data, result, {
                "beneficiary_type": kwargs.get("beneficiary_type", "Other"),
                "linking_reference": kwargs.get("linking_reference", ""),
                "document_type": "General Payout"
            })
            
            return {
                "status": "success",
                "payout_reference": payout_reference,
                "payout_id": payout_doc.name,
                "amount": kwargs["amount"]
            }
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "General Payout Error")
            frappe.throw(_("Failed to initiate payout: {0}").format(str(e)))
    
    def process_bulk_supplier_payments(self, purchase_invoice_names, verify_accounts=True):
        """Process bulk payments to suppliers"""
        if isinstance(purchase_invoice_names, str):
            import json
            purchase_invoice_names = json.loads(purchase_invoice_names)
        
        results = []
        successful_count = 0
        failed_count = 0
        
        for invoice_name in purchase_invoice_names:
            try:
                result = self.initiate_supplier_payment(invoice_name, verify_accounts)
                results.append({
                    "invoice_name": invoice_name,
                    "status": "success",
                    "payout_reference": result["payout_reference"],
                    "amount": result["amount"]
                })
                successful_count += 1
                
            except Exception as e:
                results.append({
                    "invoice_name": invoice_name,
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1
                frappe.log_error(f"Bulk supplier payment failed for {invoice_name}: {str(e)}", "SeerBit Bulk Payment Error")
        
        return {
            "status": "completed",
            "successful_count": successful_count,
            "failed_count": failed_count,
            "results": results,
            "total_processed": len(purchase_invoice_names)
        }
    
    def get_payout_status(self, payout_reference):
        """Get status of a specific payout"""
        try:
            verification_result = self.api_client.verify_payout(payout_reference)
            
            # Update local payout record if exists
            if frappe.db.exists("SeerBit Payout", {"payout_reference": payout_reference}):
                payout = frappe.get_doc("SeerBit Payout", {"payout_reference": payout_reference})
                
                payout_status = verification_result.get("status", "").upper()
                if payout_status == "SUCCESSFUL":
                    payout.status = "Paid"
                elif payout_status == "FAILED":
                    payout.status = "Failed"
                else:
                    payout.status = "Processing"
                
                payout.gateway_response = frappe.as_json(verification_result)
                payout.save(ignore_permissions=True)
            
            return verification_result
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Payout Status Check Error for {payout_reference}")
            frappe.throw(_("Failed to get payout status: {0}").format(str(e)))
    
    def _validate_supplier_payout_setup(self, supplier):
        """Validate supplier is properly set up for payouts"""
        if not supplier.seerbit_payout_enabled:
            frappe.throw(_("SeerBit payouts not enabled for supplier {0}").format(supplier.name))
        
        if not supplier.default_bank_account:
            frappe.throw(_("Default bank account not set for supplier {0}").format(supplier.name))
        
        if not supplier.seerbit_bank_code:
            frappe.throw(_("SeerBit bank code not set for supplier {0}").format(supplier.name))
    
    def _initiate_enhanced_payout(self, payout_data):
        """Initiate enhanced payout with proper SeerBit flow"""
        try:
            # Step 1: Verify account first
            verification_result = self.api_client.verify_bank_account(
                payout_data["bank_account"],
                payout_data["bank_code"]
            )
            
            frappe.log_error(f"Account verification result: {verification_result}", "SeerBit Enhanced Payout")
            
            # Step 2: Generate OTP
            otp_result = self.api_client.generate_otp_for_payout()
            otp = otp_result.get("otp")
            
            if not otp:
                frappe.throw(_("Failed to generate OTP for payout"))
            
            frappe.log_error(f"OTP generated successfully", "SeerBit Enhanced Payout")
            
            # Step 3: Generate signature
            signature = self.api_client.generate_payout_signature(payout_data, otp)
            
            if not signature:
                frappe.throw(_("Failed to generate signature for payout"))
            
            frappe.log_error(f"Signature generated successfully", "SeerBit Enhanced Payout")
            
            # Step 4: Execute enhanced payout
            result = self.api_client.execute_enhanced_payout(payout_data, otp, signature)
            
            frappe.log_error(f"Enhanced payout executed successfully: {result}", "SeerBit Enhanced Payout")
            
            return result
            
        except Exception as e:
            frappe.log_error(f"Enhanced payout failed: {str(e)}", "SeerBit Enhanced Payout Error")
            # Fallback to legacy payout if enhanced fails
            frappe.log_error("Falling back to legacy payout method", "SeerBit Enhanced Payout")
            return self.api_client.initiate_payout(**payout_data)
    
    def _create_payout_record(self, payout_data, api_result, meta_data):
        """Create SeerBit Payout record for tracking"""
        payout_doc = frappe.get_doc({
            "doctype": "SeerBit Payout",
            "payout_reference": payout_data["reference"],
            "status": "Processing",
            "amount": payout_data["amount"],
            "currency": payout_data["currency"],
            "beneficiary_type": meta_data.get("beneficiary_type", "Supplier"),
            "beneficiary_name": payout_data["beneficiary_name"],
            "beneficiary_email": payout_data["beneficiary_email"],
            "beneficiary_mobile": payout_data.get("beneficiary_mobile", ""),
            "bank_account": payout_data["bank_account"],
            "bank_code": payout_data["bank_code"],
            "narration": payout_data["narration"],
            "gateway_response": frappe.as_json(api_result),
            "meta_data": frappe.as_json(meta_data),
            "payout_method": "Enhanced" if self.settings.get("use_enhanced_payouts", 0) else "Legacy",
            "linking_reference": meta_data.get("linking_reference", "")
        })
        payout_doc.insert(ignore_permissions=True)
        return payout_doc


def process_purchase_invoice_payment_completion(payout_reference, payment_data):
    """Process successful purchase invoice payment completion"""
    try:
        payout = frappe.get_doc("SeerBit Payout", {"payout_reference": payout_reference})
        meta_data = frappe.parse_json(payout.meta_data or "{}")
        purchase_invoice_name = meta_data.get("purchase_invoice_name")
        
        if not purchase_invoice_name:
            frappe.throw(_("Purchase Invoice name not found in payout metadata"))
        
        purchase_invoice = frappe.get_doc("Purchase Invoice", purchase_invoice_name)
        
        # Create Payment Entry
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Pay"
        payment_entry.party_type = "Supplier"
        payment_entry.party = purchase_invoice.supplier
        payment_entry.posting_date = nowdate()
        
        # Get company's default cash/bank account
        company = frappe.get_doc("Company", purchase_invoice.company)
        payment_entry.paid_from = company.default_cash_account or company.default_bank_account
        payment_entry.paid_to = purchase_invoice.credit_to
        
        payment_entry.paid_amount = float(payment_data.get("amount", payout.amount))
        payment_entry.received_amount = payment_entry.paid_amount
        payment_entry.reference_no = payment_data.get("transactionRef") or payout.payout_reference
        payment_entry.reference_date = nowdate()
        payment_entry.mode_of_payment = "SeerBit"
        
        # Link to purchase invoice
        payment_entry.append("references", {
            "reference_doctype": "Purchase Invoice",
            "reference_name": purchase_invoice.name,
            "allocated_amount": payment_entry.paid_amount
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Update purchase invoice status
        purchase_invoice.db_set("seerbit_payout_status", "Paid")
        
        # Update payout
        payout.payment_entry = payment_entry.name
        payout.status = "Paid"
        payout.save(ignore_permissions=True)
        
        return payment_entry
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Purchase Invoice Payment Completion Error for {payout_reference}")
        frappe.throw(_("Failed to complete purchase invoice payment: {0}").format(str(e)))


# API endpoints
@frappe.whitelist()
def initiate_supplier_payment(purchase_invoice_name, verify_account=True):
    """API endpoint for initiating supplier payment"""
    buying_ops = SeerBitBuyingOperations()
    return buying_ops.initiate_supplier_payment(purchase_invoice_name, verify_account)


@frappe.whitelist()
def initiate_general_payout(**kwargs):
    """API endpoint for initiating general payout"""
    buying_ops = SeerBitBuyingOperations()
    return buying_ops.initiate_general_payout(**kwargs)


@frappe.whitelist()
def process_bulk_supplier_payments(purchase_invoice_names, verify_accounts=True):
    """API endpoint for bulk supplier payments"""
    buying_ops = SeerBitBuyingOperations()
    return buying_ops.process_bulk_supplier_payments(purchase_invoice_names, verify_accounts)


@frappe.whitelist()
def get_payout_status(payout_reference):
    """API endpoint for getting payout status"""
    buying_ops = SeerBitBuyingOperations()
    return buying_ops.get_payout_status(payout_reference)


@frappe.whitelist()
def get_eligible_purchase_invoices(company, supplier=None, from_date=None, to_date=None):
    """Get purchase invoices eligible for SeerBit payout"""
    filters = {
        "company": company,
        "docstatus": 1,
        "outstanding_amount": [">", 0],
        "seerbit_payout_status": ["in", ["Not Initiated", "Failed", ""]]
    }
    
    if supplier:
        filters["supplier"] = supplier
    if from_date:
        filters["posting_date"] = [">=", from_date]
    if to_date:
        filters.setdefault("posting_date", []).extend(["<=", to_date])
    
    # Get invoices with SeerBit enabled suppliers
    invoices = frappe.db.sql("""
        SELECT pi.name, pi.supplier, pi.supplier_name, pi.outstanding_amount, 
               pi.currency, pi.posting_date
        FROM `tabPurchase Invoice` pi
        INNER JOIN `tabSupplier` s ON pi.supplier = s.name
        WHERE pi.company = %(company)s
        AND pi.docstatus = 1
        AND pi.outstanding_amount > 0
        AND (pi.seerbit_payout_status IS NULL OR pi.seerbit_payout_status IN ('Not Initiated', 'Failed'))
        AND s.seerbit_payout_enabled = 1
        AND s.seerbit_bank_code IS NOT NULL
        AND s.default_bank_account IS NOT NULL
        {supplier_filter}
        {date_filter}
        ORDER BY pi.posting_date DESC
    """.format(
        supplier_filter="AND pi.supplier = %(supplier)s" if supplier else "",
        date_filter="AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s" if from_date and to_date else ""
    ), {
        "company": company,
        "supplier": supplier,
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=True)
    
    return invoices
