// SeerBit Payout Integration for Payment Entry
frappe.ui.form.on('Payment Entry', {
    refresh: function(frm) {
        // Add SeerBit payout button for supplier payments
        if (frm.doc.docstatus === 1 && frm.doc.payment_type === 'Pay' && 
            frm.doc.party_type === 'Supplier' && !frm.doc.seerbit_payout_reference &&
            frappe.user.has_role(['Accounts Manager', 'Finance Manager'])) {
            
            // Check if supplier has SeerBit enabled
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Supplier',
                    filters: {'name': frm.doc.party},
                    fieldname: 'seerbit_payout_enabled'
                },
                callback: function(r) {
                    if (r.message && r.message.seerbit_payout_enabled) {
                        frm.add_custom_button(__('Initiate SeerBit Payout'), function() {
                            initiate_supplier_payout(frm);
                        }, __('Actions'));
                    }
                }
            });
        }
        
        // Show payout status if SeerBit payout exists
        if (frm.doc.seerbit_payout_reference) {
            frm.add_custom_button(__('Check Payout Status'), function() {
                check_payout_status(frm);
            }, __('SeerBit'));
        }
    }
});

function initiate_supplier_payout(frm) {
    frappe.confirm(
        __('Are you sure you want to initiate SeerBit payout of {0} to {1}?', 
           [format_currency(frm.doc.paid_amount, frm.doc.paid_to_account_currency), frm.doc.party]),
        function() {
            frappe.call({
                method: 'payments.payment_gateways.doctype.seerbit_payout.seerbit_payout.initiate_supplier_payout',
                args: {
                    'payment_entry_name': frm.doc.name
                },
                freeze: true,
                freeze_message: __('Initiating payout...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frm.set_value('seerbit_payout_reference', r.message.payout_reference);
                        frm.set_value('seerbit_payout_status', 'Processing');
                        frm.save();
                        
                        frappe.msgprint({
                            title: __('Payout Initiated'),
                            message: __('SeerBit payout has been initiated. Reference: {0}', [r.message.payout_reference]),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    );
}

function check_payout_status(frm) {
    frappe.call({
        method: 'payments.payment_gateways.doctype.seerbit_settings.seerbit_settings.verify_payout',
        args: {
            'payout_reference': frm.doc.seerbit_payout_reference
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('seerbit_payout_status', r.message.status);
                frm.save();
                
                frappe.msgprint({
                    title: __('Payout Status'),
                    message: __('Status: {0}<br>Amount: {1}', [r.message.status, r.message.amount]),
                    indicator: r.message.status === 'Paid' ? 'green' : 'orange'
                });
            }
        }
    });
}
