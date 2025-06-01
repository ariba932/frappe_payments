import unittest
import frappe
from unittest.mock import patch, Mock


class TestSeerBitOrder(unittest.TestCase):
    
    def setUp(self):
        frappe.set_user("Administrator")
    
    def tearDown(self):
        frappe.db.rollback()
    
    def test_order_autoname(self):
        """Test that order name is set to payment reference"""
        order = frappe.get_doc({
            "doctype": "SeerBit Order",
            "payment_reference": "AUTO_REF_123",
            "amount": 500,
            "currency": "NGN",
            "customer_email": "auto@example.com",
            "customer_name": "Auto Test"
        })
        order.insert()
        
        self.assertEqual(order.name, "AUTO_REF_123")
    
    def test_order_lifecycle_events(self):
        """Test order lifecycle events are triggered"""
        with patch.object(frappe.get_doc("SeerBit Order"), 'run_method') as mock_run_method:
            order = frappe.get_doc({
                "doctype": "SeerBit Order",
                "payment_reference": "LIFECYCLE_123",
                "amount": 750,
                "currency": "NGN",
                "customer_email": "lifecycle@example.com",
                "customer_name": "Lifecycle Test",
                "status": "Pending"
            })
            order.insert()
            
            # Update to Paid status
            order.status = "Paid"
            order.save()
            
            # Verify that on_payment_captured was called
            mock_run_method.assert_called_with("on_payment_captured")


if __name__ == '__main__':
    unittest.main()
