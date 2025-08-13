// SeerBit Sales Invoice Integration
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Add SeerBit payment button
        if (frm.doc.docstatus === 1 && frm.doc.outstanding_amount > 0) {
            frm.add_custom_button(__('Create SeerBit Payment Request'), function() {
                create_seerbit_payment_request(frm);
            }, __('SeerBit'));
            
            // Show payment link if exists
            if (frm.doc.seerbit_payment_request) {
                frm.add_custom_button(__('View Payment Request'), function() {
                    frappe.set_route('Form', 'SeerBit Payment Request', frm.doc.seerbit_payment_request);
                }, __('SeerBit'));
                
                frm.add_custom_button(__('Verify Payment'), function() {
                    verify_seerbit_payment(frm);
                }, __('SeerBit'));
            }
        }
        
        // Add SeerBit status indicator
        if (frm.doc.enable_seerbit_payment && frm.doc.seerbit_payment_status) {
            let status_color = get_payment_status_color(frm.doc.seerbit_payment_status);
            frm.dashboard.add_indicator(__('SeerBit Payment: {0}', [frm.doc.seerbit_payment_status]), status_color);
        }
    },
    
    enable_seerbit_payment: function(frm) {
        if (frm.doc.enable_seerbit_payment && frm.doc.docstatus === 1 && !frm.doc.seerbit_payment_request) {
            frappe.msgprint(__('Save the document and use "Create SeerBit Payment Request" button to generate payment link.'));
        }
    }
});

function create_seerbit_payment_request(frm) {
    frappe.call({
        method: 'payments.seerbit_operations.utils.integration_utils.create_payment_request_from_sales_invoice',
        args: {
            sales_invoice: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.msgprint(__('Payment request created successfully: {0}', [r.message.payment_request]));
                frm.reload_doc();
            } else {
                frappe.msgprint(__('Error: {0}', [r.message ? r.message.message : 'Unknown error']));
            }
        }
    });
}

function verify_seerbit_payment(frm) {
    if (!frm.doc.seerbit_payment_request) {
        frappe.msgprint(__('No payment request found'));
        return;
    }
    
    frappe.call({
        method: 'payments.seerbit_operations.doctype.seerbit_payment_request.seerbit_payment_request.verify_payment',
        args: {
            payment_request: frm.doc.seerbit_payment_request
        },
        callback: function(r) {
            if (r.message) {
                frappe.msgprint(__('Payment verification completed'));
                frm.reload_doc();
            }
        }
    });
}

function get_payment_status_color(status) {
    const status_colors = {
        'Not Initiated': 'grey',
        'Link Created': 'blue',
        'Pending': 'orange',
        'Paid': 'green',
        'Failed': 'red'
    };
    return status_colors[status] || 'grey';
}
