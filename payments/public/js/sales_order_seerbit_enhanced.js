// Enhanced SeerBit Payment Integration for Sales Order
// Supports advance payments with configurable percentage

frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        // Add SeerBit advance payment buttons for submitted sales orders
        if (frm.doc.docstatus === 1 && frm.doc.per_billed < 100) {
            add_seerbit_advance_payment_buttons(frm);
        }
        
        // Show advance payment history
        if (frm.doc.advance_paid > 0) {
            show_advance_payment_summary(frm);
        }
    }
});

function add_seerbit_advance_payment_buttons(frm) {
    // Check if SeerBit is enabled
    frappe.call({
        method: 'frappe.client.get_single',
        args: {
            doctype: 'SeerBit Settings'
        },
        callback: function(r) {
            if (r.message && r.message.is_enabled) {
                // Advanced payment request button
                frm.add_custom_button(__('Request Advance Payment'), function() {
                    create_advance_payment_dialog(frm);
                }, __('SeerBit'));
                
                // Quick 50% advance button
                frm.add_custom_button(__('50% Advance Payment'), function() {
                    create_quick_advance_payment(frm, 50);
                }, __('SeerBit'));
                
                // Full payment button
                if (frm.doc.advance_paid === 0) {
                    frm.add_custom_button(__('Full Payment'), function() {
                        create_quick_advance_payment(frm, 100);
                    }, __('SeerBit'));
                }
            }
        }
    });
}

function create_advance_payment_dialog(frm) {
    let remaining_amount = frm.doc.grand_total - frm.doc.advance_paid;
    
    let d = new frappe.ui.Dialog({
        title: __('Create Advance Payment Request'),
        fields: [
            {
                label: __('Sales Order Details'),
                fieldname: 'order_info',
                fieldtype: 'HTML',
                options: `
                    <div class="row">
                        <div class="col-sm-6">
                            <strong>Total Amount:</strong> ${format_currency(frm.doc.grand_total, frm.doc.currency)}
                        </div>
                        <div class="col-sm-6">
                            <strong>Advance Paid:</strong> ${format_currency(frm.doc.advance_paid, frm.doc.currency)}
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-sm-6">
                            <strong>Remaining:</strong> ${format_currency(remaining_amount, frm.doc.currency)}
                        </div>
                        <div class="col-sm-6">
                            <strong>% Billed:</strong> ${frm.doc.per_billed}%
                        </div>
                    </div>
                    <hr>
                `
            },
            {
                label: __('Advance Payment Percentage'),
                fieldname: 'advance_percentage',
                fieldtype: 'Percent',
                default: 50,
                reqd: 1,
                description: __('Percentage of remaining amount to request as advance')
            },
            {
                label: __('Advance Amount'),
                fieldname: 'advance_amount',
                fieldtype: 'Currency',
                default: remaining_amount * 0.5,
                reqd: 1,
                depends_on: 'advance_percentage'
            },
            {
                label: __('Customer Email'),
                fieldname: 'customer_email',
                fieldtype: 'Data',
                default: frm.doc.contact_email,
                reqd: 1
            },
            {
                label: __('Payment Description'),
                fieldname: 'payment_description',
                fieldtype: 'Small Text',
                default: `Advance payment for Sales Order ${frm.doc.name}`,
                description: __('Description shown to customer during payment')
            },
            {
                label: __('Payment Due Date'),
                fieldname: 'due_date',
                fieldtype: 'Date',
                description: __('Expected payment completion date')
            }
        ],
        primary_action_label: __('Create Payment Request'),
        primary_action(values) {
            frappe.call({
                method: 'payments.payment_gateways.seerbit_checkout_enhanced.create_sales_order_payment_request',
                args: {
                    sales_order_name: frm.doc.name,
                    advance_percentage: values.advance_percentage
                },
                freeze: true,
                freeze_message: __('Creating advance payment request...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        d.hide();
                        
                        // Show success dialog
                        show_advance_payment_success_dialog(r.message, frm);
                    }
                }
            });
        }
    });
    
    // Update advance amount when percentage changes
    d.fields_dict.advance_percentage.$input.on('change', function() {
        let percentage = parseFloat(d.get_value('advance_percentage')) || 0;
        let amount = remaining_amount * (percentage / 100);
        d.set_value('advance_amount', amount);
    });
    
    d.show();
}

function create_quick_advance_payment(frm, percentage) {
    let remaining_amount = frm.doc.grand_total - frm.doc.advance_paid;
    let advance_amount = remaining_amount * (percentage / 100);
    
    frappe.confirm(
        __('Create {0}% advance payment request for {1}?', [percentage, format_currency(advance_amount, frm.doc.currency)]),
        function() {
            frappe.call({
                method: 'payments.payment_gateways.seerbit_checkout_enhanced.create_sales_order_payment_request',
                args: {
                    sales_order_name: frm.doc.name,
                    advance_percentage: percentage
                },
                freeze: true,
                freeze_message: __('Creating payment request...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        show_advance_payment_success_dialog(r.message, frm);
                    }
                }
            });
        }
    );
}

function show_advance_payment_success_dialog(response, frm) {
    let d = new frappe.ui.Dialog({
        title: __('Advance Payment Request Created'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                options: `
                    <div class="text-center">
                        <div class="alert alert-success">
                            <h4><i class="fa fa-check-circle"></i> Advance payment request created!</h4>
                        </div>
                        <div class="row">
                            <div class="col-sm-6">
                                <strong>Payment Reference:</strong><br>
                                <code>${response.payment_reference}</code>
                            </div>
                            <div class="col-sm-6">
                                <strong>Advance Amount:</strong><br>
                                ${format_currency(response.amount, frm.doc.currency)}
                            </div>
                        </div>
                        <br>
                        <a href="${response.redirect_url}" target="_blank" class="btn btn-primary btn-lg">
                            <i class="fa fa-external-link"></i> Open Payment Page
                        </a>
                        <br><br>
                        <div class="form-group">
                            <label>Payment Link:</label>
                            <input type="text" class="form-control" value="${response.redirect_url}" readonly>
                        </div>
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
            send_advance_payment_email(frm, response);
            d.hide();
        }
    });
    
    d.show();
}

function send_advance_payment_email(frm, payment_response) {
    if (!frm.doc.contact_email) {
        frappe.msgprint(__('Customer email not found'));
        return;
    }
    
    frappe.call({
        method: 'frappe.core.doctype.communication.email.make',
        args: {
            recipients: frm.doc.contact_email,
            subject: `Advance Payment Request for Sales Order ${frm.doc.name}`,
            content: `
                <p>Dear ${frm.doc.customer_name},</p>
                <p>We are pleased to confirm your Sales Order ${frm.doc.name}. To proceed with order processing, we request an advance payment.</p>
                
                <div style="border: 1px solid #ddd; padding: 15px; margin: 15px 0; border-radius: 5px;">
                    <h4>Order Details:</h4>
                    <table style="width: 100%;">
                        <tr><td><strong>Order Number:</strong></td><td>${frm.doc.name}</td></tr>
                        <tr><td><strong>Order Date:</strong></td><td>${frappe.datetime.str_to_user(frm.doc.transaction_date)}</td></tr>
                        <tr><td><strong>Total Amount:</strong></td><td>${format_currency(frm.doc.grand_total, frm.doc.currency)}</td></tr>
                        <tr><td><strong>Advance Requested:</strong></td><td><strong>${format_currency(payment_response.amount, frm.doc.currency)}</strong></td></tr>
                    </table>
                </div>
                
                <p style="text-align: center;">
                    <a href="${payment_response.redirect_url}" target="_blank" 
                       style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Pay Advance Amount
                    </a>
                </p>
                
                <p><strong>Payment Reference:</strong> ${payment_response.payment_reference}</p>
                <p>Please make the advance payment to confirm your order. Once payment is received, we will begin processing your order.</p>
                <p>If you have any questions, please don't hesitate to contact us.</p>
                <p>Thank you for your business!</p>
            `,
            doctype: frm.doc.doctype,
            name: frm.doc.name
        },
        callback: function(r) {
            if (!r.exc) {
                frappe.show_alert({
                    message: __('Advance payment request email sent successfully'),
                    indicator: 'green'
                });
            }
        }
    });
}

function show_advance_payment_summary(frm) {
    // Add advance payment summary to dashboard
    let advance_percent = (frm.doc.advance_paid / frm.doc.grand_total) * 100;
    
    frm.dashboard.add_indicator(
        __('Advance Paid: {0} ({1}%)', [
            format_currency(frm.doc.advance_paid, frm.doc.currency),
            advance_percent.toFixed(1)
        ]), 
        'blue'
    );
    
    // Add button to view advance payment entries
    frm.add_custom_button(__('View Advance Payments'), function() {
        frappe.route_options = {
            "party_type": "Customer",
            "party": frm.doc.customer,
            "is_advance": "Yes",
            "docstatus": 1
        };
        frappe.set_route("List", "Payment Entry");
    }, __('SeerBit'));
}
