# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re
import base64
import datetime

from typing import Optional         # pyflakes:ignore

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import DataError
from django.urls import reverse as urlreverse
from django.core.validators import ValidationError
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden, HttpResponse
from django.http import HttpRequest     # pyflakes:ignore
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

import debug                            # pyflakes:ignore

from ietf.doc.models import Document, DocAlias, AddedMessageEvent
from ietf.doc.utils import prettify_std_name
from ietf.group.models import Group
from ietf.group.utils import group_features_group_filter
from ietf.ietfauth.utils import has_role, role_required
from ietf.mailtrigger.utils import gather_address_lists
from ietf.message.models import Message, MessageAttachment
from ietf.person.models import Person, Email
from ietf.submit.forms import ( SubmissionManualUploadForm, SubmissionAutoUploadForm, AuthorForm,
    SubmitterForm, EditSubmissionForm, PreapprovalForm, ReplacesForm, SubmissionEmailForm, MessageModelForm )
from ietf.submit.mail import ( send_full_url, send_manual_post_request, add_submission_email, get_reply_to )
from ietf.submit.models import (Submission, Preapproval,
    DraftSubmissionStateName, SubmissionEmailEvent )
from ietf.submit.utils import ( approvable_submissions_for_user, preapprovals_for_user,
    recently_approved_by_user, validate_submission, create_submission_event, docevent_from_submission,
    post_submission, cancel_submission, rename_submission_files, remove_submission_files, get_draft_meta,
    get_submission, fill_in_submission, apply_checkers, send_confirmation_emails, save_files,
    get_person_from_name_email )
from ietf.stats.utils import clean_country_name
from ietf.utils.accesstoken import generate_access_token
from ietf.utils.log import log
from ietf.utils.mail import parseaddr, send_mail_message

def upload_submission(request):
    if request.method == 'POST':
        try:
            form = SubmissionManualUploadForm(request, data=request.POST, files=request.FILES)
            if form.is_valid():
                saved_files = save_files(form)
                authors, abstract, file_name, file_size = get_draft_meta(form, saved_files)

                submission = get_submission(form)
                try:
                    fill_in_submission(form, submission, authors, abstract, file_size)
                except Exception as e:
                    log("Exception: %s\n" % e)
                    if submission and submission.id:
                        submission.delete()
                    raise

                apply_checkers(submission, file_name)

                create_submission_event(request, submission, desc="Uploaded submission")
                # Don't add an "Uploaded new revision doevent yet, in case of cancellation

                return redirect("ietf.submit.views.submission_status", submission_id=submission.pk, access_token=submission.access_token())
        except IOError as e:
            if "read error" in str(e): # The server got an IOError when trying to read POST data
                form = SubmissionManualUploadForm(request=request)
                form._errors = {}
                form._errors["__all__"] = form.error_class(["There was a failure receiving the complete form data -- please try again."])
            else:
                raise
        except ValidationError as e:
            form = SubmissionManualUploadForm(request=request)
            form._errors = {}
            form._errors["__all__"] = form.error_class(["There was a failure converting the xml file to text -- please verify that your xml file is valid.  (%s)" % e.message])
            if debug.debug:
                raise
        except DataError as e:
            form = SubmissionManualUploadForm(request=request)
            form._errors = {}
            form._errors["__all__"] = form.error_class(["There was a failure processing your upload -- please verify that your draft passes idnits.  (%s)" % e.message])
            if debug.debug:
                raise

    else:
        form = SubmissionManualUploadForm(request=request)

    return render(request, 'submit/upload_submission.html',
                              {'selected': 'index',
                               'form': form})

@csrf_exempt
def api_submit(request):
    "Automated submission entrypoint"
    submission = None
    def err(code, text):
        return HttpResponse(text, status=code, content_type='text/plain')
        
    if request.method == 'GET':
        return render(request, 'submit/api_submit_info.html')
    elif request.method == 'POST':
        exception = None
        try:
            form = SubmissionAutoUploadForm(request, data=request.POST, files=request.FILES)
            if form.is_valid():
                username = form.cleaned_data['user']
                user = User.objects.filter(username=username)
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

                saved_files = save_files(form)
                authors, abstract, file_name, file_size = get_draft_meta(form, saved_files)
                for a in authors:
                    if not a['email']:
                        raise ValidationError("Missing email address for author %s" % a)

                submission = get_submission(form)
                fill_in_submission(form, submission, authors, abstract, file_size)
                apply_checkers(submission, file_name)

                create_submission_event(request, submission, desc="Uploaded submission")

                errors = validate_submission(submission)
                if errors:
                    raise ValidationError(errors)

                errors = [ c.message for c in submission.checks.all() if c.passed==False ]
                if errors:
                    raise ValidationError(errors)

                if not username.lower() in [ a['email'].lower() for a in authors ]:
                    raise ValidationError('Submitter %s is not one of the document authors' % user.username)

                submission.submitter = user.person.formatted_email()
                docevent_from_submission(request, submission, desc="Uploaded new revision")

                requires_group_approval = (submission.rev == '00'
                    and submission.group and submission.group.features.req_subm_approval
                    and not Preapproval.objects.filter(name=submission.name).exists())
                requires_prev_authors_approval = Document.objects.filter(name=submission.name)

                sent_to, desc, docDesc = send_confirmation_emails(request, submission, requires_group_approval, requires_prev_authors_approval)
                msg = "Set submitter to \"%s\" and %s" % (submission.submitter, desc)
                create_submission_event(request, submission, msg)
                docevent_from_submission(request, submission, docDesc, who=Person.objects.get(name="(System)"))


                return HttpResponse(
                    "Upload of %s OK, confirmation requests sent to:\n  %s" % (submission.name, ',\n  '.join(sent_to)),
                    content_type="text/plain")
            else:
                raise ValidationError(form.errors)
        except IOError as e:
            exception = e
            return err(500, "IO Error: %s" % str(e))
        except ValidationError as e:
            exception = e
            return err(400, "Validation Error: %s" % str(e))
        except Exception as e:
            exception = e
            raise
            return err(500, "Exception: %s" % str(e))            
        finally:
            if exception and submission:
                remove_submission_files(submission)
                submission.delete()
    else:
        return err(405, "Method not allowed")

def note_well(request):
    return render(request, 'submit/note_well.html', {'selected': 'notewell'})

def tool_instructions(request):
    return render(request, 'submit/tool_instructions.html', {'selected': 'instructions'})

def search_submission(request):
    error = None
    name = None
    if request.method == 'POST':
        name = request.POST.get('name', '')
        submission = Submission.objects.filter(name=name).order_by('-pk').first()
        if submission:
            return redirect(submission_status, submission_id=submission.pk)
        else:
            if re.search(r'-\d\d$', name):
                submission = Submission.objects.filter(name=name[:-3]).order_by('-pk').first()
                if submission:
                    return redirect(submission_status, submission_id=submission.pk)
        error = 'No valid submission found for %s' % name
    return render(request, 'submit/search_submission.html',
                              {'selected': 'status',
                               'error': error,
                               'name': name})

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

    errors = validate_submission(submission)
    passes_checks = all([ c.passed!=False for c in submission.checks.all() ])

    is_secretariat = has_role(request.user, "Secretariat")
    is_chair = submission.group and submission.group.has_role(request.user, "chair")

    can_edit = can_edit_submission(request.user, submission, access_token) and submission.state_id == "uploaded"
    can_cancel = (key_matched or is_secretariat) and submission.state.next_states.filter(slug="cancel")
    can_group_approve = (is_secretariat or is_chair) and submission.state_id == "grp-appr"
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

    requires_group_approval = (submission.rev == '00'
        and submission.group and submission.group.features.req_subm_approval
        and not Preapproval.objects.filter(name=submission.name).exists())

    requires_prev_authors_approval = Document.objects.filter(name=submission.name)

    message = None



    if submission.state_id == "cancel":
        message = ('error', 'This submission has been cancelled, modification is no longer possible.')
    elif submission.state_id == "auth":
        message = ('success', 'The submission is pending email authentication. An email has been sent to: %s' % ", ".join(confirmation_list))
    elif submission.state_id == "grp-appr":
        message = ('success', 'The submission is pending approval by the group chairs.')
    elif submission.state_id == "aut-appr":
        message = ('success', 'The submission is pending approval by the authors of the previous version. An email has been sent to: %s' % ", ".join(confirmation_list))


    submitter_form = SubmitterForm(initial=submission.submitter_parsed(), prefix="submitter")
    replaces_form = ReplacesForm(name=submission.name,initial=DocAlias.objects.filter(name__in=submission.replaces.split(",")))

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == "autopost" and submission.state_id == "uploaded":
            if not can_edit:
                return HttpResponseForbidden("You do not have permission to perform this action")

            submitter_form = SubmitterForm(request.POST, prefix="submitter")
            replaces_form = ReplacesForm(request.POST, name=submission.name)
            validations = [submitter_form.is_valid(), replaces_form.is_valid()]

            if all(validations):
                submission.submitter = submitter_form.cleaned_line()
                replaces = replaces_form.cleaned_data.get("replaces", [])
                submission.replaces = ",".join(o.name for o in replaces)

                approvals_received = submitter_form.cleaned_data['approvals_received']
                
                if approvals_received:
                    if not is_secretariat:
                        return HttpResponseForbidden('You do not have permission to perform this action')

                    # go directly to posting submission
                    docevent_from_submission(request, submission, desc="Uploaded new revision")

                    desc = "Secretariat manually posting. Approvals already received"
                    post_submission(request, submission, desc, desc)

                else:
                    doc = submission.existing_document()
                    prev_authors = [] if not doc else [ author.person for author in doc.documentauthor_set.all() ]
                    curr_authors = [ get_person_from_name_email(author["name"], author.get("email")) for author in submission.authors ]

                    if request.user.is_authenticated and request.user.person in (prev_authors if submission.rev != '00' else curr_authors): # type: ignore
                        # go directly to posting submission
                        docevent_from_submission(request, submission, desc="Uploaded new revision", who=request.user.person) # type: ignore

                        desc = "New version accepted (logged-in submitter: %s)" % request.user.person # type: ignore
                        post_submission(request, submission, desc, desc)

                    else:
                        sent_to, desc, docDesc = send_confirmation_emails(request, submission, requires_group_approval, requires_prev_authors_approval)
                        msg = "Set submitter to \"%s\", replaces to %s and %s" % (
                            submission.submitter,
                            ", ".join(prettify_std_name(r.name) for r in replaces) if replaces else "(none)",
                            desc)
                        create_submission_event(request, submission, msg)
                        docevent_from_submission(request, submission, docDesc, who=Person.objects.get(name="(System)"))
    
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
                return HttpResponseForbidden('You do not have permission to perform this action')

            cancel_submission(submission)

            create_submission_event(request, submission, "Cancelled submission")

            return redirect("ietf.submit.views.submission_status", submission_id=submission_id)


        elif action == "approve" and submission.state_id == "grp-appr":
            if not can_group_approve:
                return HttpResponseForbidden('You do not have permission to perform this action')

            post_submission(request, submission, "WG -00 approved", "Approved and posted submission")

            return redirect("ietf.doc.views_doc.document_main", name=submission.name)


        elif action == "forcepost" and submission.state.next_states.filter(slug="posted"):
            if not can_force_post:
                return HttpResponseForbidden('You do not have permission to perform this action')

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

    return render(request, 'submit/submission_status.html', {
        'selected': 'status',
        'submission': submission,
        'errors': errors,
        'passes_checks': passes_checks,
        'submitter_form': submitter_form,
        'replaces_form': replaces_form,
        'message': message,
        'can_edit': can_edit,
        'can_force_post': can_force_post,
        'can_group_approve': can_group_approve,
        'can_cancel': can_cancel,
        'show_send_full_url': show_send_full_url,
        'requires_group_approval': requires_group_approval,
        'requires_prev_authors_approval': requires_prev_authors_approval,
        'confirmation_list': confirmation_list,
    })


def edit_submission(request, submission_id, access_token=None):
    submission = get_object_or_404(Submission, pk=submission_id, state="uploaded")

    if not can_edit_submission(request.user, submission, access_token):
        return HttpResponseForbidden('You do not have permission to access this page')

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
        replaces_form = ReplacesForm(name=submission.name,initial=DocAlias.objects.filter(name__in=submission.replaces.split(",")))
        author_forms = [ AuthorForm(initial=author, prefix="authors-%s" % i)
                         for i, author in enumerate(submission.authors) ]

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
    recently_approved = recently_approved_by_user(request.user, datetime.date.today() - datetime.timedelta(days=days))

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

    waiting_for_draft = Submission.objects.filter(state_id = "waiting-for-draft").distinct()

    return render(request, 'submit/manual_post.html',
                  {'manual': manual,
                   'selected': 'manual_posts',
                   'waiting_for_draft': waiting_for_draft})


def cancel_waiting_for_draft(request):
    if request.method == 'POST':
        can_cancel = has_role(request.user, "Secretariat")
        
        if not can_cancel:
            return HttpResponseForbidden('You do not have permission to perform this action')

        submission_id = request.POST.get('submission_id', '')
        access_token = request.POST.get('access_token', '')

        submission = get_submission_or_404(submission_id, access_token = access_token)
        cancel_submission(submission)
    
        create_submission_event(request, submission, "Cancelled submission")
        if (submission.rev != "00"):
            # Add a doc event
            docevent_from_submission(request, 
                                     submission,
                                     "Cancelled submission for rev {}".format(submission.rev))
    
    return redirect("ietf.submit.views.manualpost")


@role_required('Secretariat',)
def add_manualpost_email(request, submission_id=None, access_token=None):
    """Add email to submission history"""

    if request.method == 'POST':
        try:
            button_text = request.POST.get('submit', '')
            if button_text == 'Cancel':
                return redirect("submit/manual_post.html")
    
            form = SubmissionEmailForm(request.POST)
            if form.is_valid():
                submission_pk = form.cleaned_data['submission_pk']
                message = form.cleaned_data['message']
                #in_reply_to = form.cleaned_data['in_reply_to']
                # create Message
    
                if form.cleaned_data['direction'] == 'incoming':
                    msgtype = 'msgin'
                else:
                    msgtype = 'msgout'
    
                submission, submission_email_event = (
                    add_submission_email(request=request,
                                         remote_ip=request.META.get('REMOTE_ADDR', None),
                                         name = form.draft_name,
                                         rev=form.revision,
                                         submission_pk = submission_pk,
                                         message = message,
                                         by = request.user.person,
                                         msgtype = msgtype) )
    
                messages.success(request, 'Email added.')
    
                try:
                    draft = Document.objects.get(name=submission.name)
                except Document.DoesNotExist:
                    # Assume this is revision 00 - we'll do this later
                    draft = None
        
                if (draft != None):
                    e = AddedMessageEvent(type="added_message", doc=draft)
                    e.message = submission_email_event.submissionemailevent.message
                    e.msgtype = submission_email_event.submissionemailevent.msgtype
                    e.in_reply_to = submission_email_event.submissionemailevent.in_reply_to
                    e.by = request.user.person
                    e.desc = submission_email_event.desc
                    e.time = submission_email_event.time
                    e.save()
    
                return redirect("ietf.submit.views.manualpost")
        except ValidationError as e:
            form = SubmissionEmailForm(request.POST)
            form._errors = {}
            form._errors["__all__"] = form.error_class(["There was a failure uploading your message. (%s)" % e.message])
    else:
        initial = {
        }

        if (submission_id != None):
            submission = get_submission_or_404(submission_id, access_token)
            initial['name'] = "{}-{}".format(submission.name, submission.rev)
            initial['direction'] = 'incoming'
            initial['submission_pk'] = submission.pk
        else:
            initial['direction'] = 'incoming'
            
        form = SubmissionEmailForm(initial=initial)

    return render(request, 'submit/add_submit_email.html',dict(form=form))


@role_required('Secretariat',)
def send_submission_email(request, submission_id, message_id=None):
    """Send an email related to a submission"""
    submission = get_submission_or_404(submission_id, access_token = None)

    if request.method == 'POST':
        button_text = request.POST.get('submit', '')
        if button_text == 'Cancel':
            return redirect('ietf.submit.views.submission_status',
                            submission_id=submission.id,
                            access_token=submission.access_token())

        form = MessageModelForm(request.POST)
        if form.is_valid():
            # create Message
            msg = Message.objects.create(
                    by = request.user.person,
                    subject = form.cleaned_data['subject'],
                    frm = form.cleaned_data['frm'],
                    to = form.cleaned_data['to'],
                    cc = form.cleaned_data['cc'],
                    bcc = form.cleaned_data['bcc'],
                    reply_to = form.cleaned_data['reply_to'],
                    body = form.cleaned_data['body']
            )
            
            in_reply_to_id = form.cleaned_data['in_reply_to_id']
            in_reply_to = None
            rp = ""
            
            if in_reply_to_id:
                rp = " reply"
                try:
                    in_reply_to = Message.objects.get(id=in_reply_to_id)
                except Message.DoesNotExist:
                    log("Unable to retrieve in_reply_to message: %s" % in_reply_to_id)
    
            desc = "Sent message {} - manual post - {}-{}".format(rp,
                                                                  submission.name, 
                                                                  submission.rev)
            SubmissionEmailEvent.objects.create(
                    submission = submission,
                    desc = desc,
                    msgtype = 'msgout',
                    by = request.user.person,
                    message = msg,
                    in_reply_to = in_reply_to)

            # send email
            send_mail_message(None,msg)

            messages.success(request, 'Email sent.')
            return redirect('ietf.submit.views.submission_status', 
                            submission_id=submission.id,
                            access_token=submission.access_token())

    else:
        reply_to = get_reply_to()
        msg = None
        
        if not message_id:
            addrs = gather_address_lists('sub_confirmation_requested',submission=submission).as_strings(compact=False)
            to_email = addrs.to
            cc = addrs.cc
            subject = 'Regarding {}'.format(submission.name)
        else:
            try:
                submitEmail = SubmissionEmailEvent.objects.get(id=message_id)
                msg = submitEmail.message
                
                if msg:
                    to_email = msg.frm
                    cc = msg.cc
                    subject = 'Re:{}'.format(msg.subject)
                else:
                    to_email = None
                    cc = None
                    subject = 'Regarding {}'.format(submission.name)
            except Message.DoesNotExist:
                to_email = None
                cc = None
                subject = 'Regarding {}'.format(submission.name)

        initial = {
            'to': to_email,
            'cc': cc,
            'frm': settings.IDSUBMIT_FROM_EMAIL,
            'subject': subject,
            'reply_to': reply_to,
        }
        
        if msg:
            initial['in_reply_to_id'] = msg.id
        
        form = MessageModelForm(initial=initial)

    return render(request, "submit/email.html",  {
        'submission': submission,
        'access_token': submission.access_token(),
        'form':form})
    

def show_submission_email_message(request, submission_id, message_id, access_token=None):
    submission = get_submission_or_404(submission_id, access_token)

    submitEmail = get_object_or_404(SubmissionEmailEvent, pk=message_id)    
    attachments = submitEmail.message.messageattachment_set.all()
    
    return render(request, 'submit/submission_email.html',
                  {'submission': submission,
                   'message': submitEmail,
                   'attachments': attachments})

def show_submission_email_attachment(request, submission_id, message_id, filename, access_token=None):
    get_submission_or_404(submission_id, access_token)

    message = get_object_or_404(SubmissionEmailEvent, pk=message_id)

    attach = get_object_or_404(MessageAttachment, 
                               message=message.message, 
                               filename=filename)
    
    if attach.encoding == "base64":
        body = base64.b64decode(attach.body)
    else:
        body = attach.body.encode('utf-8')
    
    if attach.content_type is None:
        content_type='text/plain'
    else:
        content_type=attach.content_type
        
    response = HttpResponse(body, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename=%s' % attach.filename
    response['Content-Length'] = len(body)
    return response
    

def get_submission_or_404(submission_id, access_token=None):
    submission = get_object_or_404(Submission, pk=submission_id)

    key_matched = access_token and submission.access_token() == access_token
    if not key_matched: key_matched = submission.access_key == access_token # backwards-compat
    if access_token and not key_matched:
        raise Http404

    return submission
