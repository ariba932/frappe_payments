// SeerBit Department Integration
frappe.ui.form.on('Department', {
    refresh: function(frm) {
        // Add create pocket button
        if (frm.doc.enable_seerbit_pocket && !frm.doc.seerbit_pocket) {
            frm.add_custom_button(__('Create SeerBit Pocket'), function() {
                create_department_pocket(frm);
            }, __('SeerBit'));
        }
        
        // Show pocket details if exists
        if (frm.doc.seerbit_pocket) {
            frm.add_custom_button(__('View Pocket'), function() {
                frappe.set_route('Form', 'SeerBit Pocket', frm.doc.seerbit_pocket);
            }, __('SeerBit'));
            
            frm.add_custom_button(__('Sync Pocket Balance'), function() {
                sync_pocket_balance(frm);
            }, __('SeerBit'));
        }
    },
    
    enable_seerbit_pocket: function(frm) {
        if (frm.doc.enable_seerbit_pocket && frm.doc.auto_create_pocket && !frm.doc.seerbit_pocket) {
            create_department_pocket(frm);
        }
    }
});

function create_department_pocket(frm) {
    frappe.call({
        method: 'payments.seerbit_operations.utils.integration_utils.create_department_pocket',
        args: {
            department: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frappe.msgprint(__('Department pocket created successfully: {0}', [r.message.pocket]));
                frm.reload_doc();
            } else {
                frappe.msgprint(__('Error: {0}', [r.message ? r.message.message : 'Unknown error']));
            }
        }
    });
}

function sync_pocket_balance(frm) {
    if (!frm.doc.seerbit_pocket) {
        frappe.msgprint(__('No pocket linked to this department'));
        return;
    }
    
    frappe.call({
        method: 'payments.seerbit_operations.doctype.seerbit_pocket.seerbit_pocket.sync_balance',
        args: {
            pocket: frm.doc.seerbit_pocket
        },
        callback: function(r) {
            if (r.message) {
                frappe.msgprint(__('Pocket balance synced successfully'));
            }
        }
    });
}
