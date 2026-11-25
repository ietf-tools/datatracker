# Copyright The IETF Trust 2012-2020, All Rights Reserved

from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

import debug                            # pyflakes:ignore

from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.forms import DBTemplateForm
from ietf.dbtemplate.template import is_group_template, value_names
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role
from ietf.review.template_values import values_class_for_path
from ietf.utils.response import permission_denied


def template_value_names(template):
    """List the names that a group template of type "django" can use.

    The list is empty for other templates, and for a path that no code renders.
    """
    if template.type_id == 'django' and is_group_template(template):
        values_class = values_class_for_path(template.path)
        if values_class is not None:
            return value_names(values_class)
    return []


def group_template_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')
    if not has_role(request.user, "Secretariat") and not (request.user.id and chairs.filter(person__user=request.user).count()):
        permission_denied(request, "You are not authorized to access this view.")

    template_list = DBTemplate.objects.filter(group=group)
    return render(request, 'dbtemplate/template_list.html',
        {'template_list': template_list,
         'group': group,
        })


def group_template_edit(request, acronym, template_id, base_template='dbtemplate/template_edit.html', formclass=DBTemplateForm, extra_context=None):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')
    extra_context = extra_context or {}

    if not has_role(request.user, "Secretariat") and not (request.user.id and chairs.filter(person__user=request.user).count()):
        permission_denied(request, "You are not authorized to access this view.")

    template = get_object_or_404(DBTemplate, id=template_id, group=group)
    if request.method == 'POST':
        form = formclass(instance=template, data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('..')
    else:
        form = formclass(instance=template)

    context = {'template': template,
        'group': group,
        'form': form,
        'value_names': template_value_names(template),
    }
    context.update(extra_context)
    return render(request, base_template, context)

def group_template_show(request, acronym, template_id, base_template='dbtemplate/template_edit.html', extra_context=None):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')
    extra_context = extra_context or {}

    if not has_role(request.user, "Secretariat") and not (request.user.id and chairs.filter(person__user=request.user).count()):
        permission_denied(request, "You are not authorized to access this view.")

    template = get_object_or_404(DBTemplate, id=template_id, group=group)

    context = {'template': template,
        'group': group,
        'value_names': template_value_names(template),
    }
    context.update(extra_context)
    return render(request, base_template, context)
