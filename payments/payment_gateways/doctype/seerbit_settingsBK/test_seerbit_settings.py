#Seerbit unit tests
# -*- coding: utf-8 -*-
import unittest
import frappe
from frappe.test_runner import make_test_records
from unittest.mock import patch, Mock


class TestSeerbitSettings(unittest.TestCase):
    
    def setUp(self):
        """Set up test data"""
        frappe.set_user("Administrator")
        
        # Create test SeerBit Settings
        if not frappe.db.exists("SeerBit Settings", "SeerBit Settings"):
            doc = frappe.get_doc({
                "doctype": "SeerBit Settings",
                "is_enabled": 1,
                "sandbox_mode": 1,
                "public_key": "SBTESTPUBK_test123",
                "private_key": "SBTEST_secret123",
                "webhook_secret": "webhook_secret_123"
            })
            doc.insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    @patch('requests.post')
    def test_get_encrypted_key_success(self, mock_post):
        """Test successful encrypted key generation"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "data": {
                "EncryptedSecKey": {
                    "encryptedKey": "test_encrypted_key_123"
                }
            }
        }
        mock_post.return_value = mock_response
        
        settings = frappe.get_doc("SeerBit Settings")
        encrypted_key = settings.get_encrypted_key()
        
        self.assertEqual(encrypted_key, "test_encrypted_key_123")
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_get_encrypted_key_failure(self, mock_post):
        """Test encrypted key generation failure"""
        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        settings = frappe.get_doc("SeerBit Settings")
        
        with self.assertRaises(frappe.ValidationError):
            settings.get_encrypted_key()
    
    @patch('payments.payment_gateways.doctype.seerbit_settings.seerbit_settings.SeerbitSettings.get_encrypted_key')
    @patch('requests.post')
    def test_get_payment_url_success(self, mock_post, mock_encrypted_key):
        """Test successful payment URL generation"""
        # Mock encrypted key
        mock_encrypted_key.return_value = "test_encrypted_key"
        
        # Mock payment creation response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "data": {
                "payments": {
                    "redirectLink": "https://checkout.seerbitapi.com/#/?test=123",
                    "paymentStatus": "08"
                }
            }
        }
        mock_post.return_value = mock_response
        
        settings = frappe.get_doc("SeerBit Settings")
        result = settings.get_payment_url(
            amount=1000,
            currency="NGN",
            email="test@example.com",
            fullName="Test User",
            paymentReference="TEST123",
            callbackUrl="https://example.com/callback"
        )
        
        self.assertEqual(result["redirect_url"], "https://checkout.seerbitapi.com/#/?test=123")
        self.assertEqual(result["reference"], "TEST123")
    
    def test_validate_required_parameters(self):
        """Test validation of required parameters"""
        settings = frappe.get_doc("SeerBit Settings")
        
        with self.assertRaises(frappe.ValidationError):
            settings.get_payment_url(
                amount=1000,
                currency="NGN",
                # Missing required parameters
            )


class TestSeerBitOrder(unittest.TestCase):
    
    def setUp(self):
        """Set up test data"""
        frappe.set_user("Administrator")
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_order_creation(self):
        """Test SeerBit Order creation"""
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": "TEST_REF_123",
            "amount": 1000,
            "currency": "NGN",
            "customer_email": "test@example.com",
            "customer_name": "Test Customer",
            "status": "Pending"
        })
        order.insert()
        
        self.assertEqual(order.payment_reference, "TEST_REF_123")
        self.assertEqual(order.status, "Pending")
        self.assertIsNotNone(order.created_at)
    
    def test_status_change_handling(self):
        """Test order status change handling"""
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": "TEST_REF_456",
            "amount": 1000,
            "currency": "NGN",
            "customer_email": "test@example.com",
            "customer_name": "Test Customer",
            "status": "Pending"
        })
        order.insert()
        
        # Change status to Paid
        order.status = "Paid"
        order.gateway_code = "00"
        order.gateway_message = "Successful"
        order.save()
        
        self.assertEqual(order.status, "Paid")
        self.assertIsNotNone(order.updated_at)
    
    def test_webhook_data_update(self):
        """Test updating order from webhook data"""
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": "TEST_REF_789",
            "amount": 1000,
            "currency": "NGN",
            "customer_email": "test@example.com",
            "customer_name": "Test Customer",
            "status": "Pending"
        })
        order.insert()
        
        # Mock webhook data
        webhook_data = {
            "data": {
                "gatewayReference": "SEER123456",
                "gatewayMessage": "Successful",
                "gatewayCode": "00",
                "paymentType": "CARD",
                "channelType": "VISA"
            }
        }
        
        order.update_from_webhook_data(webhook_data)
        
        self.assertEqual(order.gateway_reference, "SEER123456")
        self.assertEqual(order.gateway_message, "Successful")
        self.assertEqual(order.status, "Paid")


if __name__ == '__main__':
    unittest.main()
