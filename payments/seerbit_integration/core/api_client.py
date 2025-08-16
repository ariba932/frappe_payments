# -*- coding: utf-8 -*-
"""
SeerBit API Client - Core HTTP client for all SeerBit API operations
Consolidates all API calls and authentication logic
"""

import frappe
from frappe import _
import requests
import json
import hmac
import hashlib
from frappe.utils.password import get_decrypted_password
from frappe.utils import get_request_site_address


class SeerBitAPIClient:
    """Centralized SeerBit API client for all operations"""
    
    def __init__(self, settings_doc=None):
        self.settings = settings_doc or self._get_seerbit_settings()
        # Use 'environment' field instead of 'sandbox_mode'
        is_sandbox = getattr(self.settings, 'environment', 'Production') == 'Sandbox'
        self.base_url = "https://sandbox.seerbitapi.com" if is_sandbox else "https://seerbitapi.com"
        self.pocket_base_url = "https://sandbox.seerbitapi.com" if is_sandbox else "https://pocket.seerbitapi.com"
        self._encrypted_key = None
        self._bearer_token = None
    
    def _get_seerbit_settings(self):
        """Get SeerBit Settings document with standard doctype approach"""
        try:
            # Try to get the specific "Seerbit Gateway" record
            settings = frappe.get_doc("SeerBit Settings", "Seerbit Gateway")
            if not settings:
                frappe.throw(_("SeerBit Settings record 'Seerbit Gateway' not found"))
            return settings
        except frappe.DoesNotExistError:
            # If "Seerbit Gateway" doesn't exist, try to get any active settings
            settings_list = frappe.get_all("SeerBit Settings", 
                filters={"is_active": 1}, 
                limit=1
            )
            if settings_list:
                return frappe.get_doc("SeerBit Settings", settings_list[0].name)
            else:
                frappe.throw(_("No active SeerBit Settings found. Please create a SeerBit Settings record named 'Seerbit Gateway'"))
    
    def get_encrypted_key(self, force_refresh=False):
        """Get encrypted key for standard API authentication"""
        if self._encrypted_key and not force_refresh:
            return self._encrypted_key
            
        # Use 'secret_key' field from the SeerBit Settings doctype
        private_key = self.settings.get_password("secret_key")
        if not private_key:
            frappe.throw(_("Secret key not found in SeerBit Settings"))
        
        url = f"{self.base_url}/api/v2/encrypt/keys"
        headers = {"Content-Type": "application/json"}
        data = {"key": f"{private_key}.{self.settings.public_key}"}
        
        response = self._make_request("POST", url, headers=headers, json_data=data)
        
        if response.get("status") == "SUCCESS":
            self._encrypted_key = response["data"]["EncryptedSecKey"]["encryptedKey"]
            return self._encrypted_key
        else:
            frappe.throw(_("Failed to get encrypted key: {0}").format(response.get("message", "Unknown error")))
    
    def get_bearer_token(self, force_refresh=False):
        """Get bearer token for enhanced payout operations using correct endpoint"""
        if self._bearer_token and not force_refresh:
            return self._bearer_token
            
        # Use correct field names from SeerBit Settings doctype
        if not self.settings.payout_email or not self.settings.payout_password:
            frappe.throw(_("Payout email and password required for enhanced operations"))
        
        url = f"{self.pocket_base_url}/pocket/authenticate"
        headers = {"Content-Type": "application/json"}
        data = {
            "email": self.settings.payout_email,
            "password": self.settings.get_password("payout_password")
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=data)
        
        if response.get("responseCode") == "00":
            self._bearer_token = response["data"]["bearerToken"]
            # Store expiry time for future reference
            self.token_expiry = response["data"].get("expiryTime")
            return self._bearer_token
        else:
            frappe.throw(_("Failed to authenticate for payout operations: {0}").format(response.get("message", "Unknown error")))
    
    def create_payment(self, **kwargs):
        """Create payment for checkout"""
        encrypted_key = self.get_encrypted_key()
        url = f"{self.base_url}/api/v2/payments"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {encrypted_key}"
        }
        
        payment_data = {
            "publicKey": self.settings.public_key,
            "amount": str(kwargs["amount"]),
            "currency": kwargs["currency"],
            "country": kwargs.get("country", "NG"),
            "paymentReference": kwargs["payment_reference"],
            "email": kwargs["email"],
            "fullName": kwargs["full_name"],
            "tokenize": kwargs.get("tokenize", "false"),
            "callbackUrl": kwargs.get("callback_url", self._get_default_callback_url())
        }
        
        # Add optional fields
        for field in ["productId", "productDescription"]:
            if kwargs.get(field):
                payment_data[field] = kwargs[field]
        
        response = self._make_request("POST", url, headers=headers, json_data=payment_data)
        
        if response.get("status") == "SUCCESS":
            return response["data"]["payments"]
        else:
            frappe.throw(_("Payment creation failed: {0}").format(response.get("message", "Unknown error")))
    
    def create_payment_link(self, payment_data):
        """Create payment link for checkout - alias for create_payment with better return format"""
        try:
            # Map the payment_data to the expected kwargs format
            kwargs = {
                "amount": payment_data.get("amount"),
                "currency": payment_data.get("currency", "NGN"),
                "country": payment_data.get("country", "NG"),
                "payment_reference": payment_data.get("productId", frappe.generate_hash(length=12)),
                "email": payment_data.get("email"),
                "full_name": payment_data.get("fullName", ""),
                "callback_url": payment_data.get("callbackUrl"),
                "productId": payment_data.get("productId"),
                "productDescription": payment_data.get("productDescription")
            }
            
            # Create the payment using the existing method
            payment_response = self.create_payment(**kwargs)
            
            # Return in the expected format for SeerBitPaymentRequest
            return {
                "status": "SUCCESS",
                "data": {
                    "reference": payment_response.get("paymentReference", kwargs["payment_reference"]),
                    "redirectLink": payment_response.get("redirectLink", ""),
                    "paymentReference": payment_response.get("paymentReference", kwargs["payment_reference"])
                }
            }
            
        except Exception as e:
            frappe.log_error(f"Payment link creation error: {str(e)}", "SeerBit Payment Link")
            return {
                "status": "FAILED",
                "message": str(e)
            }
    
    def verify_payment(self, payment_reference):
        """Verify payment status"""
        encrypted_key = self.get_encrypted_key()
        url = f"{self.base_url}/api/v3/payments/query/{payment_reference}"
        headers = {"Authorization": f"Bearer {encrypted_key}"}
        
        response = self._make_request("GET", url, headers=headers)
        frappe.log_error("Verify response", response)
        
        # Return the full response structure to the caller
        # Let the caller handle the response structure and status checking
        return response
    
    def initiate_payout(self, **kwargs):
        """Initiate payout using legacy method"""
        encrypted_key = self.get_encrypted_key()
        url = f"{self.base_url}/api/v2/payouts"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {encrypted_key}"
        }
        
        payout_data = {
            "reference": kwargs["reference"],
            "amount": str(kwargs["amount"]),
            "currency": kwargs["currency"],
            "bankAccount": kwargs["bank_account"],
            "bankCode": kwargs["bank_code"],
            "beneficiaryName": kwargs["beneficiary_name"],
            "beneficiaryEmail": kwargs.get("beneficiary_email", ""),
            "narration": kwargs.get("narration", "")
        }
        
        # Add optional fields
        for field in ["bankName", "beneficiaryMobile"]:
            if kwargs.get(field):
                payout_data[field] = kwargs[field]
        
        response = self._make_request("POST", url, headers=headers, json_data=payout_data)
        
        if response.get("status") == "SUCCESS":
            return response["data"]
        else:
            frappe.throw(_("Payout initiation failed: {0}").format(response.get("message", "Unknown error")))
    
    def generate_otp_for_payout(self, pocket_id=None):
        """Generate OTP for enhanced payout flow using correct endpoint"""
        bearer_token = self.get_bearer_token()
        pocket_id = pocket_id or self.settings.default_pocket_id
        
        if not pocket_id:
            frappe.throw(_("Pocket ID is required for OTP generation"))
        
        url = f"{self.pocket_base_url}/pocket/getOtp"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        data = {
            "actionItem": "APPROVE_DISBURSEMENT",
            "pocketId": pocket_id
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=data)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("OTP generation failed: {0}").format(response.get("message", "Unknown error")))
    
    def generate_payout_signature(self, payout_data, otp):
        """Generate signature for enhanced payout using correct endpoint"""
        bearer_token = self.get_bearer_token()
        url = f"{self.pocket_base_url}/pocket/payout/get-signature"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}"
        }
        
        data = {
            "reference": payout_data["reference"],
            "amount": str(payout_data["amount"]),
            "currency": payout_data["currency"],
            "description": payout_data.get("narration", ""),
            "accountNumber": payout_data["bank_account"],
            "bankCode": payout_data["bank_code"],
            "actionType": "APPROVE_DISBURSEMENT",
            "passKey": otp
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=data)
        
        if response.get("responseCode") == "00":
            return response["data"]  # This is the signature string
        else:
            frappe.throw(_("Signature generation failed: {0}").format(response.get("message", "Unknown error")))
    
    def execute_enhanced_payout(self, payout_data, otp, signature, pocket_id=None):
        """Execute enhanced payout using correct SeerBit endpoint and flow"""
        bearer_token = self.get_bearer_token()
        pocket_id = pocket_id or self.settings.default_pocket_id
        
        if not pocket_id:
            frappe.throw(_("Pocket ID is required for enhanced payout"))
        
        url = f"{self.pocket_base_url}/pocket/payout/encrypted/pocket-id/{pocket_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        data = {
            "reference": payout_data["reference"],
            "amount": str(payout_data["amount"]),
            "currency": payout_data["currency"],
            "description": payout_data.get("narration", ""),
            "accountNumber": payout_data["bank_account"],
            "bankCode": payout_data["bank_code"],
            "passKey": otp,
            "actionType": "APPROVE_DISBURSEMENT",
            "signature": signature
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=data)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Enhanced payout execution failed: {0}").format(response.get("message", "Unknown error")))
    
    def initiate_enhanced_payout(self, signature, **kwargs):
        """Initiate enhanced payout with signature"""
        bearer_token = self.get_bearer_token()
        url = f"{self.pocket_base_url}/pocket/payouts"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Signature": signature
        }
        
        payout_data = {
            "reference": kwargs["reference"],
            "amount": str(kwargs["amount"]),
            "currency": kwargs["currency"],
            "bankAccount": kwargs["bank_account"],
            "bankCode": kwargs["bank_code"],
            "beneficiaryName": kwargs["beneficiary_name"],
            "beneficiaryEmail": kwargs.get("beneficiary_email", ""),
            "narration": kwargs.get("narration", ""),
            "pocketId": kwargs["pocket_id"]
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=payout_data)
        
        if response.get("status") == "SUCCESS":
            return response["data"]
        else:
            frappe.throw(_("Enhanced payout failed: {0}").format(response.get("message", "Unknown error")))
    
    def verify_payout(self, payout_reference):
        """Verify payout status"""
        encrypted_key = self.get_encrypted_key()
        url = f"{self.base_url}/api/v2/payouts/query/{payout_reference}"
        headers = {"Authorization": f"Bearer {encrypted_key}"}
        
        response = self._make_request("POST", url, headers=headers)
        
        if response.get("status") == "SUCCESS":
            return response["data"]
        else:
            frappe.throw(_("Payout verification failed: {0}").format(response.get("message", "Unknown error")))
    
    def verify_bank_account(self, account_number, bank_code):
        """Verify bank account details using correct SeerBit endpoint"""
        bearer_token = self.get_bearer_token()
        url = f"{self.pocket_base_url}/pocket/payout/account-enquiry"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}"
        }
        
        data = {
            "accountnumber": account_number,
            "bankcode": bank_code
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=data)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Account verification failed: {0}").format(response.get("message", "Unknown error")))
    
    def get_bank_list(self):
        """Get list of supported banks"""
        encrypted_key = self.get_encrypted_key()
        url = f"{self.pocket_base_url}/pocket/banks"
        headers = {"Authorization": f"Bearer {encrypted_key}"}
        
        response = self._make_request("GET", url, headers=headers)
        
        if response.get("status") == "SUCCESS":
            return response["data"]
        else:
            frappe.throw(_("Failed to fetch bank list: {0}").format(response.get("message", "Unknown error")))
    
    def get_wallet_balance(self, pocket_id=None):
        """Get wallet balance for payout operations using correct endpoint"""
        bearer_token = self.get_bearer_token()
        pocket_id = pocket_id or self.settings.default_pocket_id
        
        if not pocket_id:
            frappe.throw(_("Pocket ID is required for balance check"))
        
        url = f"{self.pocket_base_url}/pocket/balance/pocket-id/{pocket_id}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get wallet balance: {0}").format(response.get("message", "Unknown error")))
    
    def create_sub_pocket(self, parent_pocket_id, sub_pocket_data):
        """Create sub-pocket using SeerBit API"""
        bearer_token = self.get_bearer_token()
        
        url = f"{self.pocket_base_url}/pocket/pocket-id/{parent_pocket_id}/sub-pocket"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=sub_pocket_data)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Sub-pocket creation failed: {0}").format(response.get("message", "Unknown error")))
    
    def transfer_between_pockets(self, from_pocket_id, to_pocket_id, transfer_data):
        """Transfer funds between pockets using SeerBit API"""
        bearer_token = self.get_bearer_token()
        
        url = f"{self.pocket_base_url}/pocket/transfer/from-pocket/{from_pocket_id}/to-pocket/{to_pocket_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self._make_request("POST", url, headers=headers, json_data=transfer_data)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Pocket transfer failed: {0}").format(response.get("message", "Unknown error")))
    
    def get_pocket_details(self, pocket_id):
        """Get detailed information about a pocket"""
        bearer_token = self.get_bearer_token()
        
        url = f"{self.pocket_base_url}/pocket/pocket-id/{pocket_id}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get pocket details: {0}").format(response.get("message", "Unknown error")))
    
    def get_pocket_transactions(self, pocket_id, page=0, size=20):
        """Get transaction history for a pocket"""
        bearer_token = self.get_bearer_token()
        
        url = f"{self.pocket_base_url}/pocket/transaction/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        params = {
            "pocketId": pocket_id,
            "page": page,
            "size": size
        }
        
        # Add query parameters to URL
        url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        response = self._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get pocket transactions: {0}").format(response.get("message", "Unknown error")))
    
    def get_merchant_balance_summary(self, pocket_id):
        """Get merchant balance summation across all pockets"""
        bearer_token = self.get_bearer_token()
        
        url = f"{self.pocket_base_url}/pocket/balances-summation/pocket-id/{pocket_id}"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        response = self._make_request("GET", url, headers=headers)
        
        if response.get("responseCode") == "00":
            return response["data"]
        else:
            frappe.throw(_("Failed to get balance summary: {0}").format(response.get("message", "Unknown error")))
    
    def _make_request(self, method, url, headers=None, json_data=None, timeout=30, max_retries=3):
        """Make HTTP request with retry logic"""
        headers = headers or {}
        
        for attempt in range(max_retries):
            try:
                if method.upper() == "GET":
                    response = requests.get(url, headers=headers, timeout=timeout)
                elif method.upper() == "POST":
                    response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
                else:
                    frappe.throw(_("Unsupported HTTP method: {0}").format(method))
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    frappe.log_error(error_msg, "SeerBit API Error")
                    if attempt == max_retries - 1:
                        frappe.throw(_("API request failed: {0}").format(error_msg))
            
            except requests.exceptions.RequestException as e:
                frappe.log_error(f"Request attempt {attempt + 1} failed: {str(e)}", "SeerBit API Network Error")
                if attempt == max_retries - 1:
                    frappe.throw(_("Network error: {0}").format(str(e)))
    
    def _get_default_callback_url(self):
        """Get default callback URL"""
        return get_request_site_address(True) + "/api/method/payments.seerbit_integration.core.webhooks.payment_callback"
    
    def verify_webhook_signature(self, payload, signature):
        """Verify webhook signature for security"""
        webhook_secret = self.settings.get_password("webhook_secret")
        if not webhook_secret:
            frappe.throw(_("Webhook secret not configured"))
        
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)


def get_api_client(settings_doc=None):
    """Factory function to get SeerBit API client"""
    return SeerBitAPIClient(settings_doc)


def get_seerbit_settings():
    """Helper function to get SeerBit Settings document consistently across modules"""
    try:
        # Try to get the specific "Seerbit Gateway" record
        settings = frappe.get_doc("SeerBit Settings", "Seerbit Gateway")
        if not settings:
            frappe.throw(_("SeerBit Settings record 'Seerbit Gateway' not found"))
        return settings
    except frappe.DoesNotExistError:
        # If "Seerbit Gateway" doesn't exist, try to get any active settings
        settings_list = frappe.get_all("SeerBit Settings", 
            filters={"is_active": 1}, 
            limit=1
        )
        if settings_list:
            return frappe.get_doc("SeerBit Settings", settings_list[0].name)
        else:
            frappe.throw(_("No active SeerBit Settings found. Please create a SeerBit Settings record named 'Seerbit Gateway'"))
