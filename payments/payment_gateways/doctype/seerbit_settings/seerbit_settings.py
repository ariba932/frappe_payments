#SerBit Settings -  document for managing SeerBit payment gateway settings and operations.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
import requests
import json


class SeerBitSettings(Document):
    supported_currencies = ["NGN", "USD", "GBP", "EUR"]
    
    def validate(self):
        self.validate_api_credentials()
    
    def validate_api_credentials(self):
        """Validate API credentials by making a test call"""
        if self.is_enabled and self.public_key and self.private_key:
            try:
                # Test the credentials by getting an encrypted key
                self.get_encrypted_key()
                frappe.msgprint(_("API credentials validated successfully"), alert=True)
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), "SeerBit API Credentials Validation Error")
                frappe.throw(_("Invalid API credentials: {0}").format(str(e)))
    
    def get_encrypted_key(self, max_retries=2):
        """Get encrypted key for API authentication"""
       # private_key = get_decrypted_password("SeerBit Settings", "SeerBit Settings", "private_key")
        
        #if not private_key:
         #   frappe.throw(_("Private key not found"))
        
        key_combination = f"***.***"  # Masked for logging, never log real keys
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        url = f"{base_url}/api/v2/encrypt/keys"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "key": f"{self.private_key}.{self.public_key}"
        }
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "SUCCESS":
                        return result["data"]["EncryptedSecKey"]["encryptedKey"]
                    else:
                        frappe.log_error(str(result), "SeerBit Encrypted Key Failure")
                        frappe.throw(_("Failed to get encrypted key: {0}").format(result.get("message", "Unknown error")))
                else:
                    frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Encrypted Key HTTP Error")
                    frappe.throw(_("API request failed with status: {0}").format(response.status_code))
            except Exception as e:
                last_exception = e
                if attempt == max_retries:
                    frappe.log_error(frappe.get_traceback(), "SeerBit Encrypted Key Network Error")
                    frappe.throw(_("Network/API error while getting encrypted key: {0}").format(str(e)))
        if last_exception:
            frappe.throw(_("Failed to get encrypted key after retries: {0}").format(str(last_exception)))
    
    def get_payment_url(self, **kwargs):
        """Create payment and return checkout URL"""
        required_params = ["amount", "currency", "email", "fullName", "paymentReference", "callbackUrl"]
        for param in required_params:
            if not kwargs.get(param):
                frappe.throw(_("Missing required parameter: {0}").format(param))
        encrypted_key = self.get_encrypted_key()
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        url = f"{base_url}/api/v2/payments"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {encrypted_key}"
        }
        payment_data = {
            "publicKey": self.public_key,
            "amount": str(kwargs["amount"]),
            "currency": kwargs["currency"],
            "country": kwargs.get("country", "NG"),
            "paymentReference": kwargs["paymentReference"],
            "email": kwargs["email"],
            "fullName": kwargs["fullName"],
            "tokenize": kwargs.get("tokenize", "false"),
            "callbackUrl": kwargs["callbackUrl"]
        }
        if kwargs.get("productId"):
            payment_data["productId"] = kwargs["productId"]
        if kwargs.get("productDescription"):
            payment_data["productDescription"] = kwargs["productDescription"]
        last_exception = None
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=payment_data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "SUCCESS":
                        return {
                            "redirect_url": result["data"]["payments"]["redirectLink"],
                            "payment_status": result["data"]["payments"]["paymentStatus"],
                            "reference": kwargs["paymentReference"]
                        }
                    else:
                        frappe.log_error(str(result), "SeerBit Payment Creation Failure")
                        frappe.throw(_("Payment creation failed: {0}").format(result.get("message", "Unknown error")))
                else:
                    frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Payment API HTTP Error")
                    frappe.throw(_("Payment API request failed with status: {0}").format(response.status_code))
            except Exception as e:
                last_exception = e
                if attempt == 2:
                    frappe.log_error(frappe.get_traceback(), "SeerBit Payment API Network Error")
                    frappe.throw(_("Network/API error while creating payment: {0}").format(str(e)))
        if last_exception:
            frappe.throw(_("Failed to create payment after retries: {0}").format(str(last_exception)))
    
    def verify_payment(self, payment_reference):
        """Verify payment status"""
        encrypted_key = self.get_encrypted_key()
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        url = f"{base_url}/api/v3/payments/query/{payment_reference}"
        headers = {
            "Authorization": f"Bearer {encrypted_key}"
        }
        last_exception = None
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "SUCCESS":
                        return result["data"]
                    else:
                        frappe.log_error(str(result), "SeerBit Payment Verification Failure")
                        frappe.throw(_("Payment verification failed: {0}").format(result.get("message", "Unknown error")))
                else:
                    frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Payment Verification HTTP Error")
                    frappe.throw(_("Verification API request failed with status: {0}").format(response.status_code))
            except Exception as e:
                last_exception = e
                if attempt == 2:
                    frappe.log_error(frappe.get_traceback(), "SeerBit Payment Verification Network Error")
                    frappe.throw(_("Network/API error while verifying payment: {0}").format(str(e)))
        if last_exception:
            frappe.throw(_("Failed to verify payment after retries: {0}").format(str(last_exception)))
    
    def initiate_payout(self, beneficiary_name, beneficiary_email, amount, currency, bank_account, bank_code, bank_name=None, narration=None, beneficiary_type=None, beneficiary_mobile=None, meta_data=None):
        """Initiate a single payout via SeerBit with all required fields"""
        encrypted_key = self.get_encrypted_key()
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        url = f"{base_url}/api/v2/payouts"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {encrypted_key}"
        }
        payout_reference = frappe.generate_hash(length=20)
        
        # Prepare complete payout data as per Seerbit API requirements
        payout_data = {
            "reference": payout_reference,
            "amount": str(amount),
            "currency": currency,
            "bankAccount": bank_account,
            "bankCode": bank_code,
            "beneficiaryName": beneficiary_name,
            "beneficiaryEmail": beneficiary_email or "",
            "narration": narration or "",
        }
        
        # Add optional fields
        if bank_name:
            payout_data["bankName"] = bank_name
        if beneficiary_mobile:
            payout_data["beneficiaryMobile"] = beneficiary_mobile
        
        last_exception = None
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=payout_data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "SUCCESS":
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
                            "meta_data": frappe.as_json(meta_data or {}),
                        })
                        payout_doc.insert(ignore_permissions=True)
                        return {
                            "status": "success",
                            "payout_reference": payout_reference,
                            "docname": payout_doc.name
                        }
                    else:
                        frappe.log_error(str(result), "SeerBit Payout Initiation Failure")
                        frappe.throw(_("Payout initiation failed: {0}").format(result.get("message", "Unknown error")))
                else:
                    frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Payout API HTTP Error")
                    frappe.throw(_("Payout API request failed with status: {0}").format(response.status_code))
            except Exception as e:
                last_exception = e
                if attempt == 2:
                    frappe.log_error(frappe.get_traceback(), "SeerBit Payout API Network Error")
                    frappe.throw(_("Network/API error while initiating payout: {0}").format(str(e)))
        if last_exception:
            frappe.throw(_("Failed to initiate payout after retries: {0}").format(str(last_exception)))

    def initiate_bulk_payouts(self, payout_list):
        """Initiate multiple payouts. payout_list: list of dicts with keys matching initiate_payout args."""
        results = []
        for payout in payout_list:
            try:
                result = self.initiate_payout(**payout)
                results.append(result)
            except Exception as e:
                results.append({"status": "failed", "error": str(e), "payout": payout})
        return results

    def verify_payout(self, payout_reference):
        """Verify payout status via SeerBit API"""
        encrypted_key = self.get_encrypted_key()
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        url = f"{base_url}/api/v2/payouts/query/{payout_reference}"
        headers = {
            "Authorization": f"Bearer {encrypted_key}"
        }
        last_exception = None
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "SUCCESS":
                        return result["data"]
                    else:
                        frappe.log_error(str(result), "SeerBit Payout Verification Failure")
                        frappe.throw(_("Payout verification failed: {0}").format(result.get("message", "Unknown error")))
                else:
                    frappe.log_error(f"Status: {response.status_code}, Response: {response.text}", "SeerBit Payout Verification HTTP Error")
                    frappe.throw(_("Payout verification API request failed with status: {0}").format(response.status_code))
            except Exception as e:
                last_exception = e
                if attempt == 2:
                    frappe.log_error(frappe.get_traceback(), "SeerBit Payout Verification Network Error")
                    frappe.throw(_("Network/API error while verifying payout: {0}").format(str(e)))
        if last_exception:
            frappe.throw(_("Failed to verify payout after retries: {0}").format(str(last_exception)))

    def auto_validate_pending_payouts(self):
        """Auto-validate all pending/processing payouts (to be called by a scheduled job)"""
        pending_payouts = frappe.get_all("SeerBit Payout", filters={"status": ["in", ["Pending", "Processing"]]}, fields=["name", "payout_reference"])
        for payout in pending_payouts:
            try:
                status_data = self.verify_payout(payout["payout_reference"])
                doc = frappe.get_doc("SeerBit Payout", payout["name"])
                # Update status and meta_data
                doc.status = status_data.get("status", doc.status)
                doc.meta_data = frappe.as_json(status_data)
                doc.save(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Auto payout validation failed for {payout['name']}")


#Method to handle the syncrhonization of bank details from seearbit
def refresh_bank_codes(self):
    """Refresh bank codes from Seerbit API"""
    if not self.is_enabled:
        frappe.throw(_("SeerBit is not enabled"))
    
    encrypted_key = self.get_encrypted_key()
    base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
    url = f"{base_url}/api/v2/banks"
    headers = {
        "Authorization": f"Bearer {encrypted_key}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "SUCCESS":
                banks = result.get("data", [])
                self.sync_bank_codes(banks)
                frappe.msgprint(_("Successfully refreshed {0} bank codes").format(len(banks)))
            else:
                frappe.throw(_("Failed to fetch bank codes: {0}").format(result.get("message", "Unknown error")))
        else:
            frappe.throw(_("API request failed with status: {0}").format(response.status_code))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SeerBit Bank Code Refresh Error")
        frappe.throw(_("Error refreshing bank codes: {0}").format(str(e)))

def sync_bank_codes(self, banks):
    """Sync bank codes to SeerBit Bank Code doctype and ERPNext Bank"""
    for bank_data in banks:
        bank_code = bank_data.get("code")
        bank_name = bank_data.get("name")
        
        if not bank_code or not bank_name:
            continue
            
        # Create/Update SeerBit Bank Code
        if frappe.db.exists("SeerBit Bank Code", bank_code):
            doc = frappe.get_doc("SeerBit Bank Code", bank_code)
            doc.bank_name = bank_name
            doc.is_active = bank_data.get("is_active", 1)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc({
                "doctype": "SeerBit Bank Code",
                "bank_code": bank_code,
                "bank_name": bank_name,
                "is_active": bank_data.get("is_active", 1)
            })
            doc.insert(ignore_permissions=True)
        
        # Create/Update ERPNext Bank
        self.sync_to_erpnext_bank(bank_code, bank_name)

def sync_to_erpnext_bank(self, bank_code, bank_name):
    """Sync bank to ERPNext Bank doctype"""
    bank_name_clean = bank_name.replace("Limited", "Ltd").replace("PLC", "Plc")
    
    if not frappe.db.exists("Bank", bank_name_clean):
        try:
            bank_doc = frappe.get_doc({
                "doctype": "Bank",
                "bank_name": bank_name_clean,
                "seerbit_bank_code": bank_code,
                "payment_gateway_source": "SeerBit"
            })
            bank_doc.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to create Bank {bank_name}: {str(e)}", "Bank Creation Error")
    else:
        try:
            bank_doc = frappe.get_doc("Bank", bank_name_clean)
            bank_doc.seerbit_bank_code = bank_code
            bank_doc.payment_gateway_source = "SeerBit"
            bank_doc.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to update Bank {bank_name}: {str(e)}", "Bank Update Error")