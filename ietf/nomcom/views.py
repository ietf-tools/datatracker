# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime
import re
from collections import OrderedDict, Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.forms.models import modelformset_factory, inlineformset_factory
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_text


from ietf.dbtemplate.models import DBTemplate
from ietf.dbtemplate.views import group_template_edit, group_template_show
from ietf.name.models import NomineePositionStateName, FeedbackTypeName
from ietf.group.models import Group, GroupEvent, Role 
from ietf.message.models import Message

from ietf.nomcom.decorators import nomcom_private_key_required
from ietf.nomcom.forms import (NominateForm, NominateNewPersonForm, FeedbackForm, QuestionnaireForm,
                               MergeNomineeForm, MergePersonForm, NomComTemplateForm, PositionForm,
                               PrivateKeyForm, EditNomcomForm, EditNomineeForm,
                               PendingFeedbackForm, ReminderDatesForm, FullFeedbackFormSet,
                               FeedbackEmailForm, NominationResponseCommentForm, TopicForm,
                               NewEditMembersForm,)
from ietf.nomcom.models import (Position, NomineePosition, Nominee, Feedback, NomCom, ReminderDates,
                                FeedbackLastSeen, Topic, TopicFeedbackLastSeen, )
from ietf.nomcom.utils import (get_nomcom_by_year, store_nomcom_private_key,
                               get_hash_nominee_position, send_reminder_to_nominees, list_eligible,
                               HOME_TEMPLATE, NOMINEE_ACCEPT_REMINDER_TEMPLATE,NOMINEE_QUESTIONNAIRE_REMINDER_TEMPLATE, )

from ietf.ietfauth.utils import role_required
from ietf.person.models import Person
from ietf.utils.response import permission_denied

import debug                  # pyflakes:ignore

def index(request):
    nomcom_list = Group.objects.filter(type__slug='nomcom').order_by('acronym')
    for nomcom in nomcom_list:
        year = int(nomcom.acronym[6:])
        nomcom.year = year
        nomcom.label = "%s/%s" % (year, year+1)
        if year > 2012:
            nomcom.url = "/nomcom/%04d" % year
        else:
            nomcom.url = None
        if year >= 2002:
            nomcom.ann_url = "/nomcom/ann/#%4d" % year
        else:
            nomcom.ann_url = None
    return render(request, 'nomcom/index.html',
                              {'nomcom_list': nomcom_list,})


def year_index(request, year):
    nomcom = get_nomcom_by_year(year)
    home_template = '/nomcom/%s/%s' % (nomcom.group.acronym, HOME_TEMPLATE)
    template = render_to_string(home_template, {})
    return render(request, 'nomcom/year_index.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'selected': 'index',
                               'template': template})

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

    return render(request, "nomcom/announcements.html",
                           {
                               'curr_chair' : regimes[0]["chair"] if regimes else None,
                               'regimes' : regimes,
                           },
                       )

def history(request):
    nomcom_list = Group.objects.filter(type__slug='nomcom').order_by('acronym')

    regimes = []

    for nomcom in nomcom_list:
        year = int(nomcom.acronym[6:])
        if year > 2012:
            personnel = {}
            for r in Role.objects.filter(group=nomcom).order_by('person__name').select_related("email", "person", "name"):
                if r.name_id not in personnel:
                    personnel[r.name_id] = []
                personnel[r.name_id].append(r)

            nomcom.personnel = []
            for role_name_slug, roles in personnel.items():
                label = roles[0].name.name
                if len(roles) > 1:
                    if label.endswith("y"):
                        label = label[:-1] + "ies"
                    else:
                        label += "s"

                nomcom.personnel.append((role_name_slug, label, roles))

            nomcom.personnel.sort(key=lambda t: t[2][0].name.order)

            regimes.append(dict(year=year, label="%s/%s" % (year, year+1), nomcom=nomcom))

    regimes.sort(key=lambda x: x['year'], reverse=True)

    return render(request, "nomcom/history.html", {'nomcom_list': nomcom_list,
                            'regimes': regimes})

@role_required("Nomcom")
def private_key(request, year):
    nomcom = get_nomcom_by_year(year)
    
    back_url = request.GET.get('back_to', reverse('ietf.nomcom.views.private_index', None, args=(year, )))
    if request.method == 'POST':
        form = PrivateKeyForm(data=request.POST)
        if form.is_valid():
            store_nomcom_private_key(request, year, force_bytes(form.cleaned_data.get('key', '')))
            return HttpResponseRedirect(back_url)
    else:
        form = PrivateKeyForm()

    if request.session.get('NOMCOM_PRIVATE_KEY_%s' % year, None):
        messages.warning(request, 'You already have a private decryption key set for this session.')
    else:
        messages.warning(request, "You don't have a private decryption key set for this session yet")

    return render(request, 'nomcom/private_key.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'back_url': back_url,
                               'form': form,
                               'selected': 'private_key'})


@role_required("Nomcom")
def private_index(request, year):
    nomcom = get_nomcom_by_year(year)
    all_nominee_positions = NomineePosition.objects.get_by_nomcom(nomcom).not_duplicated()
    is_chair = nomcom.group.has_role(request.user, "chair")
    if is_chair and request.method == 'POST':
        if nomcom.group.state_id != 'active':
            messages.warning(request, "This nomcom is not active. Request administrative assistance if Nominee state needs to change.")
        else:
            action = request.POST.get('action')
            nominations_to_modify = request.POST.getlist('selected')
            if nominations_to_modify:
                nominations = all_nominee_positions.filter(id__in=nominations_to_modify)
                if action == "set_as_accepted":
                    nominations.update(state='accepted')
                    messages.success(request,'The selected nominations have been set as accepted')
                elif action == "set_as_declined":
                    nominations.update(state='declined')
                    messages.success(request,'The selected nominations have been set as declined')
                elif action == "set_as_pending":
                    nominations.update(state='pending')
                    messages.success(request,'The selected nominations have been set as pending')
            else:
                messages.warning(request, "Please, select some nominations to work with")

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

    positions = Position.objects.get_by_nomcom(nomcom=nomcom)
    stats = [ { 'position__name':p.name,
                'position__id':p.pk,
                'position': p,
              } for p in positions]
    states = list(NomineePositionStateName.objects.values('slug', 'name')) + [{'slug': questionnaire_state, 'name': 'Questionnaire'}]
    positions = set([ n.position for n in all_nominee_positions.order_by('position__name') ])
    for s in stats:
        for state in states:
            if state['slug'] == questionnaire_state:
                s[state['slug']] = Feedback.objects.filter(positions__id=s['position__id'], type='questio').count()
            else:
                s[state['slug']] = all_nominee_positions.filter(position__name=s['position__name'],
                                                                state=state['slug']).count()
        s['nominations'] = Feedback.objects.filter(positions__id=s['position__id'], type='nomina').count()
        s['nominees'] = all_nominee_positions.filter(position__name=s['position__name']).count()
        s['comments'] = Feedback.objects.filter(positions__id=s['position__id'], type='comment').count()

    totals = dict()
    totals['nominations'] = Feedback.objects.filter(nomcom=nomcom, type='nomina').count()
    totals['nominees'] = all_nominee_positions.count()
    for state in states:
        if state['slug'] == questionnaire_state:
            totals[state['slug']] = Feedback.objects.filter(nomcom=nomcom, type='questio').count()
        else:
            totals[state['slug']] = all_nominee_positions.filter(state=state['slug']).count()
    totals['comments'] = Feedback.objects.filter(nomcom=nomcom, type='comment', positions__isnull=False).count()
    totals['open'] = nomcom.position_set.filter(is_open=True).count()
    totals['accepting_nominations'] = nomcom.position_set.filter(accepting_nominations=True).count()
    totals['accepting_feedback'] = nomcom.position_set.filter(accepting_feedback=True).count()

    unique_totals = dict()
    unique_totals['nominees'] = Person.objects.filter(nominee__nomcom=nomcom).distinct().count()
    for state in states:
        if state['slug'] != questionnaire_state:
            unique_totals[state['slug']] = len(set(all_nominee_positions.filter(state=state['slug']).values_list('nominee__person',flat=True)))

    return render(request, 'nomcom/private_index.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'nominee_positions': nominee_positions,
                               'stats': stats,
                               'totals': totals,
                               'unique_totals': unique_totals,
                               'states': states,
                               'positions': positions,
                               'selected_state': selected_state,
                               'selected_position': selected_position and int(selected_position) or None,
                               'selected': 'index',
                               'is_chair': is_chair,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def send_reminder_mail(request, year, type):
    nomcom = get_nomcom_by_year(year)
    nomcom_template_path = '/nomcom/%s/' % nomcom.group.acronym

    has_publickey = nomcom.public_key and True or False
    if not has_publickey:
        messages.warning(request, "This Nomcom does not yet have a public key.")
        nomcom_ready = False
    elif nomcom.group.state_id != 'active':
        messages.warning(request, "This Nomcom is not active.")
        nomcom_ready = False
    else:
        nomcom_ready = True

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

    if request.method == 'POST' and nomcom_ready:
        selected_nominees = request.POST.getlist('selected')
        selected_nominees = nominees.filter(id__in=selected_nominees)
        if selected_nominees:
            addrs = send_reminder_to_nominees(selected_nominees,type)
            if addrs:
                messages.success(request, 'A copy of "%s" has been sent to %s'%(mail_template.title,", ".join(addrs)))
            else:
                messages.warning(request, 'No messages were sent.')
        else:
            messages.warning(request, "Please, select at least one nominee")

    return render(request, 'nomcom/send_reminder_mail.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'nominees': annotated_nominees,
                               'mail_template': mail_template,
                               'selected': selected_tab,
                               'reminder_description': reminder_description,
                               'state_description': state_description,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def private_merge_person(request, year):
    nomcom = get_nomcom_by_year(year)
    if nomcom.group.state_id != 'active':
        messages.warning(request, "This Nomcom is not active.")
        form = None
    else:
        if request.method == 'POST':
            form = MergePersonForm(request.POST, nomcom=nomcom )
            if form.is_valid():
                form.save()
                messages.success(request, 'A merge request has been sent to the secretariat.')
                return redirect('ietf.nomcom.views.private_index',year=year)
        else:
            form = MergePersonForm(nomcom=nomcom)

    return render(request, 'nomcom/private_merge_person.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'form': form,
                               'selected': 'merge_person',
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def private_merge_nominee(request, year):
    nomcom = get_nomcom_by_year(year)
    if nomcom.group.state_id != 'active':
        messages.warning(request, "This Nomcom is not active.")
        form = None
    else:
        if request.method == 'POST':
            form = MergeNomineeForm(request.POST, nomcom=nomcom )
            if form.is_valid():
                form.save()
                messages.success(request, 'The Nominee records have been joined.')
                return redirect('ietf.nomcom.views.private_index',year=year)
        else:
            form = MergeNomineeForm(nomcom=nomcom)

    return render(request, 'nomcom/private_merge_nominee.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'form': form,
                               'selected': 'merge_nominee',
                               'is_chair_task' : True,
                              })

def requirements(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    return render(request, 'nomcom/requirements.html',
                              {'nomcom': nomcom,
                               'positions': positions,
                               'year': year,
                               'selected': 'requirements'})


def questionnaires(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.all()
    return render(request, 'nomcom/questionnaires.html',
                              {'nomcom': nomcom,
                               'positions': positions,
                               'year': year,
                               'selected': 'questionnaires'})


@login_required
def public_nominate(request, year):
    return nominate(request=request, year=year, public=True, newperson=False)


@role_required("Nomcom")
def private_nominate(request, year):
    return nominate(request=request, year=year, public=False, newperson=False)

@login_required
def public_nominate_newperson(request, year):
    return nominate(request=request, year=year, public=True, newperson=True)


@role_required("Nomcom")
def private_nominate_newperson(request, year):
    return nominate(request=request, year=year, public=False, newperson=True)


def nominate(request, year, public, newperson):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    if public:
        template = 'nomcom/public_nominate.html'
    else:
        template = 'nomcom/private_nominate.html'

    if not has_publickey:
        messages.warning(request, "This Nomcom is not yet accepting nominations")
        return render(request, template,
                              {'nomcom': nomcom,
                               'year': year,
                               'selected': 'nominate'})

    if nomcom.group.state_id == 'conclude':
        messages.warning(request, "Nominations to this Nomcom are closed.")
        return render(request, template,
                              {'nomcom': nomcom,
                               'year': year,
                               'selected': 'nominate'})

    if request.method == 'POST':
        if newperson:
            form = NominateNewPersonForm(data=request.POST, nomcom=nomcom, user=request.user, public=public)
        else:
            form = NominateForm(data=request.POST, nomcom=nomcom, user=request.user, public=public)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your nomination has been registered. Thank you for the nomination.')
            if newperson:
                return redirect('ietf.nomcom.views.%s_nominate' % ('public' if public else 'private'), year=year)
            else:
                form = NominateForm(nomcom=nomcom, user=request.user, public=public)
    else:
        if newperson:
            form = NominateNewPersonForm(nomcom=nomcom, user=request.user, public=public)
        else:
            form = NominateForm(nomcom=nomcom, user=request.user, public=public)

    return render(request, template,
                              {'form': form,
                               'nomcom': nomcom,
                               'year': year,
                               'positions': nomcom.position_set.filter(is_open=True),
                               'selected': 'nominate'})

@login_required
def public_feedback(request, year):
    return feedback(request, year, True)


@role_required("Nomcom")
def private_feedback(request, year):
    return feedback(request, year, False)


def feedback(request, year, public):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    nominee = None
    position = None
    topic = None
    if nomcom.group.state_id != 'conclude':
        selected_nominee = request.GET.get('nominee')
        selected_position = request.GET.get('position')
        if selected_nominee and selected_position:
            nominee = get_object_or_404(Nominee, id=selected_nominee)
            position = get_object_or_404(Position, id=selected_position)
        selected_topic = request.GET.get('topic')
        if selected_topic:
            topic = get_object_or_404(Topic,id=selected_topic)
            if topic.audience_id == 'nomcom' and not nomcom.group.has_role(request.user, ['chair','advisor','liaison','member']):
                raise Http404()
            if topic.audience_id == 'nominees' and not nomcom.nominee_set.filter(person=request.user.person).exists():
                raise Http404()

    if public:
        positions = Position.objects.get_by_nomcom(nomcom=nomcom).filter(is_open=True,accepting_feedback=True)
        topics = Topic.objects.filter(nomcom=nomcom,accepting_feedback=True)
    else:
        positions = Position.objects.get_by_nomcom(nomcom=nomcom).filter(is_open=True)
        topics = Topic.objects.filter(nomcom=nomcom)

    if not nomcom.group.has_role(request.user, ['chair','advisor','liaison','member']):
        topics = topics.exclude(audience_id='nomcom')
    if not nomcom.nominee_set.filter(person=request.user.person).exists():
        topics = topics.exclude(audience_id='nominees')

    user_comments = Feedback.objects.filter(nomcom=nomcom,
                                            type='comment',
                                            author__in=request.user.person.email_set.filter(active='True')) 
    counter = Counter(user_comments.values_list('positions','nominees'))
    counts = dict()
    for pos,nom in counter:
        counts.setdefault(pos,dict())[nom] = counter[(pos,nom)]

    topic_counts = Counter(user_comments.values_list('topics',flat=True))

    if public:
        base_template = "nomcom/nomcom_public_base.html"
    else:
        base_template = "nomcom/nomcom_private_base.html"

    if not has_publickey:
            messages.warning(request, "This Nomcom is not yet accepting comments")
            return render(request, 'nomcom/feedback.html', {
                'nomcom': nomcom,
                'year': year,
                'selected': 'feedback',
                'counts' : counts,
                'base_template': base_template
            })

    if public and position and not (position.is_open and position.accepting_feedback):
            messages.warning(request, "This Nomcom is not currently accepting feedback for "+position.name)
            return render(request, 'nomcom/feedback.html', {
                'form': None,
                'nomcom': nomcom,
                'year': year,
                'selected': 'feedback',
                'positions': positions,
                'topics': topics,
                'counts' : counts,
                'topic_counts' : topic_counts,
                'base_template': base_template
            })

    if public and topic and not topic.accepting_feedback:
            messages.warning(request, "This Nomcom is not currently accepting feedback for "+topic.subject)
            return render(request, 'nomcom/feedback.html', {
                'form': None,
                'nomcom': nomcom,
                'year': year,
                'selected': 'feedback',
                'positions': positions,
                'topics': topics,
                'counts' : counts,
                'topic_counts' : topic_counts,
                'base_template': base_template
            })
    if request.method == 'POST':
        if nominee and position:
            form = FeedbackForm(data=request.POST,
                                nomcom=nomcom, user=request.user,
                                public=public, position=position, nominee=nominee)
        elif topic:
            form = FeedbackForm(data=request.POST,
                                nomcom=nomcom, user=request.user,
                                public=public, topic=topic)
        else:
            form = None
        if form and form.is_valid():
            form.save()
            messages.success(request, 'Your feedback has been registered.')
            form = None
            if position:
                counts.setdefault(position.pk,dict())
                counts[position.pk].setdefault(nominee.pk,0)
                counts[position.pk][nominee.pk] += 1
            elif topic:
                topic_counts.setdefault(topic.pk,0)
                topic_counts[topic.pk] += 1
            else:
                pass
    else:
        if nominee and position:
            form = FeedbackForm(nomcom=nomcom, user=request.user, public=public,
                                position=position, nominee=nominee)
        elif topic:
            form = FeedbackForm(nomcom=nomcom, user=request.user, public=public,
                                topic=topic)
        else:
            form = None

    return render(request, 'nomcom/feedback.html', {
        'form': form,
        'nomcom': nomcom,
        'year': year,
        'positions': positions,
        'topics': topics,
        'selected': 'feedback',
        'counts': counts,
        'topic_counts': topic_counts,
        'base_template': base_template
    })


@role_required("Nomcom Chair", "Nomcom Advisor")
def private_feedback_email(request, year):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    template = 'nomcom/private_feedback_email.html'

    if not has_publickey:
        messages.warning(request, "This Nomcom is not yet accepting feedback email.")
        nomcom_ready = False
    elif nomcom.group.state_id != 'active':
        messages.warning(request, "This Nomcom is not active, and is not accepting feedback email.")
        nomcom_ready = False
    else:
        nomcom_ready = True
        
    if not nomcom_ready:
        return render(request, template,
                          {'nomcom': nomcom,
                           'year': year,
                           'selected': 'feedback_email',
                           'is_chair_task' : True,
                          })

    form = FeedbackEmailForm(nomcom=nomcom)

    if request.method == 'POST':
        form = FeedbackEmailForm(data=request.POST,
                                 nomcom=nomcom)
        if form.is_valid():
            form.save()
            form = FeedbackEmailForm(nomcom=nomcom)
            messages.success(request, 'The feedback email has been registered.')

    return render(request, template,
                              {'form': form,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'feedback_email'})

@role_required("Nomcom Chair", "Nomcom Advisor")
def private_questionnaire(request, year):
    nomcom = get_nomcom_by_year(year)
    has_publickey = nomcom.public_key and True or False
    questionnaire_response = None
    template = 'nomcom/private_questionnaire.html'

    if not has_publickey:
        messages.warning(request, "This Nomcom is not yet accepting questionnaires.")
        nomcom_ready = False
    elif nomcom.group.state_id != 'active':
        messages.warning(request, "This Nomcom is not active, and is not accepting questionnaires.")
        nomcom_ready = False
    else:
        nomcom_ready = True
        
    if not nomcom_ready:
        return render(request, template,
                          {'nomcom': nomcom,
                           'year': year,
                           'selected': 'questionnaire',
                           'is_chair_task' : True,
                          })

    if request.method == 'POST':
        form = QuestionnaireForm(data=request.POST,
                                 nomcom=nomcom, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'The questionnaire response has been registered.')
            questionnaire_response = force_text(form.cleaned_data['comment_text'])
            form = QuestionnaireForm(nomcom=nomcom, user=request.user)
    else:
        form = QuestionnaireForm(nomcom=nomcom, user=request.user)

    return render(request, template,
                              {'form': form,
                               'questionnaire_response': questionnaire_response,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'questionnaire'})


def process_nomination_status(request, year, nominee_position_id, state, date, hash):
    valid = get_hash_nominee_position(date, nominee_position_id) == hash
    if not valid:
        permission_denied(request, "Bad hash!")
    expiration_days = getattr(settings, 'DAYS_TO_EXPIRE_NOMINATION_LINK', None)
    if expiration_days:
        request_date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:]))
        if datetime.date.today() > (request_date + datetime.timedelta(days=settings.DAYS_TO_EXPIRE_NOMINATION_LINK)):
            permission_denied(request, "Link expired.")

    need_confirmation = True
    nomcom = get_nomcom_by_year(year)
    if nomcom.group.state_id == 'conclude':
        permission_denied(request, "This nomcom is concluded.")
    nominee_position = get_object_or_404(NomineePosition, id=nominee_position_id)
    if nominee_position.state.slug != "pending":
        permission_denied(request, "The nomination already was %s" % nominee_position.state)

    state = get_object_or_404(NomineePositionStateName, slug=state)
    messages.info(request, "Click on 'Save' to set the state of your nomination to %s to %s (this is not a final commitment - you can notify us later if you need to change this)." % (nominee_position.position.name, state.name))
    if request.method == 'POST':
        form = NominationResponseCommentForm(request.POST)
        if form.is_valid():
            nominee_position.state = state
            nominee_position.save()
            need_confirmation = False
            if form.cleaned_data['comments']:
                # This Feedback object is of type comment instead of nomina in order to not
                # make answering "who nominated themselves" harder.
                who = request.user
                if isinstance(who,AnonymousUser):
                    who = None
                f = Feedback.objects.create(nomcom = nomcom,
                                            author = nominee_position.nominee.email,
                                            subject = '%s nomination %s'%(nominee_position.nominee.name(),state),
                                            comments = nomcom.encrypt(form.cleaned_data['comments']),
                                            type_id = 'comment', 
                                            user = who,
                                           )
                f.positions.add(nominee_position.position)
                f.nominees.add(nominee_position.nominee)
        
            messages.success(request,  'Your nomination on %s has been set as %s' % (nominee_position.position.name, state.name))
    else:
        form = NominationResponseCommentForm()
    return render(request, 'nomcom/process_nomination_status.html',
                              {'nomcom': nomcom,
                               'year': year,
                               'nominee_position': nominee_position,
                               'state': state,
                               'need_confirmation': need_confirmation,
                               'selected': 'feedback',
                               'form': form })


@role_required("Nomcom")
@nomcom_private_key_required
def view_feedback(request, year):
    nomcom = get_nomcom_by_year(year)
    nominees = Nominee.objects.get_by_nomcom(nomcom).not_duplicated().distinct()
    independent_feedback_types = []
    nominee_feedback_types = []
    for ft in FeedbackTypeName.objects.all():
        if ft.slug in settings.NOMINEE_FEEDBACK_TYPES:
            nominee_feedback_types.append(ft)
        else:
            independent_feedback_types.append(ft)
    topic_feedback_types=FeedbackTypeName.objects.filter(slug='comment')
    nominees_feedback = []
    topics_feedback = []

    def nominee_staterank(nominee):
        states=nominee.nomineeposition_set.values_list('state_id',flat=True)
        if 'accepted' in states:
            return 0
        elif 'pending' in states:
            return 1
        else:
            return 2

    for nominee in nominees:
        nominee.staterank = nominee_staterank(nominee)

    sorted_nominees = sorted(nominees,key=lambda x:x.staterank)

    for nominee in sorted_nominees:
        last_seen = FeedbackLastSeen.objects.filter(reviewer=request.user.person,nominee=nominee).first()
        nominee_feedback = []
        for ft in nominee_feedback_types:
            qs = nominee.feedback_set.by_type(ft.slug)
            count = qs.count()
            if not count:
                newflag = False
            elif not last_seen:
                newflag = True
            else:
                newflag = qs.filter(time__gt=last_seen.time).exists()
            nominee_feedback.append( (ft.name,count,newflag) )
        nominees_feedback.append( {'nominee':nominee, 'feedback':nominee_feedback} )
    independent_feedback = [ft.feedback_set.get_by_nomcom(nomcom).count() for ft in independent_feedback_types]
    for topic in nomcom.topic_set.all():
        last_seen = TopicFeedbackLastSeen.objects.filter(reviewer=request.user.person,topic=topic).first()
        topic_feedback = []
        for ft in topic_feedback_types:
            qs = topic.feedback_set.by_type(ft.slug)
            count = qs.count()
            if not count: 
                newflag = False
            elif not last_seen:
                newflag = True
            else:
                newflag = qs.filter(time__gt=last_seen.time).exists()
            topic_feedback.append( (ft.name,count,newflag) )
        topics_feedback.append ( {'topic':topic, 'feedback':topic_feedback} )

    return render(request, 'nomcom/view_feedback.html',
                              {'year': year,
                               'selected': 'view_feedback',
                               'nominees': nominees,
                               'nominee_feedback_types': nominee_feedback_types,
                               'independent_feedback_types': independent_feedback_types,
                               'topic_feedback_types': topic_feedback_types,
                               'topics_feedback': topics_feedback,
                               'independent_feedback': independent_feedback,
                               'nominees_feedback': nominees_feedback,
                               'nomcom': nomcom})


@role_required("Nomcom Chair", "Nomcom Advisor")
@nomcom_private_key_required
def view_feedback_pending(request, year):
    nomcom = get_nomcom_by_year(year)
    if nomcom.group.state_id == 'conclude':
        permission_denied(request, "This nomcom is concluded.")
    extra_ids = None
    FeedbackFormSet = modelformset_factory(Feedback,
                                           form=PendingFeedbackForm,
                                           extra=0)
    feedback_list = Feedback.objects.filter(type__isnull=True, nomcom=nomcom).order_by('-time')
    paginator = Paginator(feedback_list, 20)
    page_num = request.GET.get('page')
    try:
        feedback_page = paginator.page(page_num)
    except PageNotAnInteger:
        feedback_page = paginator.page(1)
    except EmptyPage:
        feedback_page = paginator.page(paginator.num_pages)
    extra_step = False
    if request.method == 'POST' and request.POST.get('end'):
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
                return redirect('ietf.nomcom.views.view_feedback_pending', year=year)
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
                    messages.success(request, '%s messages classified. You must enter more information for the following feedback.' % moved)
            else:
                messages.success(request, 'Feedback saved')
                return redirect('ietf.nomcom.views.view_feedback_pending', year=year)
    else:
        formset = FeedbackFormSet(queryset=feedback_page.object_list)
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
    return render(request, 'nomcom/view_feedback_pending.html',
                              {'year': year,
                               'selected': 'feedback_pending',
                               'formset': formset,
                               'extra_step': extra_step,
                               'type_dict': type_dict,
                               'extra_ids': extra_ids,
                               'types': FeedbackTypeName.objects.all().order_by('pk'),
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                               'page': feedback_page,
                              })


@role_required("Nomcom")
@nomcom_private_key_required
def view_feedback_unrelated(request, year):
    nomcom = get_nomcom_by_year(year)
    feedback_types = []
    for ft in FeedbackTypeName.objects.exclude(slug__in=settings.NOMINEE_FEEDBACK_TYPES):
        feedback_types.append({'ft': ft,
                               'feedback': ft.feedback_set.get_by_nomcom(nomcom)})

    return render(request, 'nomcom/view_feedback_unrelated.html',
                              {'year': year,
                               'selected': 'view_feedback',
                               'feedback_types': feedback_types,
                               'nomcom': nomcom})

@role_required("Nomcom")
@nomcom_private_key_required
def view_feedback_topic(request, year, topic_id):
    nomcom = get_nomcom_by_year(year)
    topic = get_object_or_404(Topic, id=topic_id)
    feedback_types = FeedbackTypeName.objects.filter(slug__in=['comment',])

    last_seen = TopicFeedbackLastSeen.objects.filter(reviewer=request.user.person,topic=topic).first()
    last_seen_time = (last_seen and last_seen.time) or datetime.datetime(year=1,month=1,day=1)
    if last_seen:
        last_seen.save()
    else:
        TopicFeedbackLastSeen.objects.create(reviewer=request.user.person,topic=topic)

    return render(request, 'nomcom/view_feedback_topic.html',
                              {'year': year,
                               'selected': 'view_feedback',
                               'topic': topic,
                               'feedback_types': feedback_types,
                               'last_seen_time' : last_seen_time,
                               'nomcom': nomcom})

@role_required("Nomcom")
@nomcom_private_key_required
def view_feedback_nominee(request, year, nominee_id):
    nomcom = get_nomcom_by_year(year)
    nominee = get_object_or_404(Nominee, id=nominee_id)
    feedback_types = FeedbackTypeName.objects.filter(slug__in=settings.NOMINEE_FEEDBACK_TYPES)

    last_seen = FeedbackLastSeen.objects.filter(reviewer=request.user.person,nominee=nominee).first()
    last_seen_time = (last_seen and last_seen.time) or datetime.datetime(year=1,month=1,day=1)
    if last_seen:
        last_seen.save()
    else:
        FeedbackLastSeen.objects.create(reviewer=request.user.person,nominee=nominee)

    return render(request, 'nomcom/view_feedback_nominee.html',
                              {'year': year,
                               'selected': 'view_feedback',
                               'nominee': nominee,
                               'feedback_types': feedback_types,
                               'last_seen_time' : last_seen_time,
                               'nomcom': nomcom})


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_nominee(request, year, nominee_id):
    nomcom = get_nomcom_by_year(year)
    nominee = get_object_or_404(Nominee, id=nominee_id)

    if request.method == 'POST':
        form = EditNomineeForm(request.POST,
                               instance=nominee)
        if form.is_valid():
            form.save()
            messages.success(request, 'The nomination address for %s has been changed to %s'%(nominee.name(),nominee.email.address))
            return redirect('ietf.nomcom.views.private_index', year=year)
    else:
        form = EditNomineeForm(instance=nominee)

    return render(request, 'nomcom/edit_nominee.html',
                              {'year': year,
                               'selected': 'index',
                               'nominee': nominee,
                               'form': form,
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_nomcom(request, year):
    nomcom = get_nomcom_by_year(year)

    ReminderDateInlineFormSet = inlineformset_factory(parent_model=NomCom,
                                                      model=ReminderDates,
                                                      form=ReminderDatesForm)
    if request.method == 'POST':

        if nomcom.group.state_id=='conclude':
            permission_denied(request, 'This nomcom is closed.')

        formset = ReminderDateInlineFormSet(request.POST, instance=nomcom)
        form = EditNomcomForm(request.POST,
                              request.FILES,
                              instance=nomcom)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            formset = ReminderDateInlineFormSet(instance=nomcom)
            messages.success(request, 'The nomcom has been changed')
    else:
        formset = ReminderDateInlineFormSet(instance=nomcom)
        form = EditNomcomForm(instance=nomcom)

    return render(request, 'nomcom/edit_nomcom.html',
                              {'form': form,
                               'formset': formset,
                               'nomcom': nomcom,
                               'year': year,
                               'selected': 'edit_nomcom',
                               'is_chair_task' : True,
                              })



@role_required("Nomcom Chair", "Nomcom Advisor")
def list_templates(request, year):
    nomcom = get_nomcom_by_year(year)
    template_list = DBTemplate.objects.filter(group=nomcom.group).exclude(path__contains='/position/').exclude(path__contains='/topic/')

    return render(request, 'nomcom/list_templates.html',
                              {'template_list': template_list,
                               'year': year,
                               'selected': 'edit_templates',
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_template(request, year, template_id):
    nomcom = get_nomcom_by_year(year)
    return_url = request.META.get('HTTP_REFERER', None)

    if nomcom.group.state_id=='conclude':
        return group_template_show(request, nomcom.group.acronym, template_id,
                             base_template='nomcom/show_template.html',
                             extra_context={'year': year,
                                            'return_url': return_url,
                                            'nomcom': nomcom,
                                            'is_chair_task' : True,
                                           })
    else:
        return group_template_edit(request, nomcom.group.acronym, template_id,
                             base_template='nomcom/edit_template.html',
                             formclass=NomComTemplateForm,
                             extra_context={'year': year,
                                            'return_url': return_url,
                                            'nomcom': nomcom,
                                            'is_chair_task' : True,
                                           })


@role_required("Nomcom Chair", "Nomcom Advisor")
def list_positions(request, year):
    nomcom = get_nomcom_by_year(year)
    positions = nomcom.position_set.order_by('-is_open')

    return render(request, 'nomcom/list_positions.html',
                              {'positions': positions,
                               'year': year,
                               'selected': 'edit_positions',
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def remove_position(request, year, position_id):
    nomcom = get_nomcom_by_year(year)
    if nomcom.group.state_id=='conclude':
        permission_denied(request, 'This nomcom is closed.')
    try:
        position = nomcom.position_set.get(id=position_id)
    except Position.DoesNotExist:
        raise Http404

    if request.POST.get('remove', None):
        position.delete()
        return redirect('ietf.nomcom.views.list_positions', year=year)
    return render(request, 'nomcom/remove_position.html',
                              {'year': year,
                               'position': position,
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_position(request, year, position_id=None):
    nomcom = get_nomcom_by_year(year)

    if nomcom.group.state_id=='conclude':
        permission_denied(request, 'This nomcom is closed.')

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
            return redirect('ietf.nomcom.views.list_positions', year=year)
    else:
        form = PositionForm(instance=position, nomcom=nomcom)

    return render(request, 'nomcom/edit_position.html',
                              {'form': form,
                               'position': position,
                               'year': year,
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def list_topics(request, year):
    nomcom = get_nomcom_by_year(year)
    topics = nomcom.topic_set.all()

    return render(request, 'nomcom/list_topics.html',
                              {'topics': topics,
                               'year': year,
                               'selected': 'edit_topics',
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def remove_topic(request, year, topic_id):
    nomcom = get_nomcom_by_year(year)
    if nomcom.group.state_id=='conclude':
        permission_denied(request, 'This nomcom is closed.')
    try:
        topic = nomcom.topic_set.get(id=topic_id)
    except Topic.DoesNotExist:
        raise Http404

    if request.POST.get('remove', None):
        topic.delete()
        return redirect('ietf.nomcom.views.list_topics', year=year)
    return render(request, 'nomcom/remove_topic.html',
                              {'year': year,
                               'topic': topic,
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })


@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_topic(request, year, topic_id=None):
    nomcom = get_nomcom_by_year(year)

    if nomcom.group.state_id=='conclude':
        permission_denied(request, 'This nomcom is closed.')

    if topic_id:
        try:
            topic = nomcom.topic_set.get(id=topic_id)
        except Topic.DoesNotExist:
            raise Http404
    else:
        topic = None

    if request.method == 'POST':
        form = TopicForm(request.POST, instance=topic, nomcom=nomcom)
        if form.is_valid():
            form.save()
            return redirect('ietf.nomcom.views.list_topics', year=year)
    else:
        form = TopicForm(instance=topic, nomcom=nomcom,initial={'accepting_feedback':True,'audience':'general'} if not topic else {})

    return render(request, 'nomcom/edit_topic.html',
                              {'form': form,
                               'topic': topic,
                               'year': year,
                               'nomcom': nomcom,
                               'is_chair_task' : True,
                              })

@role_required("Nomcom Chair", "Nomcom Advisor")
def configuration_help(request, year):
    nomcom = get_nomcom_by_year(year)
    return render(request,'nomcom/chair_help.html',{'nomcom':nomcom,'year':year})

@role_required("Nomcom Chair", "Nomcom Advisor")
def edit_members(request, year):
    nomcom = get_nomcom_by_year(year)

    if nomcom.group.state_id=='conclude':
        permission_denied(request, 'This nomcom is closed.')

    old_members_email = [r.email for r in nomcom.group.role_set.filter(name='member')]

    if request.method=='POST':
        form = NewEditMembersForm(data=request.POST)
        if form.is_valid():
            new_members_email = form.cleaned_data['members']
            nomcom.group.role_set.filter( email__in=set(old_members_email)-set(new_members_email) ).delete()
            for email in set(new_members_email)-set(old_members_email):
                nomcom.group.role_set.create(email=email,person=email.person,name_id='member')
            return HttpResponseRedirect(reverse('ietf.nomcom.views.private_index',kwargs={'year':year}))
    else:
        form = NewEditMembersForm(initial={ 'members' : old_members_email })

    return render(request, 'nomcom/new_edit_members.html',
                              {'nomcom' : nomcom,
                               'year' : year,
                               'form': form,
                              })

@role_required("Nomcom Chair", "Nomcom Advisor")
def extract_email_lists(request, year):
    nomcom = get_nomcom_by_year(year)

    pending = nomcom.nominee_set.filter(nomineeposition__state='pending').distinct()
    accepted = nomcom.nominee_set.filter(nomineeposition__state='accepted').distinct()
    noresp = [n for n in accepted if n.nomineeposition_set.without_questionnaire_response().filter(state='accepted')]
    
    bypos = {}
    for pos in nomcom.position_set.all():
        bypos[pos] = nomcom.nominee_set.filter(nomineeposition__position=pos,nomineeposition__state='accepted').distinct()

    return render(request, 'nomcom/extract_email_lists.html',
                             {'nomcom': nomcom,
                              'year' : year,
                              'pending': pending,
                              'accepted': accepted,
                              'noresp': noresp,
                              'bypos': bypos,
                             })

@role_required("Nomcom Chair", "Nomcom Advisor", "Secretariat")
def eligible(request, year):
    nomcom = get_nomcom_by_year(year)

    eligible_persons = list(list_eligible(nomcom=nomcom))
    eligible_persons.sort(key=lambda p: p.last_name() )

    return render(request, 'nomcom/eligible.html',
                             {'nomcom':nomcom,
                              'year':year,
                              'eligible_persons':eligible_persons,
                             })
