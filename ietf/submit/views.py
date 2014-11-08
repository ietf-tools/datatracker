# Copyright The IETF Trust 2007, All Rights Reserved
import datetime
import os

from django.conf import settings
from django.core.urlresolvers import reverse as urlreverse
from django.core.validators import validate_email, ValidationError
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from ietf.doc.models import Document
from ietf.group.models import Group
from ietf.ietfauth.utils import has_role, role_required
from ietf.submit.forms import UploadForm, NameEmailForm, EditSubmissionForm, PreapprovalForm
from ietf.submit.mail import send_full_url, send_approval_request_to_group, send_submission_confirmation, submission_confirmation_email_list, send_manual_post_request
from ietf.submit.models import Submission, Preapproval, DraftSubmissionStateName
from ietf.submit.utils import approvable_submissions_for_user, preapprovals_for_user, recently_approved_by_user
from ietf.submit.utils import check_idnits, found_idnits, validate_submission, create_submission_event
from ietf.submit.utils import post_submission, cancel_submission, rename_submission_files
from ietf.utils.accesstoken import generate_random_key, generate_access_token

def upload_submission(request):
    if request.method == 'POST':
        try:
            form = UploadForm(request, data=request.POST, files=request.FILES)
            if form.is_valid():
                # save files
                file_types = []
                for ext in ['txt', 'pdf', 'xml', 'ps']:
                    f = form.cleaned_data[ext]
                    if not f:
                        continue
                    file_types.append('.%s' % ext)

                    draft = form.parsed_draft

                    name = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.%s' % (draft.filename, draft.revision, ext))
                    with open(name, 'wb+') as destination:
                        for chunk in f.chunks():
                            destination.write(chunk)

                # check idnits
                text_path = os.path.join(settings.IDSUBMIT_STAGING_PATH, '%s-%s.txt' % (draft.filename, draft.revision))
                idnits_message = check_idnits(text_path)

                # extract author lines
                authors = []
                for author in draft.get_author_list():
                    full_name, first_name, middle_initial, last_name, name_suffix, email, company = author

                    line = full_name.replace("\n", "").replace("\r", "").replace("<", "").replace(">", "").strip()
                    email = (email or "").strip()

                    if email:
                        try:
                            validate_email(email)
                        except ValidationError:
                            email = ""

                    if email:
                        line += u" <%s>" % email

                    authors.append(line)

                # save submission
                submission = Submission.objects.create(
                    state=DraftSubmissionStateName.objects.get(slug="uploaded"),
                    remote_ip=form.remote_ip,
                    name=draft.filename,
                    group=form.group,
                    title=draft.get_title(),
                    abstract=draft.get_abstract(),
                    rev=draft.revision,
                    pages=draft.get_pagecount(),
                    authors="\n".join(authors),
                    note="",
                    first_two_pages=''.join(draft.pages[:2]),
                    file_size=form.cleaned_data['txt'].size,
                    file_types=','.join(file_types),
                    submission_date=datetime.date.today(),
                    document_date=draft.get_creation_date(),
                    replaces="",
                    idnits_message=idnits_message,
                    )

                create_submission_event(request, submission, desc="Uploaded submission")

                return redirect("submit_submission_status_by_hash", submission_id=submission.pk, access_token=submission.access_token())
        except IOError as e:
            if "read error" in str(e): # The server got an IOError when trying to read POST data
                form = UploadForm(request=request)
                form._errors = {}
                form._errors["__all__"] = form.error_class(["There was a failure receiving the complete form data -- please try again."])
            else:
                raise
    else:
        form = UploadForm(request=request)

    return render_to_response('submit/upload_submission.html',
                              {'selected': 'index',
                               'form': form},
                              context_instance=RequestContext(request))

def note_well(request):
    return render_to_response('submit/note_well.html', {'selected': 'notewell'},
                              context_instance=RequestContext(request))

def tool_instructions(request):
    return render_to_response('submit/tool_instructions.html', {'selected': 'instructions'},
                              context_instance=RequestContext(request))

def search_submission(request):
    error = None
    name = None
    if request.method == 'POST':
        name = request.POST.get('name', '')
        submission = Submission.objects.filter(name=name).order_by('-pk').first()
        if submission:
            return redirect(submission_status, submission_id=submission.pk)
        error = 'No valid submission found for %s' % name
    return render_to_response('submit/search_submission.html',
                              {'selected': 'status',
                               'error': error,
                               'name': name},
                              context_instance=RequestContext(request))

def can_edit_submission(user, submission, access_token):
    key_matched = access_token and submission.access_token() == access_token
    if not key_matched: key_matched = submission.access_key == access_token # backwards-compat
    return key_matched or has_role(user, "Secretariat")

def submission_status(request, submission_id, access_token=None):
    submission = get_object_or_404(Submission, pk=submission_id)

    key_matched = access_token and submission.access_token() == access_token
    if not key_matched: key_matched = submission.access_key == access_token # backwards-compat
    if access_token and not key_matched:
        raise Http404

    errors = validate_submission(submission)
    passes_idnits = found_idnits(submission.idnits_message)

    is_secretariat = has_role(request.user, "Secretariat")
    is_chair = submission.group and submission.group.has_role(request.user, "chair")

    can_edit = can_edit_submission(request.user, submission, access_token) and submission.state_id == "uploaded"
    can_cancel = (key_matched or is_secretariat) and submission.state.next_states.filter(slug="cancel")
    can_group_approve = (is_secretariat or is_chair) and submission.state_id == "grp-appr"
    can_force_post = is_secretariat and submission.state.next_states.filter(slug="posted")
    show_send_full_url = not key_matched and not is_secretariat and submission.state_id not in ("cancel", "posted")

    confirmation_list = submission_confirmation_email_list(submission)

    try:
        preapproval = Preapproval.objects.get(name=submission.name)
    except Preapproval.DoesNotExist:
        preapproval = None

    requires_group_approval = submission.rev == '00' and submission.group and submission.group.type_id in ("wg", "rg", "ietf", "irtf", "iab", "iana", "rfcedtyp") and not preapproval

    requires_prev_authors_approval = Document.objects.filter(name=submission.name)

    message = None

    if submission.state_id == "cancel":
        message = ('error', 'This submission has been canceled, modification is no longer possible.')
    elif submission.state_id == "auth":
        message = ('success', u'The submission is pending email authentication. An email has been sent to: %s' % ", ".join(confirmation_list))
    elif submission.state_id == "grp-appr":
        message = ('success', 'The submission is pending approval by the group chairs.')
    elif submission.state_id == "aut-appr":
        message = ('success', 'The submission is pending approval by the authors of the previous version. An email has been sent to: %s' % ", ".join(confirmation_list))


    submitter_form = NameEmailForm(initial=submission.submitter_parsed(), prefix="submitter")

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == "autopost" and submission.state_id == "uploaded":
            if not can_edit:
                return HttpResponseForbidden("You do not have permission to perfom this action")

            submitter_form = NameEmailForm(request.POST, prefix="submitter")
            if submitter_form.is_valid():
                submission.submitter = submitter_form.cleaned_line()

                if requires_group_approval:
                    submission.state = DraftSubmissionStateName.objects.get(slug="grp-appr")
                    submission.save()

                    sent_to = send_approval_request_to_group(request, submission)

                    desc = "sent approval email to group chairs: %s" % u", ".join(sent_to)

                else:
                    submission.auth_key = generate_random_key()
                    if requires_prev_authors_approval:
                        submission.state = DraftSubmissionStateName.objects.get(slug="aut-appr")
                    else:
                        submission.state = DraftSubmissionStateName.objects.get(slug="auth")
                    submission.save()

                    sent_to = send_submission_confirmation(request, submission)

                    if submission.state_id == "aut-appr":
                        desc = u"sent confirmation email to previous authors: %s" % u", ".join(sent_to)
                    else:
                        desc = u"sent confirmation email to submitter and authors: %s" % u", ".join(sent_to)

                create_submission_event(request, submission, u"Set submitter to \"%s\" and %s" % (submission.submitter, desc))

                if access_token:
                    return redirect("submit_submission_status_by_hash", submission_id=submission.pk, access_token=access_token)
                else:
                    return redirect("submit_submission_status", submission_id=submission.pk)

        elif action == "edit" and submission.state_id == "uploaded":
            if access_token:
                return redirect("submit_edit_submission_by_hash", submission_id=submission.pk, access_token=access_token)
            else:
                return redirect("submit_edit_submission", submission_id=submission.pk)

        elif action == "sendfullurl" and submission.state_id not in ("cancel", "posted"):
            sent_to = send_full_url(request, submission)

            message = ('success', u'An email has been sent with the full access URL to: %s' % u",".join(confirmation_list))

            create_submission_event(request, submission, u"Sent full access URL to: %s" % u", ".join(sent_to))

        elif action == "cancel" and submission.state.next_states.filter(slug="cancel"):
            if not can_cancel:
                return HttpResponseForbidden('You do not have permission to perform this action')

            cancel_submission(submission)

            create_submission_event(request, submission, "Canceled submission")

            return redirect("submit_submission_status", submission_id=submission_id)


        elif action == "approve" and submission.state_id == "grp-appr":
            if not can_group_approve:
                return HttpResponseForbidden('You do not have permission to perform this action')

            post_submission(request, submission)

            create_submission_event(request, submission, "Approved and posted submission")

            return redirect("doc_view", name=submission.name)


        elif action == "forcepost" and submission.state.next_states.filter(slug="posted"):
            if not can_force_post:
                return HttpResponseForbidden('You do not have permission to perform this action')

            post_submission(request, submission)

            if submission.state_id == "manual":
                desc = "Posted submission manually"
            else:
                desc = "Forced post of submission"

            create_submission_event(request, submission, desc)

            return redirect("doc_view", name=submission.name)


        else:
            # something went wrong, turn this into a GET and let the user deal with it
            return HttpResponseRedirect("")

    return render_to_response('submit/submission_status.html',
                              {'selected': 'status',
                               'submission': submission,
                               'errors': errors,
                               'passes_idnits': passes_idnits,
                               'submitter_form': submitter_form,
                               'message': message,
                               'can_edit': can_edit,
                               'can_force_post': can_force_post,
                               'can_group_approve': can_group_approve,
                               'can_cancel': can_cancel,
                               'show_send_full_url': show_send_full_url,
                               'requires_group_approval': requires_group_approval,
                               'requires_prev_authors_approval': requires_prev_authors_approval,
                               'confirmation_list': confirmation_list,
                              },
                              context_instance=RequestContext(request))


def edit_submission(request, submission_id, access_token=None):
    submission = get_object_or_404(Submission, pk=submission_id, state="uploaded")

    if not can_edit_submission(request.user, submission, access_token):
        return HttpResponseForbidden('You do not have permission to access this page')

    errors = validate_submission(submission)
    form_errors = False

    # we split the form handling into multiple forms, one for the
    # submission itself, one for the submitter, and a list of forms
    # for the authors

    empty_author_form = NameEmailForm(email_required=False)

    if request.method == 'POST':
        # get a backup submission now, the model form may change some
        # fields during validation
        prev_submission = Submission.objects.get(pk=submission.pk)

        edit_form = EditSubmissionForm(request.POST, instance=submission, prefix="edit")
        submitter_form = NameEmailForm(request.POST, prefix="submitter")
        author_forms = [ NameEmailForm(request.POST, email_required=False, prefix=prefix)
                         for prefix in request.POST.getlist("authors-prefix")
                         if prefix != "authors-" ]

        # trigger validation of all forms
        validations = [edit_form.is_valid(), submitter_form.is_valid()] + [ f.is_valid() for f in author_forms ]
        if all(validations):
            submission.submitter = submitter_form.cleaned_line()
            submission.authors = "\n".join(f.cleaned_line() for f in author_forms)
            edit_form.save(commit=False) # transfer changes

            if submission.rev != prev_submission.rev:
                rename_submission_files(submission, prev_submission.rev, submission.rev)

            submission.state = DraftSubmissionStateName.objects.get(slug="manual")
            submission.save()

            send_manual_post_request(request, submission, errors)

            changed_fields = [
                submission._meta.get_field(f).verbose_name
                for f in list(edit_form.fields.keys()) + ["submitter", "authors"]
                if getattr(submission, f) != getattr(prev_submission, f)
            ]

            if changed_fields:
                desc = u"Edited %s and sent request for manual post" % u", ".join(changed_fields)
            else:
                desc = "Sent request for manual post"

            create_submission_event(request, submission, desc)

            return redirect("submit_submission_status", submission_id=submission.pk)
        else:
            form_errors = True
    else:
        edit_form = EditSubmissionForm(instance=submission, prefix="edit")
        submitter_form = NameEmailForm(initial=submission.submitter_parsed(), prefix="submitter")
        author_forms = [ NameEmailForm(initial=author, email_required=False, prefix="authors-%s" % i)
                         for i, author in enumerate(submission.authors_parsed()) ]

    return render_to_response('submit/edit_submission.html',
                              {'selected': 'status',
                               'submission': submission,
                               'edit_form': edit_form,
                               'submitter_form': submitter_form,
                               'author_forms': author_forms,
                               'empty_author_form': empty_author_form,
                               'errors': errors,
                               'form_errors': form_errors,
                              },
                              context_instance=RequestContext(request))


def confirm_submission(request, submission_id, auth_token):
    submission = get_object_or_404(Submission, pk=submission_id)

    key_matched = submission.auth_key and auth_token == generate_access_token(submission.auth_key)
    if not key_matched: key_matched = auth_token == submission.auth_key # backwards-compat

    if request.method == 'POST' and submission.state_id in ("auth", "aut-appr") and key_matched:
        post_submission(request, submission)

        create_submission_event(request, submission, "Confirmed and posted submission")

        return redirect("doc_view", name=submission.name)

    return render_to_response('submit/confirm_submission.html', {
        'submission': submission,
        'key_matched': key_matched,
    }, context_instance=RequestContext(request))


def approvals(request):
    approvals = approvable_submissions_for_user(request.user)
    preapprovals = preapprovals_for_user(request.user)

    days = 30
    recently_approved = recently_approved_by_user(request.user, datetime.date.today() - datetime.timedelta(days=days))

    return render_to_response('submit/approvals.html',
                              {'selected': 'approvals',
                               'approvals': approvals,
                               'preapprovals': preapprovals,
                               'recently_approved': recently_approved,
                               'days': days },
                              context_instance=RequestContext(request))


@role_required("Secretariat", "WG Chair", "RG Chair")
def add_preapproval(request):
    groups = Group.objects.filter(type__in=("wg", "rg")).exclude(state="conclude").order_by("acronym").distinct()

    if not has_role(request.user, "Secretariat"):
        groups = groups.filter(role__person__user=request.user,role__name__in=['ad','chair','delegate','secr'])

    if request.method == "POST":
        form = PreapprovalForm(request.POST)
        form.groups = groups
        if form.is_valid():
            p = Preapproval()
            p.name = form.cleaned_data["name"]
            p.by = request.user.person
            p.save()

            return HttpResponseRedirect(urlreverse("submit_approvals") + "#preapprovals")
    else:
        form = PreapprovalForm()

    return render_to_response('submit/add_preapproval.html',
                              {'selected': 'approvals',
                               'groups': groups,
                               'form': form },
                              context_instance=RequestContext(request))

@role_required("Secretariat", "WG Chair", "RG Chair")
def cancel_preapproval(request, preapproval_id):
    preapproval = get_object_or_404(Preapproval, pk=preapproval_id)

    if preapproval not in preapprovals_for_user(request.user):
        raise HttpResponseForbidden("You do not have permission to cancel this preapproval.")

    if request.method == "POST" and request.POST.get("action", "") == "cancel":
        preapproval.delete()

        return HttpResponseRedirect(urlreverse("submit_approvals") + "#preapprovals")

    return render_to_response('submit/cancel_preapproval.html',
                              {'selected': 'approvals',
                               'preapproval': preapproval },
                              context_instance=RequestContext(request))
