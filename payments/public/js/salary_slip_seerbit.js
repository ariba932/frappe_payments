// SeerBit Salary Payout Integration for Salary Slip
frappe.ui.form.on('Salary Slip', {
    refresh: function(frm) {
        // Add SeerBit salary payout button
        if (frm.doc.docstatus === 1 && frm.doc.net_pay > 0 && 
            !frm.doc.seerbit_payout_reference &&
            frappe.user.has_role(['HR Manager', 'Payroll Manager', 'Accounts Manager'])) {
            
            // Check if employee has SeerBit enabled
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Employee',
                    filters: {'name': frm.doc.employee},
                    fieldname: 'seerbit_payout_enabled'
                },
                callback: function(r) {
                    if (r.message && r.message.seerbit_payout_enabled) {
                        frm.add_custom_button(__('Pay via SeerBit'), function() {
                            initiate_salary_payout(frm);
                        }, __('Actions'));
                    }
                }
            });
        }
        
        // Show bulk payout button for payroll managers
        if (frappe.user.has_role(['Payroll Manager', 'HR Manager'])) {
            frm.add_custom_button(__('Bulk SeerBit Payouts'), function() {
                open_bulk_payout_dialog(frm);
            }, __('Tools'));
        }
        
        // Show payout status if SeerBit payout exists
        if (frm.doc.seerbit_payout_reference) {
            frm.add_custom_button(__('Check Payout Status'), function() {
                check_salary_payout_status(frm);
            }, __('SeerBit'));
        }
    }
});

function initiate_salary_payout(frm) {
    frappe.confirm(
        __('Are you sure you want to initiate SeerBit salary payout of {0} to {1}?', 
           [format_currency(frm.doc.net_pay, 'NGN'), frm.doc.employee_name]),
        function() {
            frappe.call({
                method: 'payments.payment_gateways.doctype.seerbit_payout.seerbit_payout.initiate_salary_payout',
                args: {
                    'salary_slip_name': frm.doc.name
                },
                freeze: true,
                freeze_message: __('Initiating salary payout...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        frm.set_value('seerbit_payout_reference', r.message.payout_reference);
                        frm.set_value('seerbit_payout_status', 'Processing');
                        frm.save();
                        
                        frappe.msgprint({
                            title: __('Salary Payout Initiated'),
                            message: __('SeerBit salary payout has been initiated. Reference: {0}', [r.message.payout_reference]),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    );
}

function open_bulk_payout_dialog(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Bulk SeerBit Salary Payouts'),
        fields: [
            {
                fieldname: 'company',
                fieldtype: 'Link',
                label: __('Company'),
                options: 'Company',
                reqd: 1
            },
            {
                fieldname: 'payroll_period',
                fieldtype: 'Link',
                label: __('Payroll Period'),
                options: 'Payroll Period',
                reqd: 1
            },
            {
                fieldname: 'salary_month',
                fieldtype: 'Data',
                label: __('Salary Month (YYYY-MM)'),
                reqd: 1
            },
            {
                fieldname: 'department',
                fieldtype: 'Link',
                label: __('Department (Optional)'),
                options: 'Department'
            }
        ],
        primary_action_label: __('Get Salary Slips'),
        primary_action: function() {
            let values = dialog.get_values();
            get_bulk_salary_slips(values, dialog);
        }
    });
    dialog.show();
}

function get_bulk_salary_slips(filters, dialog) {
    frappe.call({
        method: 'payments.payment_gateways.doctype.seerbit_payout.seerbit_payout.get_salary_slips_for_bulk_payout',
        args: filters,
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                show_bulk_payout_confirmation(r.message, dialog);
            } else {
                frappe.msgprint(__('No eligible salary slips found'));
            }
        }
    });
}

function show_bulk_payout_confirmation(salary_slips, dialog) {
    dialog.hide();
    
    let total_amount = salary_slips.reduce((sum, slip) => sum + slip.net_pay, 0);
    
    frappe.confirm(
        __('Process {0} salary payouts totaling {1}?', [salary_slips.length, format_currency(total_amount, 'NGN')]),
        function() {
            process_bulk_payouts(salary_slips);
        }
    );
}

function process_bulk_payouts(salary_slips) {
    frappe.call({
        method: 'payments.payment_gateways.doctype.seerbit_payout.seerbit_payout.process_bulk_salary_payouts',
        args: {
            'salary_slip_names': salary_slips.map(s => s.name)
        },
        freeze: true,
        freeze_message: __('Processing bulk payouts...'),
        callback: function(r) {
            if (r.message) {
                frappe.msgprint({
                    title: __('Bulk Payouts Status'),
                    message: __('Successful: {0}<br>Failed: {1}', [r.message.successful_count, r.message.failed_count]),
                    indicator: r.message.failed_count === 0 ? 'green' : 'orange'
                });
            }
        }
    });
}

function check_salary_payout_status(frm) {
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
                    title: __('Salary Payout Status'),
                    message: __('Status: {0}<br>Amount: {1}', [r.message.status, r.message.amount]),
                    indicator: r.message.status === 'Paid' ? 'green' : 'orange'
                });
            }
        }
    });
}
