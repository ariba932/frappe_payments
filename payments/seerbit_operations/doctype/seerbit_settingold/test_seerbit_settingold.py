# -*- coding: utf-8 -*-
# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest
import frappe

class TestSeerBitSettingold(unittest.TestCase):
	"""Test cases for SeerBit Settings"""
	
	def setUp(self):
		"""Set up test environment"""
		# Clean up any existing test settings
		if frappe.db.exists("SeerBit Settings", "Test Settings"):
			frappe.delete_doc("SeerBit Settings", "Test Settings", force=True)
	
	def test_create_settings(self):
		"""Test creating SeerBit settings"""
		settings = frappe.new_doc("SeerBit Settings")
		settings.settings_name = "Test Settings"
		settings.environment = "Sandbox"
		settings.public_key = "test_public_key"
		settings.secret_key = "test_secret_key"
		settings.is_active = 1
		
		settings.save()
		
		self.assertEqual(settings.settings_name, "Test Settings")
		self.assertEqual(settings.environment, "Sandbox")
		self.assertTrue(settings.is_active)
	
	def test_validation_missing_credentials(self):
		"""Test validation with missing credentials"""
		settings = frappe.new_doc("SeerBit Settings")
		settings.settings_name = "Test Settings"
		settings.environment = "Sandbox"
		
		with self.assertRaises(frappe.ValidationError):
			settings.save()
	
	def test_validation_webhook_config(self):
		"""Test webhook configuration validation"""
		settings = frappe.new_doc("SeerBit Settings")
		settings.settings_name = "Test Settings"
		settings.environment = "Sandbox"
		settings.public_key = "test_public_key"
		settings.secret_key = "test_secret_key"
		settings.enable_webhooks = 1
		settings.webhook_url = "invalid_url"
		
		with self.assertRaises(frappe.ValidationError):
			settings.save()
	
	def test_get_api_credentials(self):
		"""Test getting API credentials"""
		settings = frappe.new_doc("SeerBit Settings")
		settings.settings_name = "Test Settings"
		settings.environment = "Sandbox"
		settings.public_key = "test_public_key"
		settings.secret_key = "test_secret_key"
		settings.api_base_url = "https://test.seerbit.com"
		settings.timeout = 60
		settings.save()
		
		credentials = settings.get_api_credentials()
		
		self.assertEqual(credentials['public_key'], "test_public_key")
		self.assertEqual(credentials['environment'], "Sandbox")
		self.assertEqual(credentials['api_base_url'], "https://test.seerbit.com")
		self.assertEqual(credentials['timeout'], 60)
	
	def test_payout_limits_validation(self):
		"""Test payout limits validation"""
		settings = frappe.new_doc("SeerBit Settings")
		settings.settings_name = "Test Settings"
		settings.environment = "Sandbox"
		settings.public_key = "test_public_key"
		settings.secret_key = "test_secret_key"
		settings.payout_daily_limit = 1000000
		settings.payout_monthly_limit = 500000  # Monthly less than daily
		
		with self.assertRaises(frappe.ValidationError):
			settings.save()
	
	def tearDown(self):
		"""Clean up after tests"""
		if frappe.db.exists("SeerBit Settings", "Test Settings"):
			frappe.delete_doc("SeerBit Settings", "Test Settings", force=True)
