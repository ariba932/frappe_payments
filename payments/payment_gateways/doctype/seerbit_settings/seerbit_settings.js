// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("SeerBit Settings", {
  refresh: function (frm) {
    frm.add_custom_button(__("Clear"), function () {
      frm.call({
        doc: frm.doc,
        method: "clear",
        callback: function (r) {
          frm.refresh();
        },
      });
    });
  },
  refresh: function(frm) {
      if (frm.doc.is_enabled) {
          frm.add_custom_button(__('Refresh Bank Codes'), function() {
              frappe.call({
                  method: 'refresh_bank_codes',
                  doc: frm.doc,
                  callback: function(r) {
                      if (!r.exc) {
                          frm.reload_doc();
                      }
                  }
              });
          });
      }
  },
});
