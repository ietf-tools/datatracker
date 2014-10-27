import datetime
import re
from collections import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404, render, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.db.models import Count
from django.forms.models import modelformset_factory, inlineformset_factory


from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.views import template_edit
from ietf.name.models import NomineePositionStateName, FeedbackTypeName
from ietf.group.models import Group, GroupEvent
from ietf.message.models import Message

from ietf.nomcom.decorators import nomcom_private_key_required
from ietf.nomcom.forms import (NominateForm, FeedbackForm, QuestionnaireForm,
                               MergeForm, NomComTemplateForm, PositionForm,
                               PrivateKeyForm, EditNomcomForm, EditNomineeForm,
                               PendingFeedbackForm, ReminderDatesForm, FullFeedbackFormSet,
                               FeedbackEmailForm)
from ietf.nomcom.models import Position, NomineePosition, Nominee, Feedback, NomCom, ReminderDates
from ietf.nomcom.utils import (get_nomcom_by_year, store_nomcom_private_key,
                               get_hash_nominee_position, send_reminder_to_nominees,
                               HOME_TEMPLATE, NOMINEE_ACCEPT_REMINDER_TEMPLATE,NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE)
from ietf.ietfauth.utils import role_required

def index(request):
    nomcom_list = Group.objects.filter(type__slug='nomcom').order_by('acronym')
    for nomcom in nomcom_list:
        year = nomcom.acronym[6:]
        try:
            year = int(year)
        except ValueError:
            year = None
        nomcom.year = year
        nomcom.label = "%s/%s" % (year, year+1)
        if   year in [ 2005, 2006, 2007, 2008, 2009, 2010 ]:
            nomcom.url = "https://tools.ietf.org/group/nomcom/%02d" % (year % 100)
        elif year in [ 2011, 2012 ]:
            nomcom.url = "https://www.ietf.org/nomcom/%04d" % year
        elif year > 2012:
            nomcom.url = "/nomcom/%04d" % year
        else:
            nomcom.url = None
        if year >= 2002:
            nomcom.ann_url = "/nomcom/ann/#%4d" % year
        else:
            nomcom.ann_url = None
    return render_to_response('nomcom/index.html',
                              {'nomcom_list': nomcom_list,}, RequestContext(request))
    

def year_index(request, year):
    nomcom = get_nomcom_by_year(year)
    home_template = '/nomcom/%s/%s' % (nomcom.group.acronym, HOME_TEMPLATE)
    template = render_to_string(home_template, {})
    return render_to_response('nomcom/year_index.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'selected': 'index',
                               'template': template}, RequestContext(request))

def announcements(request):
    address_re = re.compile("<.*>")
    
    nomcoms = Group.objects.filter(type="nomcom")

    regimes = []
    
    for n in nomcoms:
        e = GroupEvent.objects.filter(group=n, type="changed_state", changestategroupevent__state="active").order_by('time')[:1]
        n.start_year = e[0].time.year if e else 0
        e = GroupEvent.objects.filter(group=n, type="changed_state", changestategroupevent__state="conclude").order_by('time')[:1]
        n.end_year = e[0].time.year if e else n.start_year + 1

        r = n.role_set.select_related().filter(name="chair") 
        chair = None 
        if r: 
            chair = r[0] 

        announcements = Message.objects.filter(related_groups=n).order_by('-time')
        for a in announcements:
            a.to_name = address_re.sub("", a.to)

        if not announcements:
            continue

        regimes.append(dict(chair=chair,
                            announcements=announcements,
                            group=n))

    regimes.sort(key=lambda x: x["group"].start_year, reverse=True)

    return render_to_response("nomcom/announcements.html",
                              { 'curr_chair' : regimes[0]["chair"] if regimes else None,
                                'regimes' : regimes },
                              context_instance=RequestContext(request))

@role_required("Nomcom")
def private_key(request, year):
    nomcom = get_nomcom_by_year(year)
    message = None
    if request.session.get('NOMCOM_PRIVATE_KEY_%s' % year, None):
        message = ('warning', 'You already have a private decryption key set for this session.')
    else:
        message = ('warning', "You don't have a private decryption key set for this session yet")

    back_url = request.GET.get('back_to', reverse('nomcom_private_index', None, args=(year, )))
    if request.method == 'POST':
        form = PrivateKeyForm(data=request.POST)
        if form.is_valid():
            store_nomcom_private_key(request, year, form.cleaned_data.get('key', ''))
            return HttpResponseRedirect(back_url)
    else:
        form = PrivateKeyForm()
    return render_to_response('nomcom/private_key.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'back_url': back_url,
                               'form': form,
                               'message': message,
                               'selected': 'private_key'}, RequestContext(request))


@role_required("Nomcom")
def private_index(request, year):
    nomcom = get_nomcom_by_year(year)
    all_nominee_positions = NomineePosition.objects.get_by_nomcom(nomcom).not_duplicated()
    is_chair = nomcom.group.has_role(request.user, "chair")
    message = None
    if is_chair and request.method == 'POST':
        action = request.POST.get('action')
        nominations_to_modify = request.POST.getlist('selected')
        if nominations_to_modify:
            nominations = all_nominee_positions.filter(id__in=nominations_to_modify)
            if action == "set_as_accepted":
                nominations.update(state='accepted')
                message = ('success', 'The selected nominations have been set as accepted')
            elif action == "set_as_declined":
                nominations.update(state='declined')
                message = ('success', 'The selected nominations have been set as declined')
            elif action == "set_as_pending":
                nominations.update(state='pending')
                message = ('success', 'The selected nominations have been set as pending')
        else:
            message = ('warning', "Please, select some nominations to work with")

    filters = {}
    questionnaire_state = "questionnaire"
    selected_state = request.GET.get('state')
    selected_position = request.GET.get('position')

    if selected_state and not selected_state == questionnaire_state:
        filters['state__slug'] = selected_state

    if selected_position:
        filters['position__id'] = selected_position

    nominee_positions = all_nominee_positions
    if filters:
        nominee_positions = nominee_positions.filter(**filters)

    if selected_state == questionnaire_state:
        nominee_positions = [np for np in nominee_positions if np.questionnaires]

    stats = all_nominee_positions.values('position__name', 'position__id').annotate(total=Count('position'))
    states = list(NomineePositionStateName.objects.values('slug', 'name')) + [{'slug': questionnaire_state, 'name': u'Questionnaire'}]
    positions = set([ n.position for n in all_nominee_positions.order_by('position__name') ])
    for s in stats:
        for state in states:
            if state['slug'] == questionnaire_state:
                s[state['slug']] = Feedback.objects.filter(positions__id=s['position__id'], type='questio').count()
            else:
                s[state['slug']] = all_nominee_positions.filter(position__name=s['position__name'],
                                                                state=state['slug']).count()

    return render_to_response('nomcom/private_index.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'nominee_positions': nominee_positions,
                               'stats': stats,
                               'states': states,
                               'positions': positions,
                               'selected_state': selected_state,
                               'selected_position': selected_position and int(selected_position) or None,
                               'selected': 'index',
                               'is_chair': is_chair,
                               'message': message}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def send_reminder_mail(request, year, type):
    nomcom = get_nomcom_by_year(year)
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym

    if type=='accept':
        interesting_state = 'pending'
        mail_path = nomcom_template_path + NOMINEE_ACCEPT_REMINDER_TEMPLATE
        reminder_description = 'accept (or decline) a nomination'
        selected_tab = 'send_accept_reminder'
        state_description = NomineePositionStateName.objects.get(slug=interesting_state).name
    elif type=='questionnaire':
        interesting_state = 'accepted'
        mail_path = nomcom_template_path + NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE
        reminder_description = 'complete the questionnaire for a nominated position'
        selected_tab = 'send_questionnaire_reminder'
        state_description =  NomineePositionStateName.objects.get(slug=interesting_state).name+' but no questionnaire has been received'
    else:
        raise Http404

    nominees = Nominee.objects.get_by_nomcom(nomcom).not_duplicated().filter(nomineeposition__state=interesting_state).distinct()
    annotated_nominees = []
    for nominee in nominees:
        if type=='accept':
            nominee.interesting_positions = [x.position.name for x in nominee.nomineeposition_set.pending()]
        else:
            nominee.interesting_positions = [x.position.name for x in nominee.nomineeposition_set.accepted().without_questionnaire_response()]
        if nominee.interesting_positions:
            annotated_nominees.append(nominee)

    mail_template = DBTemplate.objects.filter(group=nomcom.group, path=mail_path)
    mail_template = mail_template and mail_template[0] or None
    message = None

    if request.method == 'POST':
        selected_nominees = request.POST.getlist('selected')
        selected_nominees = nominees.filter(id__in=selected_nominees)
        if selected_nominees:
            addrs = send_reminder_to_nominees(selected_nominees,type)
            if addrs:
                message = ('success', 'A copy of "%s" has been sent to %s'%(mail_template.title,", ".join(addrs)))
            else:
                message = ('warning', 'No messages were sent.')
        else:
            message = ('warning', "Please, select at least one nominee")
    return render_to_response('nomcom/send_reminder_mail.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'nominees': annotated_nominees,
                               'mail_template': mail_template,
                               'selected': selected_tab,
                               'reminder_description': reminder_description,
                               'state_description': state_description,
                               'message': message}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def private_merge(request, year):
    nomcom = get_nomcom_by_year(year)
    message = None
    if request.method == 'POST':
        form = MergeForm(request.POST, nomcom=nomcom)
        if form.is_valid():
            form.save()
            message = ('success', 'The emails have been unified')
    else:
        form = MergeForm(nomcom=nomcom)

    return render_to_response('nomcom/private_merge.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'form': form,
                               'message': message,
                               'selected': 'merge'}, RequestContext(request))


def requirements(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    return render_to_response('nomcom/requirements.html',
                              {'nomcom': nomcom,
                               'positions': positions,
                               'year': year,
                               'selected': 'requirements'}, RequestContext(request))


def questionnaires(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    return render_to_response('nomcom/questionnaires.html',
                              {'nomcom': nomcom,
                               'positions': positions,
                               'year': year,
                               'selected': 'questionnaires'}, RequestContext(request))


@login_required
def public_nominate(request, year):
    return nominate(request, year, True)


@role_required("Nomcom")
def private_nominate(request, year):
    return nominate(request, year, False)


def nominate(request, year, public):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    if public:
        template = 'nomcom/public_nominate.html'
    else:
        template = 'nomcom/private_nominate.html'

    if not has_publickey:
            message = ('warning', "This Nomcom is not yet accepting nominations")
            return render_to_response(template,
                              {'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'nominate'}, RequestContext(request))

    message = None
    if request.method == 'POST':
        form = NominateForm(data=request.POST, nomcom=nomcom, user=request.user, public=public)
        if form.is_valid():
            form.save()
            message = ('success', 'Your nomination has been registered. Thank you for the nomination.')
    else:
        form = NominateForm(nomcom=nomcom, user=request.user, public=public)

    return render_to_response(template,
                              {'form': form,
                               'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'nominate'}, RequestContext(request))


@login_required
def public_feedback(request, year):
    return feedback(request, year, True)


@role_required("Nomcom")
def private_feedback(request, year):
    return feedback(request, year, False)


def feedback(request, year, public):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    submit_disabled = True
    nominee = None
    position = None
    selected_nominee = request.GET.get('nominee')
    selected_position = request.GET.get('position')
    if selected_nominee and selected_position:
        nominee = get_object_or_404(Nominee, id=selected_nominee)
        position = get_object_or_404(Position, id=selected_position)
        submit_disabled = False

    positions = Position.objects.get_by_nomcom(nomcom=nomcom).opened()

    if public:
        template = 'nomcom/public_feedback.html'
    else:
        template = 'nomcom/private_feedback.html'

    if not has_publickey:
            message = ('warning', "This Nomcom is not yet accepting comments")
            return render_to_response(template,
                              {'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'feedback'}, RequestContext(request))

    message = None
    if request.method == 'POST':
        form = FeedbackForm(data=request.POST,
                            nomcom=nomcom, user=request.user,
                            public=public, position=position, nominee=nominee)
        if form.is_valid():
            form.save()
            message = ('success', 'Your feedback has been registered.')
    else:
        form = FeedbackForm(nomcom=nomcom, user=request.user, public=public,
                            position=position, nominee=nominee)

    return render_to_response(template,
                              {'form': form,
                               'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'positions': positions,
                               'submit_disabled': submit_disabled,
                               'selected': 'feedback'}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def private_feedback_email(request, year):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    message = None
    template = 'nomcom/private_feedback_email.html'

    if not has_publickey:
            message = ('warning', "This Nomcom is not yet accepting feedback email")
            return render_to_response(template,
                              {'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'feedback_email'}, RequestContext(request))

    form = FeedbackEmailForm(nomcom=nomcom)

    if request.method == 'POST':
        form = FeedbackEmailForm(data=request.POST,
                                 nomcom=nomcom)
        if form.is_valid():
            form.save()
            form = FeedbackEmailForm(nomcom=nomcom)
            message = ('success', 'The feedback email has been registered.')

    return render_to_response(template,
                              {'form': form,
                               'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'feedback_email'}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def private_questionnaire(request, year):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    message = None
    questionnaire_response = None
    template = 'nomcom/private_questionnaire.html'

    if not has_publickey:
            message = ('warning', "This Nomcom is not yet accepting questionnaires")
            return render_to_response(template,
                              {'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'questionnaire'}, RequestContext(request))

    if request.method == 'POST':
        form = QuestionnaireForm(data=request.POST,
                                 nomcom=nomcom, user=request.user)
        if form.is_valid():
            form.save()
            message = ('success', 'The questionnaire response has been registered.')
            questionnaire_response = form.cleaned_data['comments']
            form = QuestionnaireForm(nomcom=nomcom, user=request.user)
    else:
        form = QuestionnaireForm(nomcom=nomcom, user=request.user)

    return render_to_response(template,
                              {'form': form,
                               'questionnaire_response': questionnaire_response,
                               'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'questionnaire'}, RequestContext(request))


def process_nomination_status(request, year, nominee_position_id, state, date, hash):
    valid = get_hash_nominee_position(date, nominee_position_id) == hash
    if not valid:
        return HttpResponseForbidden("Bad hash!")
    expiration_days = getattr(settings, 'DAYS_TO_EXPIRE_NOMINATION_LINK', None)
    if expiration_days:
        request_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:]))
        if datetime.date.today() > (request_date + datetime.timedelta(days=settings.DAYS_TO_EXPIRE_REGISTRATION_LINK)):
            return HttpResponseForbidden("Link expired")

    need_confirmation = True
    nomcom = get_nomcom_by_year(year)
    nominee_position = get_object_or_404(NomineePosition, id=nominee_position_id)
    if nominee_position.state.slug != "pending":
        return HttpResponseForbidden("The nomination already was %s" % nominee_position.state)

    state = get_object_or_404(NomineePositionStateName, slug=state)
    message = ('warning',
        ("Click on 'Save' to set the state of your nomination to %s to %s (this"+
        "is not a final commitment - you can notify us later if you need to change this)") %
        (nominee_position.position.name, state.name))
    if request.method == 'POST':
        nominee_position.state = state
        nominee_position.save()
        need_confirmation = False
        message = message = ('success', 'Your nomination on %s has been set as %s' % (nominee_position.position.name,
                                                                                      state.name))

    return render_to_response('nomcom/process_nomination_status.html',
                              {'message': message,
                               'nomcom': nomcom,
                               'year': year,
                               'nominee_position': nominee_position,
                               'state': state,
                               'need_confirmation': need_confirmation,
                               'selected': 'feedback'}, RequestContext(request))


@role_required("Nomcom")
@nomcom_private_key_required
def view_feedback(request, year):
    nomcom = get_nomcom_by_year(year)
    nominees = Nominee.objects.get_by_nomcom(nomcom).not_duplicated().distinct()
    independent_feedback_types = []
    feedback_types = []
    for ft in FeedbackTypeName.objects.all():
        if ft.slug in settings.NOMINEE_FEEDBACK_TYPES:
            feedback_types.append(ft)
        else:
            independent_feedback_types.append(ft)
    nominees_feedback = {}
    for nominee in nominees:
        nominee_feedback = [(ft.name, nominee.feedback_set.by_type(ft.slug).count()) for ft in feedback_types]
        nominees_feedback.update({nominee: nominee_feedback})
    independent_feedback = [ft.feedback_set.get_by_nomcom(nomcom).count() for ft in independent_feedback_types]

    return render_to_response('nomcom/view_feedback.html',
                              {'year': year,
                               'selected': 'view_feedback',
                               'nominees': nominees,
                               'feedback_types': feedback_types,
                               'independent_feedback_types': independent_feedback_types,
                               'independent_feedback': independent_feedback,
                               'nominees_feedback': nominees_feedback,
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
@nomcom_private_key_required
def view_feedback_pending(request, year):
    nomcom = get_nomcom_by_year(year)
    extra_ids = None
    message = None
    for message in messages.get_messages(request):
        message = ('success', message.message)
    FeedbackFormSet = modelformset_factory(Feedback,
                                           form=PendingFeedbackForm,
                                           extra=0)
    feedbacks = Feedback.objects.filter(type__isnull=True, nomcom=nomcom)

    try:
        default_type = FeedbackTypeName.objects.get(slug=settings.DEFAULT_FEEDBACK_TYPE)
    except FeedbackTypeName.DoesNotExist:
        default_type = None

    extra_step = False
    if request.method == 'POST' and request.POST.get('move_to_default'):
        formset = FeedbackFormSet(request.POST)
        if formset.is_valid():
            for form in formset.forms:
                form.set_nomcom(nomcom, request.user)
                form.move_to_default()
            formset = FeedbackFormSet(queryset=feedbacks)
            for form in formset.forms:
                form.set_nomcom(nomcom, request.user)
            messages.success(request, 'Feedback saved')
            return redirect('nomcom_view_feedback_pending', year=year)
    elif request.method == 'POST' and request.POST.get('end'):
        extra_ids = request.POST.get('extra_ids', None)
        extra_step = True
        formset = FullFeedbackFormSet(request.POST)
        # workaround -- why isn't formset_factory() being used?
        formset.absolute_max = 2000     
        formset.validate_max = False
        for form in formset.forms:
            form.set_nomcom(nomcom, request.user)
        if formset.is_valid():
            formset.save()
            if extra_ids:
                extra = []
                for key in extra_ids.split(','):
                    id, pk_type = key.split(':')
                    feedback = Feedback.objects.get(id=id)
                    feedback.type_id = pk_type
                    extra.append(feedback)
                formset = FullFeedbackFormSet(queryset=Feedback.objects.filter(id__in=[i.id for i in extra]))
                for form in formset.forms:
                    form.set_nomcom(nomcom, request.user, extra)
                extra_ids = None
            else:
                messages.success(request, 'Feedback saved')
                return redirect('nomcom_view_feedback_pending', year=year)
    elif request.method == 'POST':
        formset = FeedbackFormSet(request.POST)
        for form in formset.forms:
            form.set_nomcom(nomcom, request.user)
        if formset.is_valid():
            extra = []
            nominations = []
            moved = 0
            for form in formset.forms:
                if form.instance.type and form.instance.type.slug in settings.NOMINEE_FEEDBACK_TYPES:
                    if form.instance.type.slug == 'nomina':
                        nominations.append(form.instance)
                    else:
                        extra.append(form.instance)
                else:
                    if form.instance.type:
                        moved += 1
                    form.save()
            if extra or nominations:
                extra_step = True
                if nominations:
                    formset = FullFeedbackFormSet(queryset=Feedback.objects.filter(id__in=[i.id for i in nominations]))
                    for form in formset.forms:
                        form.set_nomcom(nomcom, request.user, nominations)
                    extra_ids = ','.join(['%s:%s' % (i.id, i.type.pk) for i in extra])
                else:
                    formset = FullFeedbackFormSet(queryset=Feedback.objects.filter(id__in=[i.id for i in extra]))
                    for form in formset.forms:
                        form.set_nomcom(nomcom, request.user, extra)
                if moved:
                    message = ('success', '%s messages classified. You must enter more information for the following feedback.' % moved)
            else:
                messages.success(request, 'Feedback saved')
                return redirect('nomcom_view_feedback_pending', year=year)
    else:
        formset = FeedbackFormSet(queryset=feedbacks)
        for form in formset.forms:
            form.set_nomcom(nomcom, request.user)
    type_dict = OrderedDict()
    for t in FeedbackTypeName.objects.all().order_by('pk'):
        rest = t.name
        slug = rest[0]
        rest = rest[1:]
        while slug in type_dict and rest:
            slug = rest[0]
            rest = rest[1]
        type_dict[slug] = t
    return render_to_response('nomcom/view_feedback_pending.html',
                              {'year': year,
                               'selected': 'feedback_pending',
                               'formset': formset,
                               'message': message,
                               'extra_step': extra_step,
                               'default_type': default_type,
                               'type_dict': type_dict,
                               'extra_ids': extra_ids,
                               'types': FeedbackTypeName.objects.all().order_by('pk'),
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom")
@nomcom_private_key_required
def view_feedback_unrelated(request, year):
    nomcom = get_nomcom_by_year(year)
    feedback_types = []
    for ft in FeedbackTypeName.objects.exclude(slug__in=settings.NOMINEE_FEEDBACK_TYPES):
        feedback_types.append({'ft': ft,
                               'feedback': ft.feedback_set.get_by_nomcom(nomcom)})

    return render_to_response('nomcom/view_feedback_unrelated.html',
                              {'year': year,
                               'selected': 'view_feedback',
                               'feedback_types': feedback_types,
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom")
@nomcom_private_key_required
def view_feedback_nominee(request, year, nominee_id):
    nomcom = get_nomcom_by_year(year)
    nominee = get_object_or_404(Nominee, id=nominee_id)
    feedback_types = FeedbackTypeName.objects.filter(slug__in=settings.NOMINEE_FEEDBACK_TYPES)

    return render_to_response('nomcom/view_feedback_nominee.html',
                              {'year': year,
                               'selected': 'view_feedback',
                               'nominee': nominee,
                               'feedback_types': feedback_types,
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_nominee(request, year, nominee_id):
    nomcom = get_nomcom_by_year(year)
    nominee = get_object_or_404(Nominee, id=nominee_id)
    message = None

    if request.method == 'POST':
        form = EditNomineeForm(request.POST,
                               instance=nominee)
        if form.is_valid():
            form.save()
            message = ('success', 'The nominee has been changed')
    else:
        form = EditNomineeForm(instance=nominee)

    return render_to_response('nomcom/edit_nominee.html',
                              {'year': year,
                               'selected': 'index',
                               'nominee': nominee,
                               'form': form,
                               'message': message,
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_nomcom(request, year):
    nomcom = get_nomcom_by_year(year)

    if nomcom.public_key:
        message = ('warning', 'Previous data will remain encrypted with the old key')
    else:
        message = ('warning', 'The nomcom has not a public key yet')

    ReminderDateInlineFormSet = inlineformset_factory(parent_model=NomCom,
                                                      model=ReminderDates,
                                                      form=ReminderDatesForm)
    if request.method == 'POST':
        formset = ReminderDateInlineFormSet(request.POST, instance=nomcom)
        form = EditNomcomForm(request.POST,
                              request.FILES,
                              instance=nomcom)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            formset = ReminderDateInlineFormSet(instance=nomcom)
            message = ('success', 'The nomcom has been changed')
    else:
        formset = ReminderDateInlineFormSet(instance=nomcom)
        form = EditNomcomForm(instance=nomcom)

    return render_to_response('nomcom/edit_nomcom.html',
                              {'form': form,
                               'formset': formset,
                               'nomcom': nomcom,
                               'message': message,
                               'year': year,
                               'selected': 'edit_nomcom'}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def delete_nomcom(request, year):
    nomcom = get_nomcom_by_year(year)

    if request.method == 'POST':
        nomcom.delete()
        messages.success(request, "Deleted NomCom data")
        return redirect('nomcom_deleted')

    return render(request, 'nomcom/delete_nomcom.html', {
        'year': year,
        'selected': 'edit_nomcom',
        'nomcom': nomcom,
    })


@role_required("Nomcom Chair", "Nomcom Advisor")
def list_templates(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    template_list = DBTemplate.objects.filter(group=nomcom.group).exclude(path__contains='/position/')

    return render_to_response('nomcom/list_templates.html',
                              {'template_list': template_list,
                               'positions': positions,
                               'year': year,
                               'selected': 'edit_templates',
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_template(request, year, template_id):
    nomcom = get_nomcom_by_year(year)
    return_url = request.META.get('HTTP_REFERER', None)

    return template_edit(request, nomcom.group.acronym, template_id,
                         base_template='nomcom/edit_template.html',
                         formclass=NomComTemplateForm,
                         extra_context={'year': year,
                                        'return_url': return_url,
                                        'nomcom': nomcom})


@role_required("Nomcom Chair", "Nomcom Advisor")
def list_positions(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()

    return render_to_response('nomcom/list_positions.html',
                              {'positions': positions,
                               'year': year,
                               'selected': 'edit_positions',
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def remove_position(request, year, position_id):
    nomcom = get_nomcom_by_year(year)
    try:
        position = nomcom.position_set.get(id=position_id)
    except Position.DoesNotExist:
        raise Http404

    if request.POST.get('remove', None):
        position.delete()
        return redirect('nomcom_list_positions', year=year)
    return render_to_response('nomcom/remove_position.html',
                              {'year': year,
                               'position': position,
                               'nomcom': nomcom}, RequestContext(request))


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_position(request, year, position_id=None):
    nomcom = get_nomcom_by_year(year)
    if position_id:
        try:
            position = nomcom.position_set.get(id=position_id)
        except Position.DoesNotExist:
            raise Http404
    else:
        position = None

    if request.method == 'POST':
        form = PositionForm(request.POST, instance=position, nomcom=nomcom)
        if form.is_valid():
            form.save()
            return redirect('nomcom_list_positions', year=year)
    else:
        form = PositionForm(instance=position, nomcom=nomcom)

    return render_to_response('nomcom/edit_position.html',
                              {'form': form,
                               'position': position,
                               'year': year,
                               'nomcom': nomcom}, RequestContext(request))
