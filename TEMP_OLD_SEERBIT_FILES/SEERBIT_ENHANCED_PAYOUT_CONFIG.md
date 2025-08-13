# SeerBit Enhanced Payout Configuration Guide

## Overview

This guide explains how to configure the SeerBit Enhanced Payout flow in your ERPNext installation after the modular integration updates.

## Required SeerBit Settings Configuration

### 1. Basic Configuration (Existing)
- **Public Key**: Your SeerBit public key
- **Private Key**: Your SeerBit private key (encrypted)
- **Sandbox Mode**: Enable for testing
- **Is Enabled**: Enable SeerBit integration
- **Enable Payouts**: Enable payout functionality

### 2. Enhanced Payout Configuration (New)

Add these new fields to your SeerBit Settings:

```python
# In SeerBit Settings DocType, add these fields:

pocket_email = frappe.Field(
    "Data",
    label="Pocket Email",
    description="Email address for SeerBit pocket authentication"
)

pocket_password = frappe.Field(
    "Password", 
    label="Pocket Password",
    description="Password for SeerBit pocket authentication"
)

pocket_id = frappe.Field(
    "Data",
    label="Pocket ID", 
    description="Your SeerBit Pocket ID (e.g., SBP0017194)"
)

use_enhanced_payouts = frappe.Field(
    "Check",
    label="Use Enhanced Payouts",
    description="Enable enhanced payout flow with OTP and signature",
    default=1
)

enable_account_verification = frappe.Field(
    "Check",
    label="Enable Account Verification",
    description="Verify bank accounts before payouts",
    default=1
)
```

### 3. Getting Your Pocket Credentials

#### Step 1: Get Pocket Access
1. Login to your SeerBit Merchant Dashboard
2. Navigate to the Pocket section
3. Request payout feature activation (requires compliance approval)
4. Once approved, you'll receive pocket credentials

#### Step 2: Find Your Pocket ID
1. Login to the SeerBit Pocket Dashboard
2. Your Pocket ID will be displayed (format: SBP0xxxxxx)
3. Copy this ID to the `pocket_id` field

#### Step 3: Authentication Credentials
- Use the same email and password you use for the Pocket Dashboard
- These are stored securely in ERPNext

## Enhanced Payout Flow

### The Complete Flow
1. **Authentication**: Get Bearer token from `/pocket/authenticate`
2. **Account Verification**: Verify beneficiary account via `/pocket/payout/account-enquiry`
3. **OTP Generation**: Generate OTP via `/pocket/getOtp`
4. **Signature Generation**: Generate signature via `/pocket/payout/get-signature`
5. **Payout Execution**: Execute payout via `/pocket/payout/encrypted/pocket-id/{pocketID}`

### API Endpoints Used
```
Base URL (Production): https://pocket.seerbitapi.com
Base URL (Sandbox): https://sandbox.seerbitapi.com

POST /pocket/authenticate
POST /pocket/payout/account-enquiry
POST /pocket/getOtp
POST /pocket/payout/get-signature
POST /pocket/payout/encrypted/pocket-id/{pocketID}
```

## Testing the Configuration

### 1. Test Authentication
```python
# In ERPNext Console
settings = frappe.get_doc("SeerBit Settings")
from payments.seerbit_integration.core.api_client import get_api_client

client = get_api_client(settings)
token = client.get_bearer_token()
print(f"Bearer Token: {token[:20]}...")
```

### 2. Test Account Verification
```python
# Test account verification
result = client.verify_bank_account("0123456789", "044")
print(f"Verification Result: {result}")
```

### 3. Test OTP Generation
```python
# Test OTP generation
otp_result = client.generate_otp_for_payout()
print(f"OTP: {otp_result.get('otp')}")
```

### 4. Test Wallet Balance
```python
# Test wallet balance
balance = client.get_wallet_balance()
print(f"Balance: {balance}")
```

## Security Considerations

### 1. Credential Storage
- Pocket password is encrypted using Frappe's password field
- Bearer tokens are not stored permanently
- OTPs expire quickly and are never stored

### 2. Error Handling
- Enhanced payout failures fall back to legacy method
- All steps are logged for debugging
- Failed attempts are recorded for audit

### 3. Compliance
- Enhanced payouts require SeerBit compliance approval
- Account verification is mandatory
- Proper audit trail is maintained

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
```
Error: "Failed to authenticate for payout operations"
Solution: Check pocket_email and pocket_password are correct
```

#### 2. Missing Pocket ID
```
Error: "Pocket ID is required"
Solution: Set pocket_id in SeerBit Settings
```

#### 3. OTP Generation Failures
```
Error: "OTP generation failed"
Solution: Ensure compliance approval and correct pocket credentials
```

#### 4. Account Verification Failures
```
Error: "Account verification failed"
Solution: Check bank_code format and account number
```

### Debug Steps

1. **Check Error Logs**
   ```python
   # View recent error logs
   frappe.get_all("Error Log", 
                  filters={"error": ["like", "%SeerBit%"]}, 
                  limit=10, 
                  order_by="creation desc")
   ```

2. **Test Individual Steps**
   - Test authentication separately
   - Verify account verification works
   - Check OTP generation
   - Validate signature creation

3. **Fallback Behavior**
   - Enhanced payout failures automatically fall back to legacy method
   - Check logs to see which method was used

## Migration from Old Implementation

### 1. Update Settings
- Add new pocket configuration fields
- Set `use_enhanced_payouts = 1`
- Test authentication

### 2. Test Existing Payouts
- Run test payouts with enhanced flow
- Verify fallback to legacy works
- Check all payout operations work

### 3. Monitor Performance
- Enhanced flow has more API calls
- Monitor response times
- Check success rates

## Production Deployment

### 1. Pre-Deployment Checklist
- [ ] SeerBit compliance approval received
- [ ] Pocket credentials configured
- [ ] Enhanced flow tested in sandbox
- [ ] Fallback mechanism verified
- [ ] Error logging configured

### 2. Deployment Steps
1. Update SeerBit Settings with pocket configuration
2. Enable enhanced payouts
3. Test with small amounts first
4. Monitor for any issues
5. Full rollout

### 3. Post-Deployment Monitoring
- Monitor payout success rates
- Check error logs regularly
- Verify account verification accuracy
- Ensure compliance requirements met

---

**Note**: Enhanced payouts require SeerBit compliance team approval. Contact SeerBit support to activate this feature for your account before using the enhanced flow in production.
