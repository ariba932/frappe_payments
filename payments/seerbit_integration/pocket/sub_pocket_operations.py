# -*- coding: utf-8 -*-
"""
SeerBit Sub-Pocket Operations
Handles creation and management of sub-pockets for departments/projects
"""

import frappe
from frappe import _
from frappe.utils import nowdate
from ..core.api_client import get_api_client


class SeerBitSubPocketOperations:
    """Sub-pocket creation and management operations"""
    
    def __init__(self):
        from ..core.api_client import get_seerbit_settings
        self.settings = get_seerbit_settings()
        self.api_client = get_api_client(self.settings)
        
        if not self.settings.is_enabled:
            frappe.throw(_("SeerBit is not enabled"))
        
        if not self.settings.enable_payouts:
            frappe.throw(_("SeerBit payouts are not enabled"))
    
    def create_sub_pocket(self, **kwargs):
        """
        Create a sub-pocket for department/project management
        
        Args:
            business_name (str): Business name for the sub-pocket
            first_name (str): Owner first name
            last_name (str): Owner last name
            email_address (str): Owner email
            phone_number (str): Owner phone number
            tag_group (str, optional): Tag group for categorization
            tag_name (str, optional): Tag name
            pocket_function (str, optional): BOTH, SEND, RECEIVE (default: BOTH)
            currency (str, optional): Currency (default: NGN)
            reference (str, optional): Unique reference
            department (str, optional): ERPNext department to link
            cost_center (str, optional): ERPNext cost center to link
        """
        bearer_token = self.api_client.get_bearer_token()
        parent_pocket_id = self.settings.pocket_id
        
        if not parent_pocket_id:
            frappe.throw(_("Parent Pocket ID is required"))
        
        # Validate required parameters
        required_params = ["business_name", "first_name", "last_name", "email_address", "phone_number"]
        for param in required_params:
            if not kwargs.get(param):
                frappe.throw(_("Missing required parameter: {0}").format(param))
        
        # Generate unique reference if not provided
        reference = kwargs.get("reference") or f"sub-pocket-{frappe.generate_hash(length=8)}"
        
        url = f"{self.api_client.pocket_base_url}/pocket/pocket-id/{parent_pocket_id}/sub-pocket"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "Public-Key": self.settings.public_key
        }
        
        data = [{
            "tagGroup": kwargs.get("tag_group", ""),
            "reference": reference,
            "pocketFunction": kwargs.get("pocket_function", "BOTH"),
            "currency": kwargs.get("currency", "NGN"),
            "tagName": kwargs.get("tag_name", ""),
            "selfOwned": False,
            "pocketOwner": {
                "existingPocketOwner": "false",
                "pocketOwnerDetails": {
                    "firstName": kwargs["first_name"],
                    "lastName": kwargs["last_name"],
                    "emailAddress": kwargs["email_address"],
                    "phoneNumber": kwargs["phone_number"],
                    "businessName": kwargs["business_name"]
                }
            }
        }]
        
        try:
            response = self.api_client._make_request("POST", url, headers=headers, json_data=data)
            
            if response.get("responseCode") == "00" and response.get("data"):
                sub_pocket_data = response["data"][0]  # API returns array
                
                # Create SeerBit Sub-Pocket record in ERPNext
                sub_pocket_doc = self._create_sub_pocket_record(sub_pocket_data, kwargs)
                
                return {
                    "status": "success",
                    "sub_pocket_id": sub_pocket_data.get("pocketId"),
                    "account_number": sub_pocket_data.get("bankAccountNumber"),
                    "bank_name": sub_pocket_data.get("bankName"),
                    "record_id": sub_pocket_doc.name,
                    "reference": reference,
                    "message": "Sub-pocket created successfully"
                }
            else:
                frappe.throw(_("Sub-pocket creation failed: {0}").format(response.get("message", "Unknown error")))
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Sub-Pocket Creation Error")
            frappe.throw(_("Failed to create sub-pocket: {0}").format(str(e)))
    
    def create_department_sub_pocket(self, department_name):
        """Create sub-pocket for a specific ERPNext department"""
        department = frappe.get_doc("Department", department_name)
        
        # Get department manager details if available
        department_manager = None
        if department.leave_approvers:
            approver = department.leave_approvers[0]
            if approver.approver:
                try:
                    employee = frappe.get_value("Employee", {"user_id": approver.approver}, 
                                              ["employee_name", "company_email", "cell_number"], as_dict=True)
                    if employee:
                        department_manager = employee
                except:
                    pass
        
        # Default to company admin if no manager found
        if not department_manager:
            company = department.company or frappe.defaults.get_defaults().get("company")
            if company:
                company_doc = frappe.get_doc("Company", company)
                department_manager = {
                    "employee_name": f"{department.department_name} Admin",
                    "company_email": f"admin@{company_doc.domain}",
                    "cell_number": "08000000000"
                }
        
        # Extract names
        full_name = department_manager.get("employee_name", department.department_name)
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else "Department"
        
        # Create sub-pocket
        sub_pocket_params = {
            "business_name": f"{department.department_name} Department",
            "first_name": first_name,
            "last_name": last_name,
            "email_address": department_manager.get("company_email", "dept@company.com"),
            "phone_number": department_manager.get("cell_number", "08000000000"),
            "tag_group": "DEPARTMENTS",
            "tag_name": department.department_name,
            "reference": f"DEPT-{department.name}-{frappe.generate_hash(length=6)}",
            "department": department.name,
            "pocket_function": "BOTH"
        }
        
        return self.create_sub_pocket(**sub_pocket_params)
    
    def create_cost_center_sub_pocket(self, cost_center_name):
        """Create sub-pocket for a specific ERPNext cost center"""
        cost_center = frappe.get_doc("Cost Center", cost_center_name)
        
        # Create sub-pocket for cost center
        sub_pocket_params = {
            "business_name": f"{cost_center.cost_center_name} Cost Center",
            "first_name": "Cost Center",
            "last_name": "Manager",
            "email_address": f"costcenter@{cost_center.company.lower().replace(' ', '')}.com",
            "phone_number": "08000000000",
            "tag_group": "COST_CENTERS",
            "tag_name": cost_center.cost_center_name,
            "reference": f"CC-{cost_center.name}-{frappe.generate_hash(length=6)}",
            "cost_center": cost_center.name,
            "pocket_function": "BOTH"
        }
        
        return self.create_sub_pocket(**sub_pocket_params)
    
    def bulk_create_department_sub_pockets(self, company=None):
        """Create sub-pockets for all departments in a company"""
        filters = {"is_group": 0}  # Only leaf departments
        if company:
            filters["company"] = company
        
        departments = frappe.get_all("Department", filters=filters, fields=["name", "department_name"])
        
        results = []
        successful_count = 0
        failed_count = 0
        
        for dept in departments:
            try:
                # Check if sub-pocket already exists
                if frappe.db.exists("SeerBit Sub-Pocket", {"department": dept.name}):
                    results.append({
                        "department": dept.name,
                        "status": "skipped",
                        "message": "Sub-pocket already exists"
                    })
                    continue
                
                result = self.create_department_sub_pocket(dept.name)
                results.append({
                    "department": dept.name,
                    "status": "success",
                    "sub_pocket_id": result["sub_pocket_id"],
                    "account_number": result["account_number"]
                })
                successful_count += 1
                
            except Exception as e:
                results.append({
                    "department": dept.name,
                    "status": "failed",
                    "error": str(e)
                })
                failed_count += 1
                frappe.log_error(f"Department sub-pocket creation failed for {dept.name}: {str(e)}", 
                               "Bulk Department Sub-Pocket Creation")
        
        return {
            "status": "completed",
            "successful_count": successful_count,
            "failed_count": failed_count,
            "skipped_count": len(results) - successful_count - failed_count,
            "results": results,
            "total_processed": len(departments)
        }
    
    def _create_sub_pocket_record(self, sub_pocket_data, original_params):
        """Create SeerBit Sub-Pocket record in ERPNext"""
        sub_pocket_doc = frappe.get_doc({
            "doctype": "SeerBit Sub-Pocket",
            "sub_pocket_id": sub_pocket_data.get("pocketId"),
            "parent_pocket_id": sub_pocket_data.get("parentId"),
            "reference": original_params.get("reference"),
            "bank_account_number": sub_pocket_data.get("bankAccountNumber"),
            "bank_account_name": sub_pocket_data.get("bankAccountName"),
            "bank_code": sub_pocket_data.get("bankCode"),
            "bank_name": sub_pocket_data.get("bankName"),
            "business_name": original_params["business_name"],
            "owner_first_name": original_params["first_name"],
            "owner_last_name": original_params["last_name"],
            "owner_email": original_params["email_address"],
            "owner_phone": original_params["phone_number"],
            "tag_group": original_params.get("tag_group", ""),
            "tag_name": original_params.get("tag_name", ""),
            "pocket_function": original_params.get("pocket_function", "BOTH"),
            "currency": original_params.get("currency", "NGN"),
            "department": original_params.get("department", ""),
            "cost_center": original_params.get("cost_center", ""),
            "status": "Active",
            "creation_date": nowdate()
        })
        
        sub_pocket_doc.insert(ignore_permissions=True)
        return sub_pocket_doc


# API endpoints
@frappe.whitelist()
def create_sub_pocket(**kwargs):
    """API endpoint for creating sub-pocket"""
    sub_pocket_ops = SeerBitSubPocketOperations()
    return sub_pocket_ops.create_sub_pocket(**kwargs)


@frappe.whitelist()
def create_department_sub_pocket(department_name):
    """API endpoint for creating department sub-pocket"""
    sub_pocket_ops = SeerBitSubPocketOperations()
    return sub_pocket_ops.create_department_sub_pocket(department_name)


@frappe.whitelist()
def create_cost_center_sub_pocket(cost_center_name):
    """API endpoint for creating cost center sub-pocket"""
    sub_pocket_ops = SeerBitSubPocketOperations()
    return sub_pocket_ops.create_cost_center_sub_pocket(cost_center_name)


@frappe.whitelist()
def bulk_create_department_sub_pockets(company=None):
    """API endpoint for bulk creating department sub-pockets"""
    sub_pocket_ops = SeerBitSubPocketOperations()
    return sub_pocket_ops.bulk_create_department_sub_pockets(company)


@frappe.whitelist()
def get_department_sub_pockets(company=None):
    """Get all department sub-pockets"""
    filters = {"department": ["!=", ""]}
    if company:
        # Filter by departments of the company
        dept_filters = {"company": company} if company else {}
        departments = frappe.get_all("Department", filters=dept_filters, pluck="name")
        if departments:
            filters["department"] = ["in", departments]
        else:
            return []
    
    return frappe.get_all("SeerBit Sub-Pocket", 
                         filters=filters,
                         fields=["name", "sub_pocket_id", "business_name", "bank_account_number", 
                                "department", "status", "creation_date"])


@frappe.whitelist()
def get_cost_center_sub_pockets(company=None):
    """Get all cost center sub-pockets"""
    filters = {"cost_center": ["!=", ""]}
    if company:
        # Filter by cost centers of the company
        cc_filters = {"company": company} if company else {}
        cost_centers = frappe.get_all("Cost Center", filters=cc_filters, pluck="name")
        if cost_centers:
            filters["cost_center"] = ["in", cost_centers]
        else:
            return []
    
    return frappe.get_all("SeerBit Sub-Pocket",
                         filters=filters,
                         fields=["name", "sub_pocket_id", "business_name", "bank_account_number",
                                "cost_center", "status", "creation_date"])
