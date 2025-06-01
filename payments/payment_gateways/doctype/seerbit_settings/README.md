# SeerBit Payment Gateway Integration

## Overview

This integration allows Frappe applications to accept payments through SeerBit's payment gateway. SeerBit supports multiple payment methods including cards, bank transfers, and mobile money across African markets.

## Features

- Standard checkout integration
- Webhook support for real-time payment notifications
- Payment verification
- Support for multiple currencies (NGN, USD, GBP, EUR)
- Sandbox and live mode support
- Automatic payment status updates
- Comprehensive logging and error handling

## Installation

1. **Install the payments app** (if not already installed):
   ```bash
   bench get-app payments
   bench --site [site-name] install-app payments
