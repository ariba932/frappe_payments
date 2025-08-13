// Enhanced SeerBit Payment Integration for Sales Invoice
// Following SeerBit Standard Checkout best practices

frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Enhanced SeerBit payment integration for submitted invoices
        if (frm.doc.docstatus === 1 && frm.doc.outstanding_amount > 0) {
            add_seerbit_payment_buttons(frm);
        }
        
        // Show payment status and actions if SeerBit payment exists
        if (frm.doc.seerbit_payment_reference) {
            add_seerbit_status_buttons(frm);
        }
        
        // Add payment status indicator
        show_payment_status_indicator(frm);
    },
    
    seerbit_payment_reference: function(frm) {
        // Auto-refresh status when payment reference is set
        if (frm.doc.seerbit_payment_reference) {
            setTimeout(() => {
                check_payment_status_enhanced(frm);
            }, 2000);
        }
    }
});

function add_seerbit_payment_buttons(frm) {
    // Check if SeerBit is enabled
    frappe.call({
        method: 'frappe.client.get_single',
        args: {
            doctype: 'SeerBit Settings'
        },
        callback: function(r) {
            if (r.message && r.message.is_enabled) {
                // Primary payment button
                frm.add_custom_button(__('Create Payment Request'), function() {
                    create_payment_request_dialog(frm);
                }, __('SeerBit'));
                
                // Quick payment link button
                frm.add_custom_button(__('Generate Payment Link'), function() {
                    generate_quick_payment_link(frm);
                }, __('SeerBit'));
                
                // Send email button
                if (frm.doc.contact_email || frm.doc.customer_email_id) {
                    frm.add_custom_button(__('Email Payment Link'), function() {
                        email_payment_link_dialog(frm);
                    }, __('SeerBit'));
                }
                
                // QR Code generation button
                frm.add_custom_button(__('Generate QR Code'), function() {
                    generate_payment_qr_code(frm);
                }, __('SeerBit'));
            }
        }
    });
}

function add_seerbit_status_buttons(frm) {
    frm.add_custom_button(__('Check Payment Status'), function() {
        check_payment_status_enhanced(frm);
    }, __('SeerBit'));
    
    frm.add_custom_button(__('View Payment Details'), function() {
        view_payment_details(frm);
    }, __('SeerBit'));
    
    if (frm.doc.seerbit_payment_status === 'Pending') {
        frm.add_custom_button(__('Resend Payment Link'), function() {
            resend_payment_link(frm);
        }, __('SeerBit'));
    }
}

function create_payment_request_dialog(frm) {
    let d = new frappe.ui.Dialog({
        title: __('Create SeerBit Payment Request'),
        fields: [
            {
                label: __('Payment Amount'),
                fieldname: 'amount',
                fieldtype: 'Currency',
                default: frm.doc.outstanding_amount,
                reqd: 1,
                description: __('Amount to be paid by customer')
            },
            {
                label: __('Include Transaction Charges'),
                fieldname: 'include_charges',
                fieldtype: 'Check',
                default: 0,
                description: __('Add SeerBit transaction charges to the amount')
            },
            {
                label: __('Customer Email'),
                fieldname: 'customer_email',
                fieldtype: 'Data',
                default: frm.doc.contact_email || frm.doc.customer_email_id,
                reqd: 1
            },
            {
                label: __('Customer Name'),
                fieldname: 'customer_name',
                fieldtype: 'Data',
                default: frm.doc.customer_name,
                reqd: 1
            },
            {
                label: __('Product Description'),
                fieldname: 'product_description',
                fieldtype: 'Small Text',
                default: `Payment for Invoice ${frm.doc.name}`,
                description: __('Description shown to customer during payment')
            },
            {
                label: __('Auto-redirect after payment'),
                fieldname: 'auto_redirect',
                fieldtype: 'Check',
                default: 1
            }
        ],
        primary_action_label: __('Create Payment Request'),
        primary_action(values) {
            frappe.call({
                method: 'payments.payment_gateways.seerbit_checkout_enhanced.create_invoice_payment_request',
                args: {
                    invoice_name: frm.doc.name,
                    include_charges: values.include_charges
                },
                freeze: true,
                freeze_message: __('Creating payment request...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        d.hide();
                        
                        // Update form with payment details
                        frm.set_value('seerbit_payment_reference', r.message.payment_reference);
                        frm.set_value('seerbit_payment_link', r.message.redirect_url);
                        frm.set_value('seerbit_payment_status', 'Pending');
                        frm.save();
                        
                        // Show success dialog with options
                        show_payment_link_success_dialog(r.message, frm);
                    }
                }
            });
        }
    });
    
    d.show();
}

function generate_quick_payment_link(frm) {
    frappe.call({
        method: 'payments.payment_gateways.seerbit_checkout_enhanced.create_invoice_payment_request',
        args: {
            invoice_name: frm.doc.name,
            include_charges: false
        },
        freeze: true,
        freeze_message: __('Generating payment link...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                // Update form
                frm.set_value('seerbit_payment_reference', r.message.payment_reference);
                frm.set_value('seerbit_payment_link', r.message.redirect_url);
                frm.set_value('seerbit_payment_status', 'Pending');
                frm.save();
                
                // Copy to clipboard and show link
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(r.message.redirect_url);
                    frappe.show_alert({
                        message: __('Payment link copied to clipboard!'),
                        indicator: 'green'
                    });
                }
                
                frappe.msgprint({
                    title: __('Payment Link Generated'),
                    message: `
                        <div class="text-center">
                            <p><strong>Payment Link:</strong></p>
                            <a href="${r.message.redirect_url}" target="_blank" class="btn btn-primary btn-sm">
                                <i class="fa fa-external-link"></i> Open Payment Page
                            </a>
                            <br><br>
                            <div class="form-group">
                                <input type="text" class="form-control" value="${r.message.redirect_url}" readonly>
                            </div>
                            <p class="text-muted small">
                                Amount: ${format_currency(r.message.amount, frm.doc.currency)}<br>
                                Reference: ${r.message.payment_reference}
                            </p>
                        </div>
                    `,
                    indicator: 'green'
                });
            }
        }
    });
}

function email_payment_link_dialog(frm) {
    if (!frm.doc.seerbit_payment_link) {
        frappe.msgprint(__('Please generate a payment link first'));
        return;
    }
    
    let d = new frappe.ui.Dialog({
        title: __('Email Payment Link'),
        fields: [
            {
                label: __('Recipient Email'),
                fieldname: 'email',
                fieldtype: 'Data',
                default: frm.doc.contact_email || frm.doc.customer_email_id,
                reqd: 1
            },
            {
                label: __('Email Subject'),
                fieldname: 'subject',
                fieldtype: 'Data',
                default: `Payment Link for Invoice ${frm.doc.name}`,
                reqd: 1
            },
            {
                label: __('Additional Message'),
                fieldname: 'message',
                fieldtype: 'Text',
                description: __('Additional message to include in the email')
            }
        ],
        primary_action_label: __('Send Email'),
        primary_action(values) {
            frappe.call({
                method: 'frappe.core.doctype.communication.email.make',
                args: {
                    recipients: values.email,
                    subject: values.subject,
                    content: `
                        <p>Dear ${frm.doc.customer_name},</p>
                        <p>Please find below the payment link for Invoice ${frm.doc.name}:</p>
                        <p><strong>Invoice Amount:</strong> ${format_currency(frm.doc.outstanding_amount, frm.doc.currency)}</p>
                        <p><a href="${frm.doc.seerbit_payment_link}" target="_blank" class="btn btn-primary">Pay Now</a></p>
                        ${values.message ? '<p>' + values.message + '</p>' : ''}
                        <p>Thank you for your business!</p>
                    `,
                    doctype: frm.doc.doctype,
                    name: frm.doc.name
                },
                callback: function(r) {
                    if (!r.exc) {
                        d.hide();
                        frappe.show_alert({
                            message: __('Payment link email sent successfully'),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    });
    
    d.show();
}

function generate_payment_qr_code(frm) {
    if (!frm.doc.seerbit_payment_link) {
        frappe.msgprint(__('Please generate a payment link first'));
        return;
    }
    
    // Generate QR code for payment link
    let qr_data = frm.doc.seerbit_payment_link;
    let qr_img_url = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qr_data)}`;
    
    frappe.msgprint({
        title: __('Payment QR Code'),
        message: `
            <div class="text-center">
                <img src="${qr_img_url}" alt="Payment QR Code" class="img-responsive" style="max-width: 200px;">
                <p class="text-muted small">
                    Scan this QR code to make payment<br>
                    Amount: ${format_currency(frm.doc.outstanding_amount, frm.doc.currency)}
                </p>
                <button class="btn btn-default btn-sm" onclick="window.print()">
                    <i class="fa fa-print"></i> Print QR Code
                </button>
            </div>
        `,
        indicator: 'blue'
    });
}

function check_payment_status_enhanced(frm) {
    if (!frm.doc.seerbit_payment_reference) {
        frappe.msgprint(__('No payment reference found'));
        return;
    }
    
    frappe.call({
        method: 'payments.payment_gateways.seerbit_checkout_enhanced.verify_payment_status',
        args: {
            payment_reference: frm.doc.seerbit_payment_reference
        },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                let status_color = 'orange';
                let status_text = r.message.payment_status;
                
                if (status_text === 'SUCCESSFUL') {
                    status_color = 'green';
                    status_text = 'Paid';
                    
                    // Update invoice status
                    frm.set_value('seerbit_payment_status', 'Paid');
                    frm.save();
                } else if (status_text === 'FAILED') {
                    status_color = 'red';
                    status_text = 'Failed';
                    
                    frm.set_value('seerbit_payment_status', 'Failed');
                    frm.save();
                }
                
                frappe.msgprint({
                    title: __('Payment Status'),
                    message: `
                        <div class="text-center">
                            <h4><span class="indicator ${status_color}">${status_text}</span></h4>
                            <p><strong>Amount:</strong> ${r.message.amount || 'N/A'}</p>
                            <p><strong>Transaction Ref:</strong> ${r.message.transaction_ref || 'N/A'}</p>
                            <p><strong>Message:</strong> ${r.message.message || 'N/A'}</p>
                        </div>
                    `,
                    indicator: status_color
                });
            } else {
                frappe.msgprint({
                    title: __('Status Check Failed'),
                    message: r.message ? r.message.message : __('Unable to check payment status'),
                    indicator: 'red'
                });
            }
        }
    });
}

function view_payment_details(frm) {
    if (!frm.doc.seerbit_payment_reference) {
        frappe.msgprint(__('No payment reference found'));
        return;
    }
    
    // Find and show SeerBit Order details
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'SeerBit Order',
            filters: {
                payment_reference: frm.doc.seerbit_payment_reference
            },
            fields: ['name', 'status', 'amount', 'currency', 'gateway_reference', 'gateway_message', 'created_at']
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let order = r.message[0];
                frappe.set_route('Form', 'SeerBit Order', order.name);
            } else {
                frappe.msgprint(__('Payment order details not found'));
            }
        }
    });
}

function show_payment_link_success_dialog(response, frm) {
    let d = new frappe.ui.Dialog({
        title: __('Payment Request Created Successfully'),
        fields: [
            {
                fieldtype: 'HTML',
                options: `
                    <div class="text-center">
                        <div class="alert alert-success">
                            <h4><i class="fa fa-check-circle"></i> Payment request created!</h4>
                        </div>
                        <p><strong>Payment Reference:</strong> ${response.payment_reference}</p>
                        <p><strong>Amount:</strong> ${format_currency(response.amount, frm.doc.currency)}</p>
                        <br>
                        <a href="${response.redirect_url}" target="_blank" class="btn btn-primary btn-lg">
                            <i class="fa fa-external-link"></i> Open Payment Page
                        </a>
                    </div>
                `
            }
        ],
        primary_action_label: __('Copy Link'),
        primary_action() {
            if (navigator.clipboard) {
                navigator.clipboard.writeText(response.redirect_url);
                frappe.show_alert({
                    message: __('Payment link copied to clipboard'),
                    indicator: 'green'
                });
            }
        },
        secondary_action_label: __('Send Email'),
        secondary_action() {
            d.hide();
            email_payment_link_dialog(frm);
        }
    });
    
    d.show();
}

function show_payment_status_indicator(frm) {
    if (frm.doc.seerbit_payment_status) {
        let color = 'gray';
        let text = frm.doc.seerbit_payment_status;
        
        switch(frm.doc.seerbit_payment_status) {
            case 'Paid':
                color = 'green';
                break;
            case 'Pending':
                color = 'orange';
                break;
            case 'Failed':
                color = 'red';
                break;
        }
        
        frm.dashboard.add_indicator(__('SeerBit Status: {0}', [text]), color);
    }
}

function resend_payment_link(frm) {
    if (frm.doc.contact_email || frm.doc.customer_email_id) {
        email_payment_link_dialog(frm);
    } else {
        frappe.msgprint(__('No customer email found to send payment link'));
    }
}
