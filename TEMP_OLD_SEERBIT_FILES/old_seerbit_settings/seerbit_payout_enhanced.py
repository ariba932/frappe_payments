# Enhanced SeerBit Settings for proper payout flow implementation
import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password
import requests
import json
from frappe.utils import get_request_site_address

class SeerBitPayoutEnhanced:
    """
    Enhanced SeerBit Payout implementation following proper API flow:
    1. Email/Password authentication for bearer token
    2. Generate OTP (pocket ID) 
    3. Generate signature using OTP
    4. Initiate payout with signature
    """
    
    def __init__(self, settings_doc):
        self.settings = settings_doc
        self.base_url = "https://pocket.seerbitapi.com" if not settings_doc.sandbox_mode else "https://sandbox.seerbitapi.com"
        self.bearer_token = None
        self.pocket_id = None
        
    def authenticate_with_credentials(self):
        """
        Step 1: Authenticate using email/password to get bearer token
        Note: This step requires SeerBit dashboard credentials
        """
        # Get credentials from settings
        email = self.settings.get_password("payout_email")
        password = self.settings.get_password("payout_password")
        
        if not email or not password:
            frappe.throw(_("SeerBit payout email and password are required for authentication"))
        
        url = f"{self.base_url}/auth/login"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "email": email,
            "password": password
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "SUCCESS":
                    self.bearer_token = result["data"]["token"]
                    self.pocket_id = result["data"]["pocketId"]
                    return True
                else:
                    frappe.log_error(str(result), "SeerBit Authentication Failure")
                    frappe.throw(_("Authentication failed: {0}").format(result.get("message", "Unknown error")))
            else:
                frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Auth HTTP Error")
                frappe.throw(_("Authentication request failed with status: {0}").format(response.status_code))
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SeerBit Authentication Network Error")
            frappe.throw(_("Network error during authentication: {0}").format(str(e)))
    
    def generate_otp(self):
        """
        Step 2: Generate OTP for disbursement approval
        """
        if not self.bearer_token or not self.pocket_id:
            self.authenticate_with_credentials()
        
        url = f"{self.base_url}/pocket/getOtp"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bearer_token}",
            "Public-Key": self.settings.public_key
        }
        data = {
            "actionItem": "APPROVE_DISBURSEMENT",
            "pocketId": self.pocket_id
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("responseCode") == "00":
                    return result["data"]["otp"]
                else:
                    frappe.log_error(str(result), "SeerBit OTP Generation Failure")
                    frappe.throw(_("OTP generation failed: {0}").format(result.get("message", "Unknown error")))
            else:
                frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit OTP HTTP Error")
                frappe.throw(_("OTP request failed with status: {0}").format(response.status_code))
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SeerBit OTP Network Error")
            frappe.throw(_("Network error during OTP generation: {0}").format(str(e)))
    
    def generate_signature(self, reference, amount, currency, description, account_number, bank_code, otp):
        """
        Step 3: Generate signature for payout authorization
        """
        if not self.bearer_token:
            self.authenticate_with_credentials()
        
        url = f"{self.base_url}/pocket/payout/get-signature"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bearer_token}"
        }
        data = {
            "reference": reference,
            "amount": str(amount),
            "currency": currency,
            "description": description or "Payout transaction",
            "accountNumber": account_number,
            "bankCode": bank_code,
            "actionType": "APPROVE_DISBURSEMENT",
            "passKey": otp
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("responseCode") == "00":
                    return result["data"]  # This is the signature
                else:
                    frappe.log_error(str(result), "SeerBit Signature Generation Failure")
                    frappe.throw(_("Signature generation failed: {0}").format(result.get("message", "Unknown error")))
            else:
                frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Signature HTTP Error")
                frappe.throw(_("Signature request failed with status: {0}").format(response.status_code))
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SeerBit Signature Network Error")
            frappe.throw(_("Network error during signature generation: {0}").format(str(e)))
    
    def initiate_payout_enhanced(self, beneficiary_name, beneficiary_email, amount, currency, 
                               bank_account, bank_code, bank_name=None, narration=None, 
                               beneficiary_type=None, beneficiary_mobile=None, meta_data=None):
        """
        Step 4: Complete payout flow with proper authentication, OTP, and signature
        """
        try:
            # Step 1: Authenticate and get bearer token
            self.authenticate_with_credentials()
            
            # Step 2: Generate OTP
            otp = self.generate_otp()
            
            # Generate unique reference
            payout_reference = frappe.generate_hash(length=20)
            
            # Step 3: Generate signature
            signature = self.generate_signature(
                reference=payout_reference,
                amount=amount,
                currency=currency,
                description=narration or f"Payout to {beneficiary_name}",
                account_number=bank_account,
                bank_code=bank_code,
                otp=otp
            )
            
            # Step 4: Initiate payout with signature
            url = f"{self.base_url}/pocket/payout/encrypted/pocket-id/{self.pocket_id}"
            headers = {
                "Content-Type": "application/json",
                "Public-Key": self.settings.public_key,
                "Authorization": f"Bearer {self.bearer_token}"
            }
            
            payout_data = {
                "reference": payout_reference,
                "amount": str(amount),
                "currency": currency,
                "description": narration or f"Payout to {beneficiary_name}",
                "accountNumber": bank_account,
                "bankCode": bank_code,
                "passKey": otp,
                "actionType": "APPROVE_DISBURSEMENT",
                "signature": signature
            }
            
            response = requests.post(url, headers=headers, json=payout_data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get("responseCode") == "00":
                    # Create SeerBit Payout DocType record
                    payout_doc = frappe.get_doc({
                        "doctype": "SeerBit Payout",
                        "payout_reference": payout_reference,
                        "status": "Processing",
                        "amount": amount,
                        "currency": currency,
                        "beneficiary_type": beneficiary_type or "Other",
                        "beneficiary_name": beneficiary_name,
                        "beneficiary_email": beneficiary_email or "",
                        "beneficiary_mobile": beneficiary_mobile or "",
                        "bank_account": bank_account,
                        "bank_code": bank_code,
                        "bank_name": bank_name or "",
                        "narration": narration or "",
                        "gateway_response": frappe.as_json(result),
                        "meta_data": frappe.as_json({
                            "pocket_id": self.pocket_id,
                            "linking_reference": result["data"].get("linkingreference"),
                            **(meta_data or {})
                        }),
                    })
                    payout_doc.insert(ignore_permissions=True)
                    return {
                        "status": "success",
                        "payout_reference": payout_reference,
                        "linking_reference": result["data"].get("linkingreference"),
                        "docname": payout_doc.name
                    }
                else:
                    frappe.log_error(str(result), "SeerBit Payout Initiation Failure")
                    frappe.throw(_("Payout initiation failed: {0}").format(result.get("message", "Unknown error")))
            else:
                frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Payout HTTP Error")
                frappe.throw(_("Payout request failed with status: {0}").format(response.status_code))
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "SeerBit Enhanced Payout Error")
            frappe.throw(_("Enhanced payout failed: {0}").format(str(e)))

# Helper functions for ERPNext integration
@frappe.whitelist()
def initiate_salary_payout_enhanced(salary_slip_name):
    """Enhanced salary payout using proper SeerBit flow"""
    salary_slip = frappe.get_doc("Salary Slip", salary_slip_name)
    employee = frappe.get_doc("Employee", salary_slip.employee)
    
    if not employee.seerbit_payout_enabled:
        frappe.throw(_("SeerBit payout not enabled for employee {0}").format(employee.name))
    
    if not employee.seerbit_bank_code:
        frappe.throw(_("SeerBit bank code not set for employee {0}").format(employee.name))
    
    settings = frappe.get_doc("SeerBit Settings")
    payout_handler = SeerBitPayoutEnhanced(settings)
    
    try:
        result = payout_handler.initiate_payout_enhanced(
            beneficiary_name=employee.employee_name,
            beneficiary_email=employee.company_email or employee.personal_email,
            amount=salary_slip.net_pay,
            currency="NGN",
            bank_account=employee.bank_ac_no,
            bank_code=employee.seerbit_bank_code,
            narration=f"Salary payment for {salary_slip.employee_name} - {salary_slip.start_date}",
            beneficiary_type="Employee",
            meta_data={"salary_slip": salary_slip_name}
        )
        
        # Update salary slip
        salary_slip.seerbit_payout_reference = result["payout_reference"]
        salary_slip.seerbit_payout_status = "Processing"
        salary_slip.save(ignore_permissions=True)
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Enhanced Salary Payout Error for {salary_slip_name}")
        frappe.throw(_("Failed to initiate enhanced salary payout: {0}").format(str(e)))

@frappe.whitelist()
def initiate_supplier_payout_enhanced(payment_entry_name):
    """Enhanced supplier payout using proper SeerBit flow"""
    payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
    supplier = frappe.get_doc("Supplier", payment_entry.party)
    
    if not supplier.seerbit_payout_enabled:
        frappe.throw(_("SeerBit payout not enabled for supplier {0}").format(supplier.name))
    
    if not supplier.seerbit_bank_code:
        frappe.throw(_("SeerBit bank code not set for supplier {0}").format(supplier.name))
    
    # Get supplier bank account
    bank_account = frappe.get_doc("Bank Account", supplier.default_bank_account)
    
    settings = frappe.get_doc("SeerBit Settings")
    payout_handler = SeerBitPayoutEnhanced(settings)
    
    try:
        result = payout_handler.initiate_payout_enhanced(
            beneficiary_name=supplier.supplier_name,
            beneficiary_email=supplier.email_id,
            amount=payment_entry.paid_amount,
            currency=payment_entry.paid_to_account_currency,
            bank_account=bank_account.bank_account_no,
            bank_code=supplier.seerbit_bank_code,
            narration=f"Payment to {supplier.supplier_name} - {payment_entry.reference_no}",
            beneficiary_type="Supplier",
            meta_data={"payment_entry": payment_entry_name}
        )
        
        # Update payment entry
        payment_entry.seerbit_payout_reference = result["payout_reference"]
        payment_entry.seerbit_payout_status = "Processing"
        payment_entry.save(ignore_permissions=True)
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Enhanced Supplier Payout Error for {payment_entry_name}")
        frappe.throw(_("Failed to initiate enhanced supplier payout: {0}").format(str(e)))
