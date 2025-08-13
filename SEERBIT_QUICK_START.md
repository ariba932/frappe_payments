# 🚀 SeerBit ERPNext Quick Start Guide

> **Get Started with SeerBit Integration in 15 Minutes**  
> *Step-by-step setup and first transactions*

---

## 🎯 Quick Navigation
- [⚡ 5-Minute Setup](#-5-minute-setup)
- [💰 First Payment Collection](#-first-payment-collection-sales)
- [💸 First Payout](#-first-payout-purchase)
- [👥 First Salary Payment](#-first-salary-payment)
- [✅ Verification Checklist](#-verification-checklist)

---

## ⚡ 5-Minute Setup

### **Step 1: Access SeerBit Operations (30 seconds)**
```
1. Login to ERPNext
2. Navigate: Home → Search "SeerBit" → Click "SeerBit Operations"
3. Click "SeerBit Settings"
```

### **Step 2: Configure API Credentials (2 minutes)**
```
✅ Public Key: SBPUBK_[your_public_key]
✅ Secret Key: [your_secret_key] 
✅ Environment: Sandbox (for testing) / Live (for production)
✅ Base URL: Auto-filled based on environment
✅ Default Currency: NGN
✅ Save Settings
```

### **Step 3: Set Default Accounts (2 minutes)**
```
✅ Default Cash Account: Select your main cash account
✅ Default Bank Account: Select your primary bank account  
✅ Fee Account: Select account for transaction fees
✅ Save Configuration
```

### **Step 4: Configure Webhook (30 seconds)**
```
✅ Webhook URL: https://[your-site].com/api/method/payments.seerbit_integration.webhook.handle_webhook
✅ Webhook Secret: Generate and copy to SeerBit dashboard
✅ Test webhook connection
```

**🎉 Setup Complete!** Total time: ~5 minutes

---

## 💰 First Payment Collection (Sales)

### **Scenario: Collect ₦50,000 from Customer for Sales Invoice**

#### **Step 1: Create Sales Invoice (2 minutes)**
```
Navigation: Home → Selling → Sales Invoice → New

📝 Fill Details:
✅ Customer: Select existing customer or create new
✅ Items: Add products/services
✅ Grand Total: ₦50,000
✅ Enable SeerBit Payment: ☑️ Check this box
✅ Submit Invoice
```

#### **Step 2: Generate Payment Link (1 minute)**
```
After submission:
✅ Click "Create SeerBit Payment Link" button
✅ System creates SeerBit Payment Request automatically
✅ Payment link appears in "Payment Link" field
✅ Copy link: https://checkout.seerbit.com/[unique_id]
```

#### **Step 3: Share & Test Payment (2 minutes)**
```
✅ Share link with customer (email/WhatsApp/SMS)
✅ Customer clicks link → redirected to SeerBit checkout
✅ Customer enters card details and pays
✅ Payment status updates automatically in ERPNext
```

#### **Step 4: Verify Payment Received (30 seconds)**
```
Check Results:
✅ Sales Invoice status: "Paid"
✅ Payment Entry: Auto-created
✅ SeerBit Transaction Log: Success entry
✅ Bank account: Balance updated
```

**💡 Pro Tip:** Use Sandbox environment for testing with test card: `4111111111111111`

---

## 💸 First Payout (Purchase)

### **Scenario: Pay ₦30,000 to Supplier for Purchase Invoice**

#### **Step 1: Setup Supplier Bank Details (2 minutes)**
```
Navigation: Home → Buying → Supplier → [Select Supplier]

📝 Add Bank Details:
✅ Go to "SeerBit Bank Details" section
✅ Bank Code: 044 (Access Bank example)
✅ Account Number: 0123456789
✅ Account Name: Supplier Company Ltd
✅ Click "Verify Account" button
✅ System validates with SeerBit
✅ Account Verified: ☑️ Shows as verified
✅ Save Supplier
```

#### **Step 2: Create Purchase Invoice (2 minutes)**
```
Navigation: Home → Buying → Purchase Invoice → New

📝 Fill Details:
✅ Supplier: Select supplier with verified bank details
✅ Items: Add purchased items
✅ Grand Total: ₦30,000
✅ Enable SeerBit Payout: ☑️ Check this box
✅ Auto Create Payout Request: ☑️ Optional auto-creation
✅ Submit Invoice
```

#### **Step 3: Process Payout (1 minute)**
```
Option A - Auto Payout (if enabled):
✅ Payout request created automatically
✅ Requires approval if workflow enabled

Option B - Manual Payout:
✅ Go to: SeerBit Operations → SeerBit Payout Request → New
✅ Purchase Invoice: Select submitted invoice
✅ Supplier: Auto-filled
✅ Amount: ₦30,000
✅ Bank Details: Auto-populated from supplier
✅ Submit to initiate payout
```

#### **Step 4: Monitor Payout Status (1 minute)**
```
✅ Payout Status: "Processing" → "Completed"
✅ Payment Entry: Auto-created
✅ Supplier Account: Balance updated
✅ SeerBit Transaction Log: Success entry
```

**⚠️ Important:** Ensure sufficient balance in SeerBit pocket before payout!

---

## 👥 First Salary Payment

### **Scenario: Pay ₦100,000 salary to Employee**

#### **Step 1: Setup Employee for SeerBit (2 minutes)**
```
Navigation: Home → Human Resources → Employee → [Select Employee]

📝 Configure SeerBit:
✅ Go to "SeerBit Payment Configuration" section
✅ Enable SeerBit Payouts: ☑️ Check this box
✅ SeerBit Bank Code: 044 (employee's bank code)
✅ Default Payout Currency: NGN
✅ Save Employee
```

#### **Step 2: Create Salary Slip (3 minutes)**
```
Navigation: Home → Payroll → Salary Slip → New

📝 Process Salary:
✅ Employee: Select SeerBit-enabled employee
✅ Posting Date: Current month
✅ Click "Get Emp Details" to load salary structure
✅ Review earnings and deductions
✅ Net Pay: ₦100,000
✅ Process via SeerBit: ☑️ Check this box
✅ Submit Salary Slip
```

#### **Step 3: Create SeerBit Salary Payout (2 minutes)**
```
Navigation: Home → SeerBit Operations → SeerBit Salary Payout → New

📝 Payout Details:
✅ Payout Type: "Salary"
✅ Employee: Select employee
✅ Salary Slip: Select submitted salary slip
✅ Bank Details: Auto-populated from employee
✅ Amount: ₦100,000 (from salary slip)
✅ Currency: NGN
✅ Submit to process payout
```

#### **Step 4: Verify Salary Payment (1 minute)**
```
✅ Payout Status: "Processing" → "Completed"
✅ Employee receives SMS notification
✅ Payment Entry: Auto-created
✅ Salary Slip: Status updated to "Paid via SeerBit"
✅ Employee record: Last payout date updated
```

**📊 Track Results:**
- Employee → Last SeerBit Payout Date: Today
- Employee → Total SeerBit Payouts: ₦100,000
- SeerBit Transaction Log: Complete audit trail

---

## ✅ Verification Checklist

### **🔧 Setup Verification**
- [ ] SeerBit Settings configured with valid credentials
- [ ] Default accounts set for cash, bank, and fees
- [ ] Webhook URL configured and responding
- [ ] Test environment working (Sandbox)

### **💰 Payment Collection Verification**
- [ ] Sales Invoice can create payment links
- [ ] Customers can complete payments via SeerBit
- [ ] Payment status updates automatically
- [ ] Payment Entries created correctly
- [ ] Bank reconciliation working

### **💸 Payout Verification**
- [ ] Supplier bank accounts verified successfully
- [ ] Purchase invoices can trigger payouts
- [ ] Payout processing completes successfully
- [ ] Payment Entries created for payouts
- [ ] Supplier accounts updated correctly

### **👥 Payroll Verification**
- [ ] Employee bank details configured
- [ ] Salary slips can be processed via SeerBit
- [ ] Employee payouts complete successfully
- [ ] Salary status tracking working
- [ ] Employee advance payments functional

### **📊 Monitoring Verification**
- [ ] SeerBit Transaction Log capturing all activities
- [ ] Webhook notifications being received
- [ ] Error logging and handling functional
- [ ] Reporting and dashboard data accurate

---

## 🆘 Quick Troubleshooting

### **❌ Payment Link Not Generated**
```
Check:
1. SeerBit Settings → API credentials valid?
2. Sales Invoice → "Enable SeerBit Payment" checked?
3. Internet connection working?
4. SeerBit API status (check their status page)
```

### **❌ Payout Failed**
```
Check:
1. Supplier bank details verified?
2. Sufficient balance in SeerBit pocket?
3. Bank code format correct (3 digits)?
4. Account number format correct?
```

### **❌ Webhook Not Working**
```
Check:
1. Webhook URL accessible from internet?
2. SSL certificate valid (HTTPS required)?
3. Webhook secret matches SeerBit dashboard?
4. No firewall blocking SeerBit IPs?
```

### **❌ Employee Payout Issues**
```
Check:
1. Employee "Enable SeerBit Payouts" checked?
2. Employee bank code configured?
3. Salary slip submitted before payout creation?
4. SeerBit pocket has sufficient balance?
```

---

## 📞 Support Contacts

### **Technical Issues**
- **ERPNext Integration**: Check error logs in SeerBit Transaction Log
- **API Issues**: Contact SeerBit support with transaction reference
- **Webhook Problems**: Verify URL accessibility and SSL

### **Business Issues**  
- **Payment Disputes**: Use SeerBit dashboard for customer support
- **Settlement Delays**: Check SeerBit merchant dashboard
- **Account Issues**: Contact your SeerBit account manager

---

## 🎯 Next Steps

### **After Setup:**
1. **Test All Flows**: Run through each scenario with small amounts
2. **Train Users**: Share this guide with relevant team members
3. **Set Limits**: Configure transaction limits and approval workflows
4. **Monitor Daily**: Check SeerBit Transaction Log regularly
5. **Scale Up**: Gradually increase transaction volumes

### **Advanced Features:**
- [ ] Setup department-wise pockets
- [ ] Configure bulk salary processing
- [ ] Implement automated reconciliation
- [ ] Create custom reports and dashboards
- [ ] Setup automated notifications

---

**🚀 You're ready to process payments with SeerBit! Start with small test transactions and scale up as you get comfortable with the system.**

---

*📧 Questions? Contact your system administrator or refer to the complete SeerBit User Guide for detailed information.*
