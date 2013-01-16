from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext

from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.forms import DBTemplateForm
from ietf.group.models import Group
from ietf.ietfauth.decorators import has_role


def template_list(request, acronym):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')
    if not has_role(request.user, "Secretariat") and not chairs.filter(person__user=request.user).count():
        return HttpResponseForbidden("You are not authorized to access this view")

    template_list = DBTemplate.objects.filter(group=group)
    return render_to_response('dbtemplate/template_list.html',
        {'template_list': template_list,
         'group': group,
        }, RequestContext(request))


def template_edit(request, acronym, template_id):
    group = get_object_or_404(Group, acronym=acronym)
    chairs = group.role_set.filter(name__slug='chair')

    if not has_role(request.user, "Secretariat") and not chairs.filter(person__user=request.user).count():
        return HttpResponseForbidden("You are not authorized to access this view")

    template = get_object_or_404(DBTemplate, id=template_id, group=group)
    if request.method == 'POST':
        form = DBTemplateForm(instance=template, data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('..')
    else:
        form = DBTemplateForm(instance=template)
    return render_to_response('dbtemplate/template_edit.html',
        {'template': template,
         'group': group,
         'form': form,
        }, RequestContext(request))
