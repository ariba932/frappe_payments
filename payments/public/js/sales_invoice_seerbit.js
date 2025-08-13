// SeerBit Payment Integration for Sales Invoice
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Add SeerBit payment button for submitted invoices
        if (frm.doc.docstatus === 1 && frm.doc.outstanding_amount > 0 && 
            frappe.user.has_role(['Accounts Manager', 'Accounts User'])) {
            
            // Check if SeerBit is enabled
            frappe.call({
                method: 'payments.payment_gateways.doctype.seerbit_settings.seerbit_settings.is_seerbit_enabled',
                callback: function(r) {
                    if (r.message) {
                        frm.add_custom_button(__('Create Payment Link'), function() {
                            create_seerbit_payment_link(frm);
                        }, __('SeerBit'));
                        
                        frm.add_custom_button(__('Send Payment Link'), function() {
                            send_payment_link_email(frm);
                        }, __('SeerBit'));
                    }
                }
            });
        }
        
        // Show payment status if SeerBit payment exists
        if (frm.doc.seerbit_payment_reference) {
            frm.add_custom_button(__('Check Payment Status'), function() {
                check_payment_status(frm);
            }, __('SeerBit'));
        }
    }
});

function create_seerbit_payment_link(frm) {
    frappe.call({
        method: 'payments.payment_gateways.seerbit_api.create_invoice_payment_link',
        args: {
            'invoice_name': frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.redirect_url) {
                frappe.msgprint({
                    title: __('Payment Link Created'),
                    message: __('Payment link: <a href="{0}" target="_blank">{0}</a>', [r.message.redirect_url]),
                    indicator: 'green'
                });
                
                // Update invoice with payment reference
                frm.set_value('seerbit_payment_reference', r.message.payment_reference);
                frm.save();
            }
        }
    });
}

function send_payment_link_email(frm) {
    if (!frm.doc.contact_email) {
        frappe.msgprint(__('Customer email not found'));
        return;
    }
    
    frappe.call({
        method: 'payments.payment_gateways.seerbit_api.send_payment_link_email',
        args: {
            'invoice_name': frm.doc.name,
            'customer_email': frm.doc.contact_email
        },
        callback: function(r) {
            if (r.message) {
                frappe.msgprint(__('Payment link sent successfully'));
            }
        }
    });
}

function check_payment_status(frm) {
    frappe.call({
        method: 'payments.payment_gateways.doctype.seerbit_settings.seerbit_settings.verify_payment',
        args: {
            'payment_reference': frm.doc.seerbit_payment_reference
        },
        callback: function(r) {
            if (r.message) {
                frappe.msgprint({
                    title: __('Payment Status'),
                    message: __('Status: {0}<br>Amount: {1}', [r.message.status, r.message.amount]),
                    indicator: r.message.status === 'Paid' ? 'green' : 'orange'
                });
            }
        }
    });
}
