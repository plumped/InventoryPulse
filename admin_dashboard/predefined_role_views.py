"""
Views for managing predefined roles.
"""

import json
import logging

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render

from accessmanagement.predefined_roles import (
    create_predefined_role, create_all_predefined_roles,
    get_roles_by_category, PREDEFINED_ROLES
)
from core.utils.logging_utils import log_list_view_usage

logger = logging.getLogger('admin_dashboard')


@login_required
@permission_required('auth.view_group', raise_exception=True)
def predefined_roles(request):
    """View and manage predefined roles."""
    log_list_view_usage(request, view_name="predefined_roles")

    # Get roles organized by category
    roles_by_category = get_roles_by_category()

    # Add role_key to each role for the template
    for category, roles in roles_by_category.items():
        for role in roles:
            # Find the role_key for this role if it's not already set
            if not hasattr(role, 'role_key') or not role.role_key:
                for key, config in PREDEFINED_ROLES.items():
                    if config['name'] == role.name:
                        role.role_key = key
                        break

    context = {
        'roles_by_category': roles_by_category,
        'section': 'permissions',
    }

    return render(request, 'admin_dashboard/permissions/predefined_roles.html', context)


@login_required
@permission_required('auth.add_group', raise_exception=True)
def create_all_predefined_roles_view(request):
    """Create or update all predefined roles."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})

    try:
        roles = create_all_predefined_roles()
        logger.info(f"All predefined roles created/updated by {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully created/updated {len(roles)} predefined roles',
            'roles': [{'name': role.name, 'key': key} for key, role in roles.items()]
        })
    except Exception as e:
        logger.error(f"Error creating predefined roles: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@permission_required('auth.add_group', raise_exception=True)
def create_predefined_role_view(request):
    """Create or update a specific predefined role."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'})

    try:
        # Parse the request body as JSON
        data = json.loads(request.body)
        role_key = data.get('role_key')
        
        if not role_key:
            return JsonResponse({'success': False, 'error': 'Role key is required'})
            
        if role_key not in PREDEFINED_ROLES:
            return JsonResponse({'success': False, 'error': f'Unknown role key: {role_key}'})
            
        role = create_predefined_role(role_key)
        logger.info(f"Predefined role '{role.name}' created/updated by {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully created/updated role {role.name}',
            'role_name': role.name,
            'role_key': role_key
        })
    except Exception as e:
        logger.error(f"Error creating predefined role: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})