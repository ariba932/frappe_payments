# -*- coding: utf-8 -*-
# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class SeerBitSettingold(Document):
	"""SeerBit Settings - Single DocType for configuring SeerBit integration"""
	
	def validate(self):
		"""Validate SeerBit settings"""
		self.validate_api_credentials()
		self.validate_webhook_config()
		self.validate_payout_limits()
	
	def validate_api_credentials(self):
		"""Validate API credentials are provided"""
		if not self.public_key:
			frappe.throw("Public Key is required")
		
		if not self.secret_key:
			frappe.throw("Secret Key is required")
		
		if self.environment == "Production" and not self.merchant_id:
			frappe.throw("Merchant ID is required for Production environment")
	
	def validate_webhook_config(self):
		"""Validate webhook configuration"""
		if self.enable_webhooks and not self.webhook_url:
			frappe.throw("Webhook URL is required when webhooks are enabled")
		
		if self.webhook_url and not self.webhook_url.startswith(('http://', 'https://')):
			frappe.throw("Webhook URL must start with http:// or https://")
	
	def validate_payout_limits(self):
		"""Validate payout limits"""
		if self.payout_daily_limit and self.payout_monthly_limit:
			if self.payout_daily_limit > self.payout_monthly_limit:
				frappe.throw("Daily payout limit cannot exceed monthly limit")
	
	def get_api_credentials(self):
		"""Get API credentials for SeerBit integration"""
		return {
			'public_key': self.public_key,
			'secret_key': self.get_password('secret_key'),
			'environment': self.environment,
			'api_base_url': self.api_base_url or 'https://seerbitapi.com',
			'timeout': self.timeout or 30
		}
	
	def get_payout_config(self):
		"""Get payout configuration"""
		return {
			'enable_payouts': self.enable_payouts,
			'auto_process_approved_payouts': self.auto_process_approved_payouts,
			'require_otp_for_payouts': self.require_otp_for_payouts,
			'default_currency': self.default_payout_currency or 'NGN',
			'daily_limit': self.payout_daily_limit,
			'monthly_limit': self.payout_monthly_limit,
			'enable_notifications': self.enable_payout_notifications
		}
	
	def get_webhook_config(self):
		"""Get webhook configuration"""
		webhook_events = []
		if self.webhook_events:
			try:
				import json
				webhook_events = json.loads(self.webhook_events)
			except:
				webhook_events = []
		
		return {
			'enable_webhooks': self.enable_webhooks,
			'webhook_url': self.webhook_url,
			'webhook_secret': self.get_password('webhook_secret'),
			'webhook_events': webhook_events
		}
	
	def test_api_connection(self):
		"""Test API connection with current settings"""
		try:
			# Import SeerBit API client
			from payments.seerbit_integration.core.client import SeerBitClient
			
			credentials = self.get_api_credentials()
			client = SeerBitClient(
				public_key=credentials['public_key'],
				secret_key=credentials['secret_key'],
				environment=credentials['environment']
			)
			
			# Test connection with a simple API call
			response = client.test_connection()
			
			if response.get('status') == 'success':
				frappe.msgprint("API connection test successful!", alert=True)
				self.last_sync = frappe.utils.now()
				self.save(ignore_permissions=True)
				return True
			else:
				frappe.throw("API connection test failed: " + response.get('message', 'Unknown error'))
		
		except Exception as e:
			frappe.throw("API connection test failed: " + str(e))
	
	@frappe.whitelist()
	def sync_pockets(self):
		"""Sync pockets from SeerBit API"""
		try:
			from payments.seerbit_integration.pocket.client import PocketClient
			
			credentials = self.get_api_credentials()
			pocket_client = PocketClient(
				public_key=credentials['public_key'],
				secret_key=credentials['secret_key'],
				environment=credentials['environment']
			)
			
			# Get pockets from API
			pockets_response = pocket_client.get_pockets()
			
			if pockets_response.get('status') == 'success':
				pockets = pockets_response.get('data', [])
				
				# Sync with ERPNext
				for pocket_data in pockets:
					self.sync_pocket_to_erpnext(pocket_data)
				
				frappe.msgprint(f"Successfully synced {len(pockets)} pockets", alert=True)
				self.last_sync = frappe.utils.now()
				self.save(ignore_permissions=True)
			else:
				frappe.throw("Failed to sync pockets: " + pockets_response.get('message', 'Unknown error'))
		
		except Exception as e:
			frappe.throw("Pocket sync failed: " + str(e))
	
	def sync_pocket_to_erpnext(self, pocket_data):
		"""Sync individual pocket to ERPNext"""
		pocket_id = pocket_data.get('pocketId')
		
		if not pocket_id:
			return
		
		# Check if pocket exists
		existing_pocket = frappe.db.exists("SeerBit Pocket", {"pocket_id": pocket_id})
		
		if existing_pocket:
			# Update existing pocket
			pocket_doc = frappe.get_doc("SeerBit Pocket", existing_pocket)
		else:
			# Create new pocket
			pocket_doc = frappe.new_doc("SeerBit Pocket")
			pocket_doc.pocket_id = pocket_id
		
		# Update pocket data
		pocket_doc.pocket_name = pocket_data.get('pocketName', '')
		pocket_doc.currency = pocket_data.get('currency', 'NGN')
		pocket_doc.available_balance = pocket_data.get('availableBalance', 0)
		pocket_doc.ledger_balance = pocket_data.get('ledgerBalance', 0)
		pocket_doc.is_active = pocket_data.get('status', '').lower() == 'active'
		pocket_doc.description = pocket_data.get('description', '')
		
		pocket_doc.save(ignore_permissions=True)

@frappe.whitelist()
def get_seerbit_settingold():
	"""Get SeerBit settings for API calls"""
	settings = frappe.get_single("SeerBit Settings")
	if not settings.is_active:
		frappe.throw("SeerBit integration is not active")
	
	return settings

@frappe.whitelist()
def test_api_connection():
	"""Test API connection endpoint"""
	settings = frappe.get_single("SeerBit Settings")
	return settings.test_api_connection()

@frappe.whitelist()
def sync_pockets():
	"""Sync pockets endpoint"""
	settings = frappe.get_single("SeerBit Settings")
	return settings.sync_pockets()
