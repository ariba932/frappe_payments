// SeerBit Purchase Invoice Integration
frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {
        // Add SeerBit payout button
        if (frm.doc.docstatus === 1 && frm.doc.outstanding_amount > 0) {
            frm.add_custom_button(__('Create SeerBit Payout Request'), function() {
                create_seerbit_payout_request(frm);
            }, __('SeerBit'));
            
            // Show payout request if exists
            if (frm.doc.seerbit_payout_request) {
                frm.add_custom_button(__('View Payout Request'), function() {
                    frappe.set_route('Form', 'SeerBit Payout Request', frm.doc.seerbit_payout_request);
                }, __('SeerBit'));
            }
        }
        
        // Verify supplier bank details
        if (frm.doc.supplier) {
            frm.add_custom_button(__('Verify Supplier Bank'), function() {
                verify_supplier_bank_account(frm);
            }, __('SeerBit'));
        }
    },
    
    supplier: function(frm) {
        if (frm.doc.supplier) {
            // Load supplier bank details
            frappe.db.get_doc('Supplier', frm.doc.supplier).then(supplier => {
                if (supplier.bank_code && supplier.account_number) {
                    frm.set_df_property('enable_seerbit_payout', 'hidden', 0);
                } else {
                    frm.set_df_property('enable_seerbit_payout', 'hidden', 1);
                    frappe.msgprint(__('Please update supplier bank details to enable SeerBit payout'));
                }
            });
        }
    }
});

function create_seerbit_payout_request(frm) {
    frappe.call({
        method: 'payments.seerbit_operations.utils.integration_utils.create_payout_request_from_purchase_invoice',
        args: {
            purchase_invoice: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.msgprint(__('Payout request created successfully: {0}', [r.message.payout_request]));
                frm.reload_doc();
            } else {
                frappe.msgprint(__('Error: {0}', [r.message ? r.message.message : 'Unknown error']));
            }
        }
    });
}

function verify_supplier_bank_account(frm) {
    frappe.call({
        method: 'payments.seerbit_operations.utils.integration_utils.verify_supplier_bank_account',
        args: {
            supplier: frm.doc.supplier
        },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.msgprint(__('Bank account verified: {0}', [r.message.account_name]));
            } else {
                frappe.msgprint(__('Verification failed: {0}', [r.message ? r.message.message : 'Unknown error']));
            }
        }
    });
}
