# Copyright The IETF Trust 2013-2022, All Rights Reserved
# -*- coding: utf-8 -*-


# various authentication and authorization utilities

import oidc_provider.lib.claims


from functools import wraps, WRAPPER_ASSIGNMENTS
from urllib.parse import quote as urlquote

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.sites.models import Site
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

import debug                            # pyflakes:ignore

from ietf.group.models import Role, GroupFeatures
from ietf.person.models import Email, Person
from ietf.person.utils import get_dots
from ietf.doc.utils_bofreq import bofreq_editors
from ietf.utils.mail import send_mail

def user_is_person(user, person):
    """Test whether user is associated with person."""
    if not user.is_authenticated or not person:
        return False

    if person.user_id == None:
        return False

    return person.user_id == user.id

def has_role(user, role_names, *args, **kwargs):
    """Determines whether user has any of the given standard roles
    given. Role names must be a list or, in case of a single value, a
    string."""
    extra_role_qs = kwargs.get("extra_role_qs", None)
    if not isinstance(role_names, (list, tuple, set)):
        role_names = [role_names]

    if not user or not user.is_authenticated:
        return False

    # use cache to avoid checking the same permissions again and again
    if not hasattr(user, "roles_check_cache"):
        user.roles_check_cache = {}

    keynames = set(role_names)
    if extra_role_qs:
        keynames.update(set(extra_role_qs.keys()))
    year = kwargs.get("year", None)
    if year is not None:
        keynames.add(f"nomcomyear{year}")
    key = frozenset(keynames)
    if key not in user.roles_check_cache:
        try:
            person = user.person
        except Person.DoesNotExist:
            return False

        role_qs = {
            "Area Director": Q(
                name__in=("pre-ad", "ad"), group__type="area", group__state="active"
            ),
            "Secretariat": Q(name="secr", group__acronym="secretariat"),
            "IAB": Q(name="member", group__acronym="iab"),
            "IANA": Q(name="auth", group__acronym="iana"),
            "RFC Editor": Q(name="auth", group__acronym="rpc"),
            "ISE": Q(name="chair", group__acronym="ise"),
            "IAD": Q(name="admdir", group__acronym="ietf"),
            "IETF Chair": Q(name="chair", group__acronym="ietf"),
            "IETF Trust Chair": Q(name="chair", group__acronym="ietf-trust"),
            "IRTF Chair": Q(name="chair", group__acronym="irtf"),
            "RSAB Chair": Q(name="chair", group__acronym="rsab"),
            "IAB Chair": Q(name="chair", group__acronym="iab"),
            "IAB Executive Director": Q(name="execdir", group__acronym="iab"),
            "IAB Group Chair": Q(
                name="chair", group__type="iab", group__state="active"
            ),
            "IAOC Chair": Q(name="chair", group__acronym="iaoc"),
            "WG Chair": Q(
                name="chair",
                group__type="wg",
                group__state__in=["active", "bof", "proposed"],
            ),
            "WG Secretary": Q(
                name="secr",
                group__type="wg",
                group__state__in=["active", "bof", "proposed"],
            ),
            "RG Chair": Q(
                name="chair", group__type="rg", group__state__in=["active", "proposed"]
            ),
            "RG Secretary": Q(
                name="secr", group__type="rg", group__state__in=["active", "proposed"]
            ),
            "AG Secretary": Q(
                name="secr", group__type="ag", group__state__in=["active"]
            ),
            "RAG Secretary": Q(
                name="secr", group__type="rag", group__state__in=["active"]
            ),
            "Team Chair": Q(name="chair", group__type="team", group__state="active"),
            "Program Lead": Q(
                name="lead", group__type="program", group__state="active"
            ),
            "Program Secretary": Q(
                name="secr", group__type="program", group__state="active"
            ),
            "Program Chair": Q(
                name="chair", group__type="program", group__state="active"
            ),
            "EDWG Chair": Q(name="chair", group__type="edwg", group__state="active"),
            "Nomcom Chair": Q(
                name="chair",
                group__type="nomcom",
                group__acronym__icontains=kwargs.get("year", "0000"),
            ),
            "Nomcom Advisor": Q(
                name="advisor",
                group__type="nomcom",
                group__acronym__icontains=kwargs.get("year", "0000"),
            ),
            "Nomcom": Q(
                group__type="nomcom",
                group__acronym__icontains=kwargs.get("year", "0000"),
            ),
            "Liaison Manager": Q(
                name="liaiman",
                group__type="sdo",
                group__state="active",
            ),
            "Authorized Individual": Q(
                name="auth",
                group__type="sdo",
                group__state="active",
            ),
            "Recording Manager": Q(
                name="recman",
                group__type="ietf",
                group__state="active",
            ),
            "Reviewer": Q(name="reviewer", group__state="active"),
            "Review Team Secretary": Q(
                name="secr",
                group__reviewteamsettings__isnull=False,
                group__state="active",
            ),
            "IRSG Member": (
                Q(name="member", group__acronym="irsg")
                | Q(name="chair", group__acronym="irtf")
                | Q(name="atlarge", group__acronym="irsg")
            ),
            "RSAB Member": Q(name="member", group__acronym="rsab"),
            "Robot": Q(name="robot", group__acronym="secretariat"),
        }

        filter_expr = Q(
            pk__in=[]
        )  # ensure empty set is returned if no other terms are added
        for r in role_names:
            filter_expr |= role_qs[r]
        if extra_role_qs:
            for r in extra_role_qs:
                filter_expr |= extra_role_qs[r]

        user.roles_check_cache[key] = bool(
            Role.objects.filter(person=person).filter(filter_expr).exists()
        )

    return user.roles_check_cache[key]



# convenient decorator

def passes_test_decorator(test_func, message):
    """Decorator creator that creates a decorator for checking that
    user passes the test, redirecting to login or returning a 403
    error. The test function should be on the form fn(user) ->
    true/false."""
    def decorate(view_func):
        @wraps(view_func, assigned=WRAPPER_ASSIGNMENTS)
        def inner(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseRedirect('%s?%s=%s' % (settings.LOGIN_URL, REDIRECT_FIELD_NAME, urlquote(request.get_full_path())))
            elif test_func(request.user, *args, **kwargs):
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied(message)
        return inner
    return decorate


def role_required(*role_names):
    """View decorator for checking that the user is logged in and
    has one of the listed roles."""
    return passes_test_decorator(lambda u, *args, **kwargs: has_role(u, role_names, *args, **kwargs),
                                 "Restricted to role%s: %s" % ("s" if len(role_names) != 1 else "", ", ".join(role_names)))

# specific permissions

def is_authorized_in_doc_stream(user, doc):
    """Return whether user is authorized to perform stream duties on
    document."""
    if has_role(user, ["Secretariat"]):
        return True

    if not user.is_authenticated:
        return False

    # must be authorized in the stream or group

    if (not doc.stream or doc.stream.slug == "ietf") and has_role(user, ["Area Director"]):
        return True

    if not doc.stream:
        return False

    if doc.stream.slug == "ietf" and doc.group.type_id == "individ":
        return False

    docman_roles = doc.group.features.docman_roles
    if doc.stream.slug == "ietf":
        group_req = Q(group=doc.group)
    elif doc.stream.slug == "irtf":
        group_req = Q(group__acronym=doc.stream.slug) | Q(group=doc.group)
    elif doc.stream.slug == "iab":
        if doc.group.type.slug == 'individ' or doc.group.acronym == 'iab':
            docman_roles = GroupFeatures.objects.get(type_id="iab").docman_roles
        group_req = Q(group__acronym=doc.stream.slug)
    elif doc.stream.slug == "ise":
        if doc.group.type.slug == 'individ':
            docman_roles = GroupFeatures.objects.get(type_id="ietf").docman_roles
        group_req = Q(group__acronym=doc.stream.slug)
    elif doc.stream.slug == "editorial":
        group_req = Q(group=doc.group) | Q(group__acronym='rsab')
        if doc.group.type.slug in ("individ", "edappr"):
            docman_roles = GroupFeatures.objects.get(type_id="edappr").docman_roles
    else:
        group_req = Q()  # no group constraint for other cases

    return Role.objects.filter(Q(name__in=docman_roles, person__user=user) & group_req).exists()

def is_authorized_in_group(user, group):
    """Return whether user is authorized to perform duties on
    a given group."""

    if not user.is_authenticated:
        return False

    if has_role(user, ["Secretariat",]):
        return True

    if group.parent:
        if group.parent.type_id == 'area' and has_role(user, ['Area Director',]):
            return True
        if group.parent.acronym == 'irtf' and has_role(user, ['IRTF Chair',]):
            return True
        if group.parent.acronym == 'iab' and has_role(user, ['IAB','IAB Executive Director',]):
            return True

    return Role.objects.filter(name__in=group.features.groupman_roles, person__user=user,group=group ).exists()

def is_individual_draft_author(user, doc):

    if not user.is_authenticated:
        return False

    if not doc.type_id=='draft':
        return False

    if not doc.group.type_id == "individ" :
        return False

    if not hasattr(user, 'person'):
        return False

    if user.person in doc.authors():
        return True

    return False

def is_bofreq_editor(user, doc):
    if not user.is_authenticated:
        return False
    if not doc.type_id=='bofreq':
        return False
    return user.person in bofreq_editors(doc)
    
def openid_userinfo(claims, user):
    # Populate claims dict.
    person = get_object_or_404(Person, user=user)
    email = person.email_allowing_inactive()
    if person.photo:
        photo_url = person.cdn_photo_url()
    else:
        photo_url = ''
    claims.update( {
            'name':         person.plain_name(),
            'given_name':   person.first_name(),
            'family_name':  person.last_name(),
            'nickname':     '-',
            'email':        email.address if email else '',
            'picture':      photo_url,
        } )
    return claims

oidc_provider.lib.claims.StandardScopeClaims.info_profile = (
		'Basic profile',
		'Access to your basic datatracker information: Name and photo (if present).'
	    )

class OidcExtraScopeClaims(oidc_provider.lib.claims.ScopeClaims):

    info_roles = (
            "Datatracker role information",
            "Access to a list of your IETF roles as known by the datatracker"
        )

    def scope_roles(self):
        roles = self.user.person.role_set.filter(group__state_id__in=('active','bof','proposed')).values_list('name__slug', 'group__acronym')
        info = {
                'roles': list(roles)
            }
        return info

    def scope_dots(self):
        dots = get_dots(self.user.person)
        return { 'dots': dots }

    def scope_pronouns(self):
        return { 'pronouns': self.user.person.pronouns() }

    info_registration = (
            "IETF Meeting Registration Info",
            "Access to public IETF meeting registration information for the current meeting. "
            "Includes meeting number, affiliation, registration type and ticket type.",
        )

    def scope_registration(self):
        from ietf.meeting.helpers import get_current_ietf_meeting
        from ietf.stats.models import MeetingRegistration
        meeting = get_current_ietf_meeting()
        person = self.user.person
        email_list = person.email_set.values_list('address')
        q = Q(person=person, meeting=meeting) | Q(email__in=email_list, meeting=meeting)
        regs = MeetingRegistration.objects.filter(q).distinct()
        for reg in regs:
            if not reg.person_id:
                reg.person = person
                reg.save()
        info = {}
        if regs:
            # fill in info to return
            ticket_types = set([])
            reg_types = set([])
            for reg in regs:
                ticket_types.add(reg.ticket_type)
                reg_types.add(reg.reg_type)
            info = {
                'meeting':      meeting.number,
                # full_week, one_day, student:
                'ticket_type':  ' '.join(ticket_types),
                # onsite, remote, hackathon_onsite, hackathon_remote:
                'reg_type':     ' '.join(reg_types),
                'affiliation':  ([ reg.affiliation for reg in regs if reg.affiliation ] or [''])[0],
            }

        return info
            
def can_request_rfc_publication(user, doc):
    """Answers whether this user has an appropriate role to send this document to the RFC Editor for publication as an RFC.

    This not take anything but the stream of the document into account.

    NOTE: This intentionally always returns False for IETF stream documents.
    The publication request process for the IETF stream is handled by the 
    secretariat at ietf.doc.views_ballot.approve_ballot"""

    if doc.stream_id == "irtf":
        return has_role(user, ("Secretariat", "IRTF Chair"))
    elif doc.stream_id == "editorial":
        return has_role(user, ("Secretariat", "RSAB Chair"))
    elif doc.stream_id == "ise":
        return has_role(user, ("Secretariat", "ISE"))
    elif doc.stream_id == "iab":
        return has_role(user, ("Secretariat", "IAB Chair"))
    elif doc.stream_id == "ietf":
        return False # See the docstring
    else:
        return False


def send_new_email_confirmation_request(person: Person, address: str):
    """Request confirmation of a new email address
    
    If the email address is already in use, sends an alert to it. If not, sends a confirmation request.
    By design, does not indicate which was sent. This is intended to make it a bit harder to scrape addresses
    with a mindless bot.
    """
    auth = signing.dumps([person.user.username, address], salt="add_email")
    domain = Site.objects.get_current().domain
    from_email = settings.DEFAULT_FROM_EMAIL

    existing = Email.objects.filter(address=address).first()
    if existing:
        subject = f"Attempt to add your email address by {person.name}"
        send_mail(
            None,
            address,
            from_email,
            subject,
            "registration/add_email_exists_email.txt",
            {
                "domain": domain,
                "email": address,
                "person": person,
            },
        )
    else:
        subject = f"Confirm email address for {person.name}"
        send_mail(
            None,
            address,
            from_email,
            subject,
            "registration/add_email_email.txt",
            {
                "domain": domain,
                "auth": auth,
                "email": address,
                "person": person,
                "expire": settings.DAYS_TO_EXPIRE_REGISTRATION_LINK,
            },
        )
