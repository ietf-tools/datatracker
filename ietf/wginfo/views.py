# Copyright The IETF Trust 2008, All Rights Reserved

from ietf.idtracker.models import Area, AreaStatus, AreaDirector, IETFWG, WGChair
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext, loader
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.sites.models import Site
from ietf.contrib import wizard, form_decorator
from ietf.utils.mail import send_mail_subj
from datetime import datetime

def wg_summary_acronym(request):
    areas = Area.objects.filter(status='1')
    wgs = IETFWG.objects.filter(status='1')
    return HttpResponse(loader.render_to_string('wginfo/summary-by-acronym.txt', {'area_list': areas, 'wg_list': wgs}),mimetype='text/plain; charset=UTF-8')

def wg_summary_area(request):
    wgs = IETFWG.objects.filter(status='1',start_date__isnull=False)
    return HttpResponse(loader.render_to_string('wginfo/summary-by-area.txt', {'wg_list': wgs}),mimetype='text/plain; charset=UTF-8')

def wg_dir(request):
    wgs = IETFWG.objects.filter(status='1',start_date__isnull=False)
    return render_to_response('wginfo/wg-dir.html', {'wg_list': wgs}, RequestContext(request))

def collect_wg_info(acronym):
    wg = get_object_or_404(IETFWG, group_acronym__acronym=acronym)
    return {'wg': wg}

def wg_charter(request, wg="1"):
    return render_to_response('wginfo/wg-charter.html', collect_wg_info(wg), RequestContext(request))

def generate_text_charter(wg):
    text = loader.render_to_string('wginfo/wg-charter.txt',collect_wg_info(wg));
    return text

def wg_charter_txt(request, wg="1"):
    return HttpResponse(generate_text_charter(wg),
                        mimetype='text/plain; charset=UTF-8')

def wg_charters(request):
    wgs = IETFWG.objects.filter(status='1',start_date__isnull=False)
    return HttpResponse(loader.render_to_string('wginfo/1wg-charters.txt', {'wg_list': wgs}),mimetype='text/plain; charset=UTF-8')

def wg_charters_by_acronym(request):
    wgs = IETFWG.objects.filter(status='1',start_date__isnull=False)
    return HttpResponse(loader.render_to_string('wginfo/1wg-charters-by-acronym.txt', {'wg_list': wgs}),mimetype='text/plain; charset=UTF-8')

