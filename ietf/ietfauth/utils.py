# various authentication and authorization utilities

from functools import wraps

from django.utils.http import urlquote
from django.conf import settings
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.decorators import available_attrs

from ietf.group.models import Role
from ietf.person.models import Person

def user_is_person(user, person):
    """Test whether user is associated with person."""
    if not user.is_authenticated() or not person:
        return False

    if person.user_id == None:
        return False

    return person.user_id == user.id

def has_role(user, role_names, *args, **kwargs):
    """Determines whether user has any of the given standard roles
    given. Role names must be a list or, in case of a single value, a
    string."""
    if isinstance(role_names, str) or isinstance(role_names, unicode):
        role_names = [ role_names ]
    
    if not user or not user.is_authenticated():
        return False

    # use cache to avoid checking the same permissions again and again
    if not hasattr(user, "roles_check_cache"):
        user.roles_check_cache = {}

    key = frozenset(role_names)
    if key not in user.roles_check_cache:
        try:
            person = user.person
        except Person.DoesNotExist:
            return False

        role_qs = {
	    "Area Director": Q(person=person, name__in=("pre-ad", "ad"), group__type="area", group__state="active"),
	    "Secretariat": Q(person=person, name="secr", group__acronym="secretariat"),
            "IAB" : Q(person=person, name="member", group__acronym="iab"),
	    "IANA": Q(person=person, name="auth", group__acronym="iana"),
            "RFC Editor": Q(person=person, name="auth", group__acronym="rfceditor"),
            "ISE" : Q(person=person, name="chair", group__acronym="ise"),
	    "IAD": Q(person=person, name="admdir", group__acronym="ietf"),
	    "IETF Chair": Q(person=person, name="chair", group__acronym="ietf"),
	    "IETF Trust Chair": Q(person=person, name="chair", group__acronym="ietf-trust"),
	    "IRTF Chair": Q(person=person, name="chair", group__acronym="irtf"),
	    "IAB Chair": Q(person=person, name="chair", group__acronym="iab"),
	    "IAB Executive Director": Q(person=person, name="execdir", group__acronym="iab"),
            "IAB Group Chair": Q(person=person, name="chair", group__type="iab", group__state="active"),
            "IAOC Chair": Q(person=person, name="chair", group__acronym="iaoc"),
	    "WG Chair": Q(person=person,name="chair", group__type="wg", group__state__in=["active","bof", "proposed"]),
	    "WG Secretary": Q(person=person,name="secr", group__type="wg", group__state__in=["active","bof", "proposed"]),
	    "RG Chair": Q(person=person,name="chair", group__type="rg", group__state__in=["active","proposed"]),
	    "RG Secretary": Q(person=person,name="secr", group__type="rg", group__state__in=["active","proposed"]),
            "AG Secretary": Q(person=person,name="secr", group__type="ag", group__state__in=["active"]),
            "Team Chair": Q(person=person,name="chair", group__type="team", group__state="active"),
            "Nomcom Chair": Q(person=person, name="chair", group__type="nomcom", group__acronym__icontains=kwargs.get('year', '0000')),
            "Nomcom Advisor": Q(person=person, name="advisor", group__type="nomcom", group__acronym__icontains=kwargs.get('year', '0000')),
            "Nomcom": Q(person=person, group__type="nomcom", group__acronym__icontains=kwargs.get('year', '0000')),
            "Liaison Manager": Q(person=person,name="liaiman",group__type="sdo",group__state="active", ),
            "Authorized Individual": Q(person=person,name="auth",group__type="sdo",group__state="active", ),
            }

        filter_expr = Q()
        for r in role_names:
            filter_expr |= role_qs[r]

        user.roles_check_cache[key] = bool(Role.objects.filter(filter_expr)[:1])

    return user.roles_check_cache[key]


# convenient decorator

def passes_test_decorator(test_func, message):
    """Decorator creator that creates a decorator for checking that
    user passes the test, redirecting to login or returning a 403
    error. The test function should be on the form fn(user) ->
    true/false."""
    def decorate(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def inner(request, *args, **kwargs):
            if not request.user.is_authenticated():
                return HttpResponseRedirect('%s?%s=%s' % (settings.LOGIN_URL, REDIRECT_FIELD_NAME, urlquote(request.get_full_path())))
            elif test_func(request.user, *args, **kwargs):
                return view_func(request, *args, **kwargs)
            else:
                return HttpResponseForbidden(message)
        return inner
    return decorate


def role_required(*role_names):
    """View decorator for checking that the user is logged in and
    has one of the listed roles."""
    return passes_test_decorator(lambda u, *args, **kwargs: has_role(u, role_names, *args, **kwargs),
                                 "Restricted to role%s %s" % ("s" if len(role_names) != 1 else "", ", ".join(role_names)))

# specific permissions

def is_authorized_in_doc_stream(user, doc):
    """Return whether user is authorized to perform stream duties on
    document."""
    if has_role(user, ["Secretariat"]):
        return True

    if not user.is_authenticated():
        return False

    # must be authorized in the stream or group

    if (not doc.stream or doc.stream.slug == "ietf") and has_role(user, ["Area Director"]):
        return True

    if not doc.stream:
        return False

    if doc.stream.slug == "ietf" and doc.group.type == "individ":
        return False

    if doc.stream.slug == "ietf":
        group_req = Q(group=doc.group)
    elif doc.stream.slug == "irtf":
        group_req = Q(group__acronym=doc.stream.slug) | Q(group=doc.group)
    elif doc.stream.slug in ("iab", "ise"):
        group_req = Q(group__acronym=doc.stream.slug)
    else:
        group_req = Q()

    return Role.objects.filter(Q(name__in=("chair", "secr", "delegate", "auth"), person__user=user) & group_req).exists()

