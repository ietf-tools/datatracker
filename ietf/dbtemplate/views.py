from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.forms import DBTemplateForm
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role


def template_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')
    if not has_role(request.user, "Secretariat") and not chairs.filter(person__user=request.user).count():
        return HttpResponseForbidden("You are not authorized to access this view")

    template_list = DBTemplate.objects.filter(group=group)
    return render(request, 'dbtemplate/template_list.html',
        {'template_list': template_list,
         'group': group,
        })


def template_edit(request, acronym, template_id, base_template='dbtemplate/template_edit.html', formclass=DBTemplateForm, extra_context=None):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')
    extra_context = extra_context or {}

    if not has_role(request.user, "Secretariat") and not chairs.filter(person__user=request.user).count():
        return HttpResponseForbidden("You are not authorized to access this view")

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
    }
    context.update(extra_context)
    return render(request, base_template, context)

def template_show(request, acronym, template_id, base_template='dbtemplate/template_edit.html', extra_context=None):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')
    extra_context = extra_context or {}

    if not has_role(request.user, "Secretariat") and not chairs.filter(person__user=request.user).count():
        return HttpResponseForbidden("You are not authorized to access this view")

    template = get_object_or_404(DBTemplate, id=template_id, group=group)

    context = {'template': template,
        'group': group,
    }
    context.update(extra_context)
    return render(request, base_template, context)
