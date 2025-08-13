# -*- coding: utf-8 -*-
"""
SeerBit Dashboard and Reporting Utilities
Provides dashboard data and reporting for SeerBit operations
"""

import frappe
from frappe import _
from frappe.utils import nowdate, add_days, getdate


def get_payment_dashboard_data(company=None, date_range="30_days"):
    """Get payment dashboard data for selling operations"""
    date_filter = _get_date_filter(date_range)
    
    company_filter = ""
    params = {"from_date": date_filter["from_date"], "to_date": date_filter["to_date"]}
    
    if company:
        company_filter = "AND so.company = %(company)s"
        params["company"] = company
    
    # Payment statistics
    payment_stats = frappe.db.sql(f"""
        SELECT 
            so.status,
            COUNT(*) as count,
            SUM(so.amount) as total_amount,
            AVG(so.amount) as avg_amount
        FROM `tabSeerBit Order` so
        WHERE so.creation BETWEEN %(from_date)s AND %(to_date)s
        {company_filter}
        GROUP BY so.status
        ORDER BY so.status
    """, params, as_dict=True)
    
    # Recent orders
    recent_orders = frappe.db.sql(f"""
        SELECT 
            so.name, so.payment_reference, so.amount, so.currency, 
            so.status, so.customer_name, so.creation, so.redirect_url
        FROM `tabSeerBit Order` so
        WHERE so.creation BETWEEN %(from_date)s AND %(to_date)s
        {company_filter}
        ORDER BY so.creation DESC
        LIMIT 10
    """, params, as_dict=True)
    
    # Currency breakdown
    currency_stats = frappe.db.sql(f"""
        SELECT 
            so.currency,
            COUNT(*) as count,
            SUM(so.amount) as total_amount
        FROM `tabSeerBit Order` so
        WHERE so.creation BETWEEN %(from_date)s AND %(to_date)s
        {company_filter}
        GROUP BY so.currency
        ORDER BY total_amount DESC
    """, params, as_dict=True)
    
    return {
        "payment_stats": payment_stats,
        "recent_orders": recent_orders,
        "currency_stats": currency_stats,
        "date_range": date_range,
        "from_date": date_filter["from_date"],
        "to_date": date_filter["to_date"]
    }


def get_payout_dashboard_data(company=None, date_range="30_days"):
    """Get payout dashboard data for buying operations"""
    date_filter = _get_date_filter(date_range)
    
    company_filter = ""
    params = {"from_date": date_filter["from_date"], "to_date": date_filter["to_date"]}
    
    if company:
        company_filter = "AND sp.company = %(company)s"
        params["company"] = company
    
    # Payout statistics by status
    payout_stats = frappe.db.sql(f"""
        SELECT 
            sp.status,
            sp.beneficiary_type,
            COUNT(*) as count,
            SUM(sp.amount) as total_amount,
            AVG(sp.amount) as avg_amount
        FROM `tabSeerBit Payout` sp
        WHERE sp.creation BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY sp.status, sp.beneficiary_type
        ORDER BY sp.status, sp.beneficiary_type
    """, params, as_dict=True)
    
    # Recent payouts
    recent_payouts = frappe.db.sql(f"""
        SELECT 
            sp.name, sp.payout_reference, sp.amount, sp.currency, 
            sp.status, sp.beneficiary_name, sp.beneficiary_type,
            sp.creation, sp.payout_method
        FROM `tabSeerBit Payout` sp
        WHERE sp.creation BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY sp.creation DESC
        LIMIT 10
    """, params, as_dict=True)
    
    # Method breakdown
    method_stats = frappe.db.sql(f"""
        SELECT 
            sp.payout_method,
            COUNT(*) as count,
            SUM(sp.amount) as total_amount,
            COUNT(CASE WHEN sp.status = 'Paid' THEN 1 END) as successful_count
        FROM `tabSeerBit Payout` sp
        WHERE sp.creation BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY sp.payout_method
        ORDER BY total_amount DESC
    """, params, as_dict=True)
    
    return {
        "payout_stats": payout_stats,
        "recent_payouts": recent_payouts,
        "method_stats": method_stats,
        "date_range": date_range,
        "from_date": date_filter["from_date"],
        "to_date": date_filter["to_date"]
    }


def get_comprehensive_dashboard_data(company=None, date_range="30_days"):
    """Get comprehensive dashboard data combining payments and payouts"""
    payment_data = get_payment_dashboard_data(company, date_range)
    payout_data = get_payout_dashboard_data(company, date_range)
    
    # Calculate totals
    total_payments = sum([stat["total_amount"] for stat in payment_data["payment_stats"]])
    total_payouts = sum([stat["total_amount"] for stat in payout_data["payout_stats"]])
    
    # Get pending verifications
    pending_verifications = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabSeerBit Payout`
        WHERE status IN ('Pending', 'Processing')
        AND creation >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """, as_dict=True)
    
    # Get failed transactions needing attention
    failed_transactions = frappe.db.sql("""
        SELECT 
            'Payment' as type, payment_reference as reference, 
            amount, customer_name as party, creation
        FROM `tabSeerBit Order`
        WHERE status = 'Failed' AND creation >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        UNION ALL
        SELECT 
            'Payout' as type, payout_reference as reference,
            amount, beneficiary_name as party, creation
        FROM `tabSeerBit Payout`
        WHERE status = 'Failed' AND creation >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        ORDER BY creation DESC
        LIMIT 10
    """, as_dict=True)
    
    return {
        "summary": {
            "total_payments": total_payments,
            "total_payouts": total_payouts,
            "net_flow": total_payments - total_payouts,
            "pending_verifications": pending_verifications[0]["count"] if pending_verifications else 0,
            "failed_transactions_count": len(failed_transactions)
        },
        "payments": payment_data,
        "payouts": payout_data,
        "failed_transactions": failed_transactions,
        "date_range": date_range
    }


def get_employee_payout_summary(company, department=None, payroll_period=None):
    """Get employee payout summary for payroll dashboard"""
    filters = {"company": company}
    
    department_filter = ""
    payroll_filter = ""
    
    if department:
        department_filter = "AND e.department = %(department)s"
        filters["department"] = department
    
    if payroll_period:
        payroll_filter = "AND ss.payroll_period = %(payroll_period)s"
        filters["payroll_period"] = payroll_period
    
    # Employee payout readiness
    employee_summary = frappe.db.sql(f"""
        SELECT 
            e.department,
            COUNT(*) as total_employees,
            COUNT(CASE WHEN e.seerbit_payout_enabled = 1 THEN 1 END) as seerbit_enabled,
            COUNT(CASE WHEN e.seerbit_payout_enabled = 1 AND e.bank_ac_no IS NOT NULL 
                       AND e.seerbit_bank_code IS NOT NULL THEN 1 END) as ready_for_payout,
            COUNT(CASE WHEN e.account_verification_status = 'Verified' THEN 1 END) as verified_accounts
        FROM `tabEmployee` e
        WHERE e.company = %(company)s
        AND e.status = 'Active'
        {department_filter}
        GROUP BY e.department
        ORDER BY e.department
    """, filters, as_dict=True)
    
    # Salary slip payout status
    if payroll_period:
        salary_summary = frappe.db.sql(f"""
            SELECT 
                ss.department,
                COUNT(*) as total_slips,
                SUM(ss.net_pay) as total_amount,
                COUNT(CASE WHEN ss.seerbit_payout_status = 'Paid' THEN 1 END) as paid_count,
                SUM(CASE WHEN ss.seerbit_payout_status = 'Paid' THEN ss.net_pay ELSE 0 END) as paid_amount,
                COUNT(CASE WHEN ss.seerbit_payout_status = 'Processing' THEN 1 END) as processing_count,
                COUNT(CASE WHEN ss.seerbit_payout_status = 'Failed' THEN 1 END) as failed_count
            FROM `tabSalary Slip` ss
            INNER JOIN `tabEmployee` e ON ss.employee = e.name
            WHERE ss.company = %(company)s
            AND ss.docstatus = 1
            AND e.seerbit_payout_enabled = 1
            {payroll_filter}
            {department_filter}
            GROUP BY ss.department
            ORDER BY ss.department
        """, filters, as_dict=True)
    else:
        salary_summary = []
    
    return {
        "employee_summary": employee_summary,
        "salary_summary": salary_summary,
        "filters": filters
    }


def get_supplier_payout_summary(company, supplier_group=None):
    """Get supplier payout summary"""
    filters = {"company": company}
    
    supplier_group_filter = ""
    if supplier_group:
        supplier_group_filter = "AND s.supplier_group = %(supplier_group)s"
        filters["supplier_group"] = supplier_group
    
    # Supplier payout readiness
    supplier_summary = frappe.db.sql(f"""
        SELECT 
            s.supplier_group,
            COUNT(*) as total_suppliers,
            COUNT(CASE WHEN s.seerbit_payout_enabled = 1 THEN 1 END) as seerbit_enabled,
            COUNT(CASE WHEN s.seerbit_payout_enabled = 1 AND s.default_bank_account IS NOT NULL 
                       AND s.seerbit_bank_code IS NOT NULL THEN 1 END) as ready_for_payout,
            COUNT(CASE WHEN s.account_verification_status = 'Verified' THEN 1 END) as verified_accounts
        FROM `tabSupplier` s
        WHERE s.company = %(company)s
        AND s.disabled = 0
        {supplier_group_filter}
        GROUP BY s.supplier_group
        ORDER BY s.supplier_group
    """, filters, as_dict=True)
    
    # Outstanding purchase invoices
    outstanding_invoices = frappe.db.sql(f"""
        SELECT 
            pi.supplier_name,
            COUNT(*) as invoice_count,
            SUM(pi.outstanding_amount) as total_outstanding
        FROM `tabPurchase Invoice` pi
        INNER JOIN `tabSupplier` s ON pi.supplier = s.name
        WHERE pi.company = %(company)s
        AND pi.docstatus = 1
        AND pi.outstanding_amount > 0
        AND s.seerbit_payout_enabled = 1
        {supplier_group_filter}
        GROUP BY pi.supplier_name
        ORDER BY total_outstanding DESC
        LIMIT 10
    """, filters, as_dict=True)
    
    return {
        "supplier_summary": supplier_summary,
        "outstanding_invoices": outstanding_invoices,
        "filters": filters
    }


def _get_date_filter(date_range):
    """Get date filter based on range"""
    today = getdate(nowdate())
    
    if date_range == "7_days":
        from_date = add_days(today, -7)
    elif date_range == "30_days":
        from_date = add_days(today, -30)
    elif date_range == "90_days":
        from_date = add_days(today, -90)
    elif date_range == "1_year":
        from_date = add_days(today, -365)
    else:
        from_date = add_days(today, -30)  # Default to 30 days
    
    return {
        "from_date": from_date,
        "to_date": today
    }


# API endpoints
@frappe.whitelist()
def get_payment_dashboard(company=None, date_range="30_days"):
    """API endpoint for payment dashboard"""
    return get_payment_dashboard_data(company, date_range)


@frappe.whitelist()
def get_payout_dashboard(company=None, date_range="30_days"):
    """API endpoint for payout dashboard"""
    return get_payout_dashboard_data(company, date_range)


@frappe.whitelist()
def get_comprehensive_dashboard(company=None, date_range="30_days"):
    """API endpoint for comprehensive dashboard"""
    return get_comprehensive_dashboard_data(company, date_range)


@frappe.whitelist()
def get_employee_dashboard(company, department=None, payroll_period=None):
    """API endpoint for employee payout dashboard"""
    return get_employee_payout_summary(company, department, payroll_period)


@frappe.whitelist()
def get_supplier_dashboard(company, supplier_group=None):
    """API endpoint for supplier payout dashboard"""
    return get_supplier_payout_summary(company, supplier_group)
