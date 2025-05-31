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
                frappe.throw(_("Invalid API credentials: {0}").format(str(e)))
    
    def get_encrypted_key(self):
        """Get encrypted key for API authentication"""
        private_key = get_decrypted_password("SeerBit Settings", "SeerBit Settings", "private_key")
        
        if not private_key:
            frappe.throw(_("Private key not found"))
            
        # Prepare the key combination as per SeerBit docs
        key_combination = f"{private_key}.{self.public_key}"
        
        # Get base URL based on sandbox mode
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        
        url = f"{base_url}/api/v2/encrypt/keys"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "key": key_combination
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "SUCCESS":
                return result["data"]["EncryptedSecKey"]["encryptedKey"]
            else:
                frappe.throw(_("Failed to get encrypted key: {0}").format(result.get("message", "Unknown error")))
        else:
            frappe.throw(_("API request failed with status: {0}").format(response.status_code))
    
    def get_payment_url(self, **kwargs):
        """Create payment and return checkout URL"""
        
        # Validate required parameters
        required_params = ["amount", "currency", "email", "fullName", "paymentReference", "callbackUrl"]
        for param in required_params:
            if not kwargs.get(param):
                frappe.throw(_("Missing required parameter: {0}").format(param))
        
        # Get encrypted key for authorization
        encrypted_key = self.get_encrypted_key()
        
        # Get base URL
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        
        url = f"{base_url}/api/v2/payments"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {encrypted_key}"
        }
        
        # Prepare payment data
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
        
        # Add optional parameters
        if kwargs.get("productId"):
            payment_data["productId"] = kwargs["productId"]
        if kwargs.get("productDescription"):
            payment_data["productDescription"] = kwargs["productDescription"]
        
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
                frappe.throw(_("Payment creation failed: {0}").format(result.get("message", "Unknown error")))
        else:
            frappe.throw(_("Payment API request failed with status: {0}").format(response.status_code))
    
    def verify_payment(self, payment_reference):
        """Verify payment status"""
        encrypted_key = self.get_encrypted_key()
        
        # Get base URL
        base_url = "https://seerbitapi.com" if not self.sandbox_mode else "https://sandbox.seerbitapi.com"
        
        url = f"{base_url}/api/v3/payments/query/{payment_reference}"
        headers = {
            "Authorization": f"Bearer {encrypted_key}"
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "SUCCESS":
                return result["data"]
            else:
                frappe.throw(_("Payment verification failed: {0}").format(result.get("message", "Unknown error")))
        else:
            frappe.throw(_("Verification API request failed with status: {0}").format(response.status_code))
