# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-
import re
import datetime

from typing import Optional, cast         # pyflakes:ignore
from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse as urlreverse
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden, HttpResponse, JsonResponse
from django.http import HttpRequest     # pyflakes:ignore
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

import debug                            # pyflakes:ignore

from ietf.doc.models import Document
from ietf.doc.forms import ExtResourceForm
from ietf.group.models import Group
from ietf.group.utils import group_features_group_filter
from ietf.ietfauth.utils import has_role, role_required
from ietf.mailtrigger.utils import gather_address_lists
from ietf.person.models import Email
from ietf.submit.forms import (
    SubmissionAutoUploadForm,
    AuthorForm,
    SubmitterForm,
    EditSubmissionForm,
    PreapprovalForm,
    ReplacesForm,
    SubmissionManualUploadForm,
    SubmissionSearchForm,
)
from ietf.submit.mail import send_full_url, send_manual_post_request
from ietf.submit.models import (
    Submission,
    Preapproval,
    SubmissionExtResource,
    DraftSubmissionStateName,
)
from ietf.submit.tasks import (
    process_uploaded_submission_task,
    process_and_accept_uploaded_submission_task,
    poke,
)
from ietf.submit.utils import (
    approvable_submissions_for_user,
    preapprovals_for_user,
    recently_approved_by_user,
    validate_submission,
    create_submission_event,
    docevent_from_submission,
    post_submission,
    cancel_submission,
    rename_submission_files,
    remove_submission_files,
    get_submission,
    save_files,
    clear_existing_files,
    accept_submission,
    accept_submission_requires_group_approval,
    accept_submission_requires_prev_auth_approval,
    update_submission_external_resources,
)
from ietf.stats.utils import clean_country_name
from ietf.utils.accesstoken import generate_access_token
from ietf.utils.log import log
from ietf.utils.mail import parseaddr
from ietf.utils.response import permission_denied
from ietf.utils.timezone import date_today


def upload_submission(request):
    if request.method == "POST":
        form = SubmissionManualUploadForm(
            request, data=request.POST, files=request.FILES
        )
        if form.is_valid():
            submission = get_submission(form)
            submission.state = DraftSubmissionStateName.objects.get(slug="validating")
            submission.remote_ip = form.remote_ip
            submission.file_types = ",".join(form.file_types)
            submission.submission_date = date_today()
            submission.save()
            clear_existing_files(form)
            save_files(form)
            create_submission_event(request, submission, desc="Uploaded submission")
            # Wrap in on_commit so the delayed task cannot start until the view is done with the DB
            transaction.on_commit(
                lambda: process_uploaded_submission_task.delay(submission.pk)
            )
            return redirect(
                "ietf.submit.views.submission_status",
                submission_id=submission.pk,
                access_token=submission.access_token(),
            )
    else:
        form = SubmissionManualUploadForm(request=request)

    return render(
        request, "submit/upload_submission.html", {"selected": "index", "form": form}
    )

@csrf_exempt
def api_submission(request):
    def err(code, error, messages=None):
        data = {'error': error}
        if messages is not None:
            data['messages'] = [messages] if isinstance(messages, str) else messages
        return JsonResponse(data, status=code)

    if request.method == 'GET':
        return render(request, 'submit/api_submission_info.html')
    elif request.method == 'POST':
        exception = None
        submission = None
        try:
            form = SubmissionAutoUploadForm(request, data=request.POST, files=request.FILES)
            if form.is_valid():
                log('got valid submission form for %s' % form.filename)
                username = form.cleaned_data['user']
                user = User.objects.filter(username__iexact=username)
                if user.count() == 0:
                    # See if a secondary login was being used
                    email = Email.objects.filter(address=username, active=True)
                    # The error messages don't talk about 'email', as the field we're
                    # looking at is still the 'username' field.
                    if email.count() == 0:
                        return err(400, "No such user: %s" % username)
                    elif email.count() > 1:
                        return err(500, "Multiple matching accounts for %s" % username)
                    email = email.first()
                    if not hasattr(email, 'person'):
                        return err(400, "No person matches %s" % username)
                    person = email.person
                    if not hasattr(person, 'user'):
                        return err(400, "No user matches: %s" % username)
                    user = person.user
                elif user.count() > 1:
                    return err(500, "Multiple matching accounts for %s" % username)
                else:
                    user = user.first()
                if not hasattr(user, 'person'):
                    return err(400, "No person with username %s" % username)

                # There is a race condition here: creating the Submission with the name/rev
                # of this draft is meant to prevent another submission from occurring. However,
                # if two submissions occur at the same time, both may decide that they are the
                # only submission in progress. This may result in a Submission being posted with
                # the wrong files. The window for this is short, though, so it's probably
                # tolerable risk.
                submission = get_submission(form)
                submission.state = DraftSubmissionStateName.objects.get(slug="validating")
                submission.remote_ip = form.remote_ip
                submission.file_types = ','.join(form.file_types)
                submission.submission_date = date_today()
                submission.submitter = user.person.formatted_email()
                submission.replaces = form.cleaned_data['replaces']
                submission.save()
                clear_existing_files(form)
                save_files(form)
                create_submission_event(request, submission, desc="Uploaded submission through API")

                # Wrap in on_commit so the delayed task cannot start until the view is done with the DB
                transaction.on_commit(
                    lambda: process_and_accept_uploaded_submission_task.delay(submission.pk)
                )
                return JsonResponse(
                    {
                        'id': str(submission.pk),
                        'name': submission.name,
                        'rev': submission.rev,
                        'status_url': urljoin(
                            settings.IDTRACKER_BASE_URL,
                            urlreverse(api_submission_status, kwargs={'submission_id': submission.pk}),
                        ),
                    }
                )
            else:
                raise ValidationError(form.errors)
        except IOError as e:
            exception = e
            return err(500, 'IO Error', str(e))
        except ValidationError as e:
            exception = e
            return err(400, 'Validation Error', e.messages)
        except Exception as e:
            exception = e
            raise
        finally:
            if exception and submission:
                remove_submission_files(submission)
                submission.delete()
    else:
        return err(405, "Method not allowed")


@csrf_exempt
def api_submission_status(request, submission_id):
    submission = get_submission_or_404(submission_id)
    return JsonResponse(
        {
            'id': str(submission.pk),
            'state': submission.state.slug,
            'state_desc': submission.state.name,
        }
    )


@csrf_exempt
def api_submit_tombstone(request):
    """Tombstone for removed automated submission entrypoint"""
    return render(
        request, 
        'submit/api_submit_info.html',
        status=410,  # Gone
    )


def tool_instructions(request):
    return render(request, 'submit/tool_instructions.html', {'selected': 'instructions'})


def search_submission(request):
    if request.method == "POST":
        form = SubmissionSearchForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            submission = Submission.objects.filter(name=name).order_by("-pk").first()
            if submission:
                return redirect(submission_status, submission_id=submission.pk)
            else:
                if re.search(r"-\d\d$", name):
                    submission = (
                        Submission.objects.filter(name=name[:-3])
                        .order_by("-pk")
                        .first()
                    )
                    if submission:
                        return redirect(submission_status, submission_id=submission.pk)
            form.add_error(None, f"No valid submission found for {name}")
    else:
        form = SubmissionSearchForm()
    return render(
        request,
        "submit/search_submission.html",
        {"selected": "status", "form": form},
    )


def can_edit_submission(user, submission, access_token):
    key_matched = access_token and submission.access_token() == access_token
    if not key_matched: key_matched = submission.access_key == access_token # backwards-compat
    return key_matched or has_role(user, "Secretariat")

def submission_status(request, submission_id, access_token=None):
    # type: (HttpRequest, str, Optional[str]) -> HttpResponse
    submission = get_object_or_404(Submission, pk=submission_id)

    key_matched = access_token and submission.access_token() == access_token
    if not key_matched: key_matched = submission.access_key == access_token # backwards-compat
    if access_token and not key_matched:
        raise Http404

    if submission.state.slug == "cancel":
        errors = {}
    else:
        errors = validate_submission(submission)
    latest_checks = submission.latest_checks()
    applied_any_checks = len(latest_checks) > 0
    passes_checks = applied_any_checks and all(c.passed for c in latest_checks)

    is_secretariat = has_role(request.user, "Secretariat")
    is_chair = submission.group and submission.group.has_role(request.user, "chair")
    area = submission.area
    is_ad = area and area.has_role(request.user, "ad")

    can_edit = can_edit_submission(request.user, submission, access_token) and submission.state_id == "uploaded"
    # disallow cancellation of 'validating' submissions except by secretariat until async process is safely abortable
    can_cancel = (
            (is_secretariat or (key_matched and submission.state_id != 'validating'))
            and submission.state.next_states.filter(slug="cancel")
    )
    can_group_approve = (is_secretariat or is_ad or is_chair) and submission.state_id == "grp-appr"
    can_ad_approve = (is_secretariat or is_ad) and submission.state_id == "ad-appr"

    can_force_post = (
            is_secretariat
        and submission.state.next_states.filter(slug="posted").exists()
        and submission.state_id != "waiting-for-draft")
    show_send_full_url = (
            not key_matched
        and not is_secretariat
        and not submission.state_id in ("cancel", "posted") )

    # Begin common code chunk
    addrs = gather_address_lists('sub_confirmation_requested',submission=submission)
    addresses = addrs.to
    addresses.extend(addrs.cc)
    # Convert from RFC 2822 format if needed
    confirmation_list = [ "%s <%s>" % parseaddr(a) for a in addresses ]

    message = None

    if submission.state_id == "cancel":
        # would be nice to have a less heuristic mechansim for reporting async processing failure
        async_processing_error = submission.submissionevent_set.filter(
            desc__startswith="Submission rejected: A system error occurred"
        ).exists()
        if async_processing_error:
            message = (
                "error",
                "This submission has been cancelled due to a system error during processing. "
                "Modification is no longer possible.",
            )
        else:
            message = (
                "error",
                "This submission has been cancelled, modification is no longer possible.",
            )
    elif submission.state_id == "auth":
        message = ('success', 'The submission is pending email authentication. An email has been sent to: %s' % ", ".join(confirmation_list))
    elif submission.state_id == "grp-appr":
        message = ('success', 'The submission is pending approval by the group chairs.')
    elif submission.state_id == "ad-appr":
        message = ('success', 'The submission is pending approval by the area director.')
    elif submission.state_id == "aut-appr":
        message = ('success', 'The submission is pending approval by the authors of the previous version. An email has been sent to: %s' % ", ".join(confirmation_list))

    existing_doc = submission.existing_document()

    # Sort out external resources
    external_resources = [
        dict(res=r, added=False)
        for r in submission.external_resources.order_by('name__slug', 'value', 'display_name')
    ]

    # Show comparison of resources with current doc resources. If not posted or canceled,
    # determine which resources were added / removed. In the output, submission resources
    # will be marked as "new" if they were not present on the existing document. Document
    # resources will be marked as "removed" if they are not present in the submission.
    #
    # To classify the resources, start by assuming that every submission resource already
    # existed (the "added=False" above) and that every existing document resource was
    # removed (the "removed=True" below). Then check every submission resource for a
    # matching resource on the existing document that is still marked as "removed". If one
    # exists, change the existing resource to "not removed" and leave the submission resource
    # as "not added." If there is no matching removed resource, then mark the submission
    # resource as "added."
    #
    show_resource_changes = submission.state_id not in ['posted', 'cancel']
    doc_external_resources = [dict(res=r, removed=True)
                              for r in existing_doc.docextresource_set.all()] if existing_doc else []
    if show_resource_changes:
        for item in external_resources:
            er = cast(SubmissionExtResource, item['res'])  # cast to help type checker with the dict typing
            # get first matching resource still marked as 'removed' from previous rev resources
            existing_item = next(
                filter(
                    lambda r: (r['removed']
                               and er.name == r['res'].name
                               and er.value == r['res'].value
                               and er.display_name == r['res'].display_name),
                    doc_external_resources
                ),
                None
            )  # type: ignore
            if existing_item is None:
                item['added'] = True
            else:
                existing_item['removed'] = False
        doc_external_resources.sort(
            key=lambda d: (d['res'].name.slug, d['res'].value, d['res'].display_name)
        )

    submitter_form = SubmitterForm(initial=submission.submitter_parsed(), prefix="submitter")
    replaces_form = ReplacesForm(name=submission.name,initial=Document.objects.filter(name__in=submission.replaces.split(",")))
    extresources_form = ExtResourceForm(
        initial=dict(resources=[er['res'] for er in external_resources]),
        extresource_model=SubmissionExtResource,
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == "autopost" and submission.state_id == "uploaded":
            if not can_edit:
                permission_denied(request, "You do not have permission to perform this action")

            submitter_form = SubmitterForm(request.POST, prefix="submitter")
            replaces_form = ReplacesForm(request.POST, name=submission.name)
            extresources_form = ExtResourceForm(
                request.POST, extresource_model=SubmissionExtResource
            )
            validations = [
                submitter_form.is_valid(),
                replaces_form.is_valid(),
                extresources_form.is_valid(),
            ]

            if all(validations):
                submission.submitter = submitter_form.cleaned_line()
                replaces = replaces_form.cleaned_data.get("replaces", [])
                submission.replaces = ",".join(o.name for o in replaces)

                extresources = extresources_form.cleaned_data.get('resources', [])
                update_submission_external_resources(submission, extresources)

                approvals_received = submitter_form.cleaned_data['approvals_received']

                if submission.rev == '00' and submission.group and not submission.group.is_active:
                    permission_denied(request, 'Posting a new Internet-Draft for an inactive group is not permitted.')

                if approvals_received:
                    if not is_secretariat:
                        permission_denied(request, 'You do not have permission to perform this action')

                    # go directly to posting submission
                    docevent_from_submission(submission, desc="Uploaded new revision")

                    desc = "Secretariat manually posting. Approvals already received"
                    post_submission(request, submission, desc, desc)

                else:
                    accept_submission(submission, request, autopost=True)

                if access_token:
                    return redirect("ietf.submit.views.submission_status", submission_id=submission.pk, access_token=access_token)
                else:
                    return redirect("ietf.submit.views.submission_status", submission_id=submission.pk)

        elif action == "edit" and submission.state_id == "uploaded":
            if access_token:
                return redirect("ietf.submit.views.edit_submission", submission_id=submission.pk, access_token=access_token)
            else:
                return redirect("ietf.submit.views.edit_submission", submission_id=submission.pk)

        elif action == "sendfullurl" and submission.state_id not in ("cancel", "posted"):
            sent_to = send_full_url(request, submission)

            message = ('success', 'An email has been sent with the full access URL to: %s' % ",".join(confirmation_list))

            create_submission_event(request, submission, "Sent full access URL to: %s" % ", ".join(sent_to))

        elif action == "cancel" and submission.state.next_states.filter(slug="cancel"):
            if not can_cancel:
                permission_denied(request, 'You do not have permission to perform this action.')

            cancel_submission(submission)

            create_submission_event(request, submission, "Cancelled submission")

            return redirect("ietf.submit.views.submission_status", submission_id=submission_id)

        elif action == "approve" and submission.state_id == "ad-appr":
            if not can_ad_approve:
                permission_denied(request, 'You do not have permission to perform this action.')

            post_submission(request, submission, "WG -00 approved", "Approved and posted submission")

            return redirect("ietf.doc.views_doc.document_main", name=submission.name)

        elif action == "approve" and submission.state_id == "grp-appr":
            if not can_group_approve:
                permission_denied(request, 'You do not have permission to perform this action.')

            post_submission(request, submission, "WG -00 approved", "Approved and posted submission")

            return redirect("ietf.doc.views_doc.document_main", name=submission.name)

        elif action == "forcepost" and submission.state.next_states.filter(slug="posted"):
            if not can_force_post:
                permission_denied(request, 'You do not have permission to perform this action.')

            if submission.state_id == "manual":
                desc = "Posted submission manually"
            else:
                desc = "Forced post of submission"

            post_submission(request, submission, desc, desc)

            return redirect("ietf.doc.views_doc.document_main", name=submission.name)


        else:
            # something went wrong, turn this into a GET and let the user deal with it
            return HttpResponseRedirect("")

    for author in submission.authors:
        author["cleaned_country"] = clean_country_name(author.get("country"))

    all_forms = [submitter_form, replaces_form]

    return render(request, 'submit/submission_status.html', {
        'selected': 'status',
        'submission': submission,
        'errors': errors,
        'applied_any_checks': applied_any_checks,
        'passes_checks': passes_checks,
        'submitter_form': submitter_form,
        'replaces_form': replaces_form,
        'extresources_form': extresources_form,
        'external_resources': {
            'current': external_resources, # dict with 'res' and 'added' as keys
            'previous': doc_external_resources, # dict with 'res' and 'removed' as keys
            'show_changes': show_resource_changes,
        },
        'message': message,
        'can_edit': can_edit,
        'can_force_post': can_force_post,
        'can_group_approve': can_group_approve,
        'can_cancel': can_cancel,
        'show_send_full_url': show_send_full_url,
        'requires_group_approval': accept_submission_requires_group_approval(submission),
        'requires_prev_authors_approval': accept_submission_requires_prev_auth_approval(submission),
        'confirmation_list': confirmation_list,
        'all_forms': all_forms,
    })


def edit_submission(request, submission_id, access_token=None):
    submission = get_object_or_404(Submission, pk=submission_id, state="uploaded")

    if not can_edit_submission(request.user, submission, access_token):
        permission_denied(request, 'You do not have permission to access this page.')

    errors = validate_submission(submission)
    form_errors = False

    # we split the form handling into multiple forms, one for the
    # submission itself, one for the submitter, and a list of forms
    # for the authors

    empty_author_form = AuthorForm()

    if request.method == 'POST':
        # get a backup submission now, the model form may change some
        # fields during validation
        prev_submission = Submission.objects.get(pk=submission.pk)

        edit_form = EditSubmissionForm(request.POST, instance=submission, prefix="edit")
        submitter_form = SubmitterForm(request.POST, prefix="submitter")
        replaces_form = ReplacesForm(request.POST,name=submission.name)
        author_forms = [ AuthorForm(request.POST, prefix=prefix)
                         for prefix in request.POST.getlist("authors-prefix")
                         if prefix != "authors-" ]

        # trigger validation of all forms
        validations = [edit_form.is_valid(), submitter_form.is_valid(), replaces_form.is_valid()] + [ f.is_valid() for f in author_forms ]
        if all(validations):
            changed_fields = []

            submission.submitter = submitter_form.cleaned_line()
            replaces = replaces_form.cleaned_data.get("replaces", [])
            submission.replaces = ",".join(o.name for o in replaces)
            submission.authors = [ { attr: f.cleaned_data.get(attr) or ""
                                     for attr in ["name", "email", "affiliation", "country"] }
                                   for f in author_forms ]
            edit_form.save(commit=False) # transfer changes

            if submission.rev != prev_submission.rev:
                rename_submission_files(submission, prev_submission.rev, submission.rev)

            submission.state = DraftSubmissionStateName.objects.get(slug="manual")
            submission.save()

            formal_languages_changed = False
            if set(submission.formal_languages.all()) != set(edit_form.cleaned_data["formal_languages"]):
                submission.formal_languages.clear()
                submission.formal_languages.set(edit_form.cleaned_data["formal_languages"])
                formal_languages_changed = True

            send_manual_post_request(request, submission, errors)

            changed_fields += [
                submission._meta.get_field(f).verbose_name
                for f in list(edit_form.fields.keys()) + ["submitter", "authors"]
                if (f == "formal_languages" and formal_languages_changed)
                or getattr(submission, f) != getattr(prev_submission, f)
            ]

            if changed_fields:
                desc = "Edited %s and sent request for manual post" % ", ".join(changed_fields)
            else:
                desc = "Sent request for manual post"

            create_submission_event(request, submission, desc)

            return redirect("ietf.submit.views.submission_status", submission_id=submission.pk)
        else:
            form_errors = True
    else:
        edit_form = EditSubmissionForm(instance=submission, prefix="edit")
        submitter_form = SubmitterForm(initial=submission.submitter_parsed(), prefix="submitter")
        replaces_form = ReplacesForm(name=submission.name, initial=Document.objects.filter(name__in=submission.replaces.split(",")))
        author_forms = [ AuthorForm(initial=author, prefix="authors-%s" % i)
                         for i, author in enumerate(submission.authors) ]

    all_forms = [edit_form, submitter_form, replaces_form, *author_forms, empty_author_form]

    return render(request, 'submit/edit_submission.html',
                              {'selected': 'status',
                               'submission': submission,
                               'edit_form': edit_form,
                               'submitter_form': submitter_form,
                               'replaces_form': replaces_form,
                               'author_forms': author_forms,
                               'empty_author_form': empty_author_form,
                               'errors': errors,
                               'form_errors': form_errors,
                               'all_forms': all_forms,
                              })


def confirm_submission(request, submission_id, auth_token):
    submission = get_object_or_404(Submission, pk=submission_id)

    key_matched = submission.auth_key and auth_token == generate_access_token(submission.auth_key)
    if not key_matched: key_matched = auth_token == submission.auth_key # backwards-compat

    if request.method == 'POST' and submission.state_id in ("auth", "aut-appr") and key_matched:
        # Set a temporary state 'confirmed' to avoid entering this code
        # multiple times to confirm.
        submission.state = DraftSubmissionStateName.objects.get(slug="confirmed")
        submission.save()

        action = request.POST.get('action')
        if action == 'confirm':
            submitter_parsed = submission.submitter_parsed()
            if submitter_parsed["name"] and submitter_parsed["email"]:
                # We know who approved it
                desc = "New version approved"
            elif submission.state_id == "auth":
                desc = "New version approved by author"
            else:
                desc = "New version approved by previous author"

            post_submission(request, submission, desc, "Confirmed and posted submission")

            return redirect("ietf.doc.views_doc.document_main", name=submission.name)

        elif action == "cancel":
            if  submission.state.next_states.filter(slug="cancel"):
                cancel_submission(submission)
                create_submission_event(request, submission, "Cancelled submission")
                messages.success(request, 'The submission was cancelled.')
            else:
                messages.error(request, 'The submission is not in a state where it can be cancelled.')

            return redirect("ietf.submit.views.submission_status", submission_id=submission_id)

        else:
            raise RuntimeError("Unexpected state in confirm_submission()")

    return render(request, 'submit/confirm_submission.html', {
        'submission': submission,
        'key_matched': key_matched,
    })


def approvals(request):
    approvals = approvable_submissions_for_user(request.user)
    preapprovals = preapprovals_for_user(request.user)

    days = 30
    recently_approved = recently_approved_by_user(request.user, date_today() - datetime.timedelta(days=days))

    return render(request, 'submit/approvals.html',
                              {'selected': 'approvals',
                               'approvals': approvals,
                               'preapprovals': preapprovals,
                               'recently_approved': recently_approved,
                               'days': days })


@role_required("Secretariat", "Area Director", "WG Chair", "RG Chair")
def add_preapproval(request):
    groups = Group.objects.filter(type__features__req_subm_approval=True).exclude(state__in=["conclude","bof-conc"]).order_by("acronym").distinct()

    if not has_role(request.user, "Secretariat"):
        groups = group_features_group_filter(groups, request.user.person, 'docman_roles')

    if request.method == "POST":
        form = PreapprovalForm(request.POST)
        form.groups = groups
        if form.is_valid():
            p = Preapproval()
            p.name = form.cleaned_data["name"]
            p.by = request.user.person
            p.save()

            return HttpResponseRedirect(urlreverse("ietf.submit.views.approvals") + "#preapprovals")
    else:
        form = PreapprovalForm()

    return render(request, 'submit/add_preapproval.html',
                              {'selected': 'approvals',
                               'groups': groups,
                               'form': form })

@role_required("Secretariat", "WG Chair", "RG Chair")
def cancel_preapproval(request, preapproval_id):
    preapproval = get_object_or_404(Preapproval, pk=preapproval_id)

    if preapproval not in preapprovals_for_user(request.user):
        raise HttpResponseForbidden("You do not have permission to cancel this preapproval.")

    if request.method == "POST" and request.POST.get("action", "") == "cancel":
        preapproval.delete()

        return HttpResponseRedirect(urlreverse("ietf.submit.views.approvals") + "#preapprovals")

    return render(request, 'submit/cancel_preapproval.html',
                              {'selected': 'approvals',
                               'preapproval': preapproval })


def manualpost(request):
    '''
    Main view for manual post requests
    '''

    manual = Submission.objects.filter(state_id = "manual").distinct()

    for s in manual:
        s.passes_checks = all([ c.passed!=False for c in s.checks.all() ])
        s.errors = validate_submission(s)

    return render(
        request, 
        'submit/manual_post.html',
        {
            'manual': manual,
            'selected': 'manual_posts'
        }
    )


def get_submission_or_404(submission_id, access_token=None):
    submission = get_object_or_404(Submission, pk=submission_id)

    key_matched = access_token and submission.access_token() == access_token
    if not key_matched: key_matched = submission.access_key == access_token # backwards-compat
    if access_token and not key_matched:
        raise Http404

    return submission


def async_poke_test(request):
    result = poke.delay()
    return HttpResponse(f'Poked {result}', content_type='text/plain')
