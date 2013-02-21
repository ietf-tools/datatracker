import re
import itertools
from datetime import datetime
from textwrap import TextWrapper
from smtplib import SMTPException

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe

from ietf.secr.lib import template, jsonapi
from ietf.secr.ipradmin.managers import IprDetailManager
from ietf.secr.ipradmin.forms import IprDetailForm, IPRContactFormset
from ietf.secr.utils.document import get_rfc_num, is_draft
import ietf.settings as settings

from ietf.ipr.models import IprDetail, IprUpdate, IprRfc, IprDraft, IprContact, LICENSE_CHOICES, STDONLY_CHOICES, IprNotification
from ietf.utils.mail import send_mail_text

from ietf.doc.models import DocAlias
from ietf.group.models import Role

@template('ipradmin/list.html')
def admin_list(request):
    queue_ipr = IprDetailManager.queue_ipr()
    generic_ipr = IprDetailManager.generic_ipr()
    specific_ipr = IprDetailManager.specific_ipr()
    admin_removed_ipr = IprDetailManager.admin_removed_ipr()
    request_removed_ipr = IprDetailManager.request_removed_ipr()
    third_party_notifications = IprDetailManager.third_party_notifications()
    return dict ( queue_ipr = queue_ipr,
                  generic_ipr = generic_ipr,
                  specific_ipr = specific_ipr,
                  admin_removed_ipr = admin_removed_ipr,
                  request_removed_ipr = request_removed_ipr,
                  third_party_notifications = third_party_notifications)


def admin_post(request, ipr_id, from_page, command):
    updated_ipr_id = 0

    ipr_dtl = IprDetail.objects.get(ipr_id=ipr_id)
    ipr_dtl.status = 1
    #assert False, (ipr_dtl.ipr_id, ipr_dtl.is_pending)
    ipr_dtl.save()

    updates = ipr_dtl.updates.filter(processed=0)
    for update in updates:
        updated_ipr_id = update.updated.ipr_id
        old_ipr = IprDetail.objects.get(ipr_id=update.updated.ipr_id)
        updated_title = re.sub(r' \(\d\)$', '', old_ipr.title)
        lc_updated_title = updated_title.lower()
        lc_this_title = ipr_dtl.title.lower()
        if lc_updated_title == lc_this_title:
            doc_number = IprDetail.objects.filter(title__istartswith=lc_this_title+' (', title__iendswith=')').count()
            if doc_number == 0: # No same ipr title before - number the orginal ipr
                old_ipr.title = "%s (1)" % ipr_dtl.title
                ipr_dtl.title = "%s (2)" % ipr_dtl.title
            else: # Second or later update, increment
                ipr_dtl.title = "%s (%d)" % (ipr_dtl.title, doc_number+1)

        old_ipr.status = update.status_to_be
        update.processed = 1
        old_ipr.save()
        update.save()
        ipr_dtl.save()

    #assert False, (ipr_dtl.ipr_id, ipr_dtl.is_pending)
    redirect_url = '/ipradmin/admin/notify/%s?from=%s' % (ipr_id, from_page)

    return HttpResponseRedirect(redirect_url)
# end admin_post

def send_notifications(post_data, ipr_id, update=False):
    for field in post_data:
        if 'notify' in field:
            str_msg = re.sub(r'\r', '', post_data[field])
            msg_lines = str_msg.split('\n')
            body = '\n'.join(msg_lines[4:])
            headers = msg_lines[:4]
            to = re.sub('To:', '', headers[0]).strip()
            frm = re.sub('From:', '', headers[1]).strip()
            subject = re.sub('Subject:', '', headers[2]).strip()
            cc = re.sub('Cc:', '', headers[3]).strip()
            '''
            not required, send_mail_text handles this
            try:
                if settings.DEVELOPMENT:
                    to = cc = settings.TEST_EMAIL
                    frm = 'test@amsl.com'
            except AttributeError:
                pass
            '''
            try:
                send_mail_text(None, to, frm, subject, body, cc)
            except (ImproperlyConfigured, SMTPException) as e:
                return e
            now = datetime.now()
            IprNotification(
                ipr_id=ipr_id,
                notification=str_msg,
                date_sent=now.date(),
                time_sent=now.time()
            )
            if update:
                ipr_dtl = IprDetail.objects.get(ipr_id=ipr_id)
                today = datetime.today().date()
                ipr_dtl.update_notified_date = today
                ipr_dtl.save()
    return None 


@template('ipradmin/notify.html')
def admin_notify(request, ipr_id):
    if request.POST and 'command' in request.POST and 'do_send_notifications' == request.POST['command']:
        send_result = send_notifications(request.POST, ipr_id) 
        if send_result:
            request.session['send_result'] = 'Some messages failed to send'
        else: 
            request.session['send_result'] = 'Messages sent successfully'
        return HttpResponseRedirect(reverse(
            'ipr_old_submitter_notify', 
            args=[ipr_id]
        ))

    if 'send_result' in request.session:
        result = request.session['send_result']
        del request.session['send_result']
        return dict(
            page_id = 'send_result',
            result = result
        )

    if request.GET and 'from' in request.GET:
        from_page = request.GET['from']
        page_id = from_page + '_post'
    ipr_dtl = IprDetail.objects.get(ipr_id=ipr_id)
    generic_ad = ''
    if ipr_dtl.generic:
        generic_ad = get_generic_ad_text(ipr_id)

    updated_ipr = ipr_dtl.updates.filter(processed=0)
    updated_ipr_id = updated_ipr[0].ipr_id if updated_ipr else 0
    submitter_text = get_submitter_text(ipr_id, updated_ipr_id, from_page)

    document_relatives = ''
    #drafts = IprDraft.objects.filter(ipr__ipr_id=ipr_id)
    #for draft in drafts:
    #    document_relatives += get_document_relatives(ipr_id, draft, is_draft=1)

    #rfcs = IprRfc.objects.filter(ipr__ipr_id=ipr_id)
    #for rfc in rfcs:
    #    document_relatives += get_document_relatives(ipr_id, rfc, is_draft=0)
    # REDESIGN
    for iprdocalias in ipr_dtl.documents.all():
        document_relatives += get_document_relatives(ipr_dtl, iprdocalias.doc_alias)

    return dict(
        page_id = page_id,
        ipr_id = ipr_id,
        submitter_text = submitter_text,
        document_relatives = document_relatives,
        generic_ad = generic_ad
    )


def get_generic_ad_text(id):
    '''
    This function builds an email to the General Area, Area Director
    '''
    text = ''
    role = Role.objects.filter(group__acronym='gen',name='ad')[0]
    gen_ad_name = role.person.name
    gen_ad_email = role.email.address
    ipr_dtl = IprDetail.objects.get(ipr_id=id)
    submitted_date, ipr_title = ipr_dtl.submitted_date, ipr_dtl.title
    email_body = TextWrapper(width=80, break_long_words=False).fill(
        'A generic IPR disclosure was submitted to the IETF Secretariat on %s and has been posted on the "IETF Page of Intellectual Property Rights Disclosures" (https://datatracker.ietf.org/public/ipr_list.cgi).  The title of the IPR disclosure is "%s."' % (submitted_date, ipr_title)
    ) 
    text = '''
<h4>Generic IPR notification to GEN AD, %s</h4>
<textarea name="notify_gen_ad" rows=25 cols=80>
To: %s
From: IETF Secretariat <ietf-ipr@ietf.org>
Subject: Posting of IPR Disclosure
Cc:

Dear %s:

%s

The IETF Secretariat
</textarea>
<br><br>
<br>
    ''' % (gen_ad_name, gen_ad_email, gen_ad_name, email_body)
    return text

def get_submitter_text(ipr_id, updated_ipr_id, from_page):
    text = ''
    ipr_dtl = IprDetail.objects.get(ipr_id=ipr_id)
    c3, c2, c1 = [ipr_dtl.contact.filter(contact_type=x) for x in [3,2,1]]
    if c3:
        to_email, to_name = c3[0].email, c3[0].name
    elif c2:
        to_email, to_name = c2[0].email, c2[0].name
    elif c1:
        to_email, to_name = c1[0].email, c1[0].name
    else:
        to_email = "UNKNOWN EMAIL - NEED ASSISTANCE HERE"
        to_name = "UNKNOWN NAME - NEED ASSISTANCE HERE"
         
    ipr_title = IprDetail.objects.get(ipr_id=ipr_id).title
    wrapper = TextWrapper(width=80, break_long_words=False)

    if from_page == 'detail':
        email_body = 'Your IPR disclosure entitled "%s" has been posted on the "IETF Page of Intellectual Property Rights Disclosures" (https://datatracker.ietf.org/public/ipr_list.cgi).' % (ipr_title)
        subject = "Posting of IPR Disclosure";
    elif from_page == 'update':
        email_body = 'On DATE, UDPATE NAME submitted an update to your 3rd party disclosure -- entitled "%s". The update has been posted on the "IETF Page of Intellectual Property Rights Disclosures" (https://datatracker.ietf.org/ipr/%s/)' % (ipr_title, ipr_id)
        subject = "IPR disclosure Update Notification"
    email_body = wrapper.fill(email_body)

    cc_list = [];
    if updated_ipr_id > 0:
        subject = "Posting of Updated IPR Disclosure"

        updated_ipr_dtl = IprDetail.objects.get(ipr_id=updated_ipr_id)
        old_submitted_date, old_title = updated_ipr_dtl.submitted_date, updated_ipr_dtl.old_title
        
        email_body = 'Your IPR disclosure entitled "%s" has been posted on the "IETF Page of Intellectual Property Rights Disclosures" (https://datatracker.ietf.org/public/ipr_list.cgi).  Your IPR disclosure updates IPR disclosure ID #$updated_ipr_id, "%s," which was posted on $old_submitted_date' % (ipr_title, updated_ipr_id, old_title, old_submitted_date)

        updated_contacts = updated_ipr_dtl.contact.all() 
        c3, c2, c1 = [updated_contacts.filter(contact_type=x) for x in [3,2,1]]
        if c3:
            cc_list.append(c3[0].email)
        elif c2:
            cc_list.append(c2[0].email)

        for idx in range(10):
            cc_list.append(c1[0].email)
            updated_ipr = IprUpdate.objects.filter(ipr_id=updated_ipr_id)
            if updated_ipr:
                c1 = IprContact.objects.filter(ipr_id=updated_ipr[0].updated, contact_type=1)
            if not updated_ipr or not c1:
                break

        cc_list.append(ipr_dtl.contacts.filter(contact_type=1)[0].email)

    cc_list = ','.join(list(set(cc_list)))

    text = '''To: %s
From: IETF Secretariat <ietf-ipr@ietf.org>
Subject: %s
Cc: %s

Dear %s:

%s

The IETF Secretariat
    ''' % (to_email, subject, cc_list, to_name, email_body)

    return text
# end get_submitter_text

def get_document_relatives(ipr_dtl, docalias):
    '''
    This function takes a IprDetail object and a DocAlias object and returns an email.
    '''
    text = ''
    doc = docalias.document
    doc_info, author_names, author_emails, cc_list = '', '', '', ''
    authors = doc.authors.all()
    
    if is_draft(doc):
        doc_info = 'Internet-Draft entitled "%s" (%s)' \
            % (doc.title, doc.name)
        updated_id = doc.pk

    else: # not i-draft, therefore rfc
        rfc_num = get_rfc_num(doc)
        doc_info = 'RFC entitled "%s" (RFC%s)' \
            % (doc.title, rfc_num)
        updated_id = rfc_num

    # if the document is not associated with a group copy job owner or Gernal Area Director
    if doc.group.acronym == 'none':
        if doc.ad and is_draft(doc):
            cc_list = doc.ad.role_email('ad').address
        else:
            role = Role.objects.filter(group__acronym='gen',name='ad')[0]
            cc_list = role.email.address
            
    else:
        cc_list = get_wg_email_list(doc.group)

    author_emails = ','.join([a.address for a in authors])
    author_names = ', '.join([a.person.name for a in authors])
    
    cc_list += ", ipr-announce@ietf.org"

    submitted_date = ipr_dtl.submitted_date
    ipr_title = ipr_dtl.title

    email_body = '''
An IPR disclosure that pertains to your %s was submitted to the IETF Secretariat on %s and has been posted on the "IETF Page of Intellectual Property Rights Disclosures" (https://datatracker.ietf.org/ipr/%s/). The title of the IPR disclosure is "%s."");
    ''' % (doc_info, submitted_date, ipr_dtl.ipr_id, ipr_title)
    wrapper = TextWrapper(width=80, break_long_words=False)
    email_body = wrapper.fill(email_body)

    text = '''
<h4>Notification for %s</h4>
<textarea name="notify_%s" rows=25 cols=80>
To: %s
From: IETF Secretariat <ietf-ipr@ietf.org>
Subject: IPR Disclosure: %s
Cc: %s

Dear %s:

%s

The IETF Secretariat

</textarea>
<br><br>
    ''' % (doc_info, updated_id, author_emails, ipr_title, cc_list, author_names, email_body)
    # FIXME: why isn't this working - done in template now, also
    return mark_safe(text)
# end get_document_relatives

def get_wg_email_list(group):
    '''This function takes a Working Group object and returns a string of comman separated email
    addresses for the Area Directors and WG Chairs
    '''
    result = []
    roles = itertools.chain(Role.objects.filter(group=group.parent,name='ad'),
                            Role.objects.filter(group=group,name='chair'))
    for role in roles:
        result.append(role.email.address)

    if group.list_email:
        result.append(group.list_email)
    
    return ', '.join(result)

@template('ipradmin/delete.html')
def admin_delete(request, ipr_id):
    ipr_dtl = IprDetail.objects.get(ipr_id=ipr_id)
    ipr_dtl.status = 2
    ipr_dtl.save()
    return HttpResponseRedirect(reverse('ipr_admin_list'))

@template('ipradmin/notify.html')
def old_submitter_notify(request, ipr_id):
    if request.POST and 'command' in request.POST \
       and 'do_send_update_notification' == request.POST['command']:
        send_result = send_notifications(request.POST, ipr_id, update=True) 
        if send_result:
            #assert False, send_result
            request.session['send_result'] = 'Some messages failed to send'
        else: 
            request.session['send_result'] = 'Messages sent successfully'
        return HttpResponseRedirect(reverse(
            'ipr_old_submitter_notify', 
            args=[ipr_id]
        ))

    if 'send_result' in request.session:
        result = request.session['send_result']
        del request.session['send_result']
        return dict(
            page_id = 'send_result',
            result = result
        )

    contact_three = IprContact.objects.filter(ipr__ipr_id=ipr_id, contact_type=3)
    if contact_three:
        submitter_email, submitter_name = contact_three[0].email, contact_three[0].name
    else:
        contact_two = IprContact.objects.filter(ipr__ipr_id=ipr_id, contact_type=2)
        if contact_two:
            submitter_email, submitter_name = contact_two[0].email, contact_two[0].name
        else:
            submitter_email = submitter_name = ''

    try:
        ipr_update = IprUpdate.objects.get(ipr__ipr_id=ipr_id, processed=0)
    except IprUpdate.DoesNotExist:
    #    import ipdb; ipdb.set_trace()
        pass
    old_ipr_id = ipr_update.updated.ipr_id
    old_ipr = IprDetail.objects.get(ipr_id=old_ipr_id)

    old_contact_three = IprContact.objects.filter(ipr__ipr_id=old_ipr_id, contact_type=3)
    if old_contact_three:
        to_email, to_name = old_contact_three[0].email, old_contact_three[0].name
    else:
        old_contact_two = IprContact.objects.filter(ipr__ipr_id=old_ipr_id, contact_type=2)
        if old_contact_two:
            to_email, to_name = old_contact_two[0].email, old_contact_two[0].name
        else:
            to_email = to_name = ''
    updated_document_title, orig_submitted_date = old_ipr.title, old_ipr.submitted_date

    return dict(
        page_id = 'detail_notify',
        ipr_id = ipr_id,
        updated_ipr_id = old_ipr_id,
        submitter_email = submitter_email,
        submitter_name = submitter_name,
        to_email = to_email,
        to_name = to_name,
        updated_document_title = updated_document_title,
        orig_submitted_date = orig_submitted_date,
    )
# end old_submitter_notify

@template('ipradmin/detail.html')
def admin_detail(request, ipr_id):
    if request.POST and request.POST['command']:
        command = request.POST['command']
        if command == 'post':
            return admin_post(request, ipr_id, 'detail', 'post')
        elif command == 'notify':
            return HttpResponseRedirect(reverse('ipr_old_submitter_notify', args=[ipr_id]))
        elif command == 'delete':
            return HttpResponseRedirect(reverse('ipr_admin_delete', args=[ipr_id]))

    header_text = possible = temp_name = footer_text = ''
    contact_one_data, contact_two_data, document_data, licensing_data,\
        disclosure_data, designations_data, contact_three_data,\
        notes_data, controls = [], [], [], [], [], [], [], [], []
    
    ipr_dtl = IprDetail.objects.get(ipr_id=ipr_id)
    ipr_updates = IprUpdate.objects.filter(processed=0, ipr__ipr_id=ipr_id)

    contact_one, contact_two, contact_three = [
        ipr_dtl.contact.filter(contact_type=x) for x in (1,2,3)
    ]

    if ipr_updates:
        if ipr_dtl.update_notified_date:
            footer_text = mark_safe('<span class="alert">This update was notifed to the submitter of the IPR that is being updated on %s.</span>' % ipr_dtl.update_notified_date)
        else:
            controls = ['notify']
    if not ipr_updates or ipr_dtl.update_notified_date:
        controls = ['post']

    controls.append('delete')

    if ipr_dtl.third_party:
        temp_name = 'Notification'
        possible = 'Possible '
        displaying_section = "I, II, and III"
        header_text = '''This form is used to let the IETF know about patent information regarding an IETF document or contribution when the person letting the IETF know about the patent has no relationship with the patent owners.<br>
  Click <a href="./ipr.cgi"> here</a> if you want to disclose information about patents or patent applications where you do have a relationship to the patent owners or patent applicants.'''
    elif ipr_dtl.generic:
        temp_name = "Generic IPR Disclosures"
        displaying_section = "I and II"
        header_text = '''This document is an IETF IPR Patent Disclosure and Licensing Declaration 
     Template and is submitted to inform the IETF of a) patent or patent application information that is not related to a specific IETF document or contribution, and b) an IPR Holder's intention with respect to the licensing of its necessary patent claims.
     No actual license is implied by submission of this template.'''
    else:
        temp_name = "Specific IPR Disclosures"
        displaying_section = "I, II, and IV"
        header_text = '''This document is an IETF IPR Disclosure and Licensing Declaration 
   Template and is submitted to inform the IETF of a) patent or patent application information regarding
   the IETF document or contribution listed in Section IV, and b) an IPR Holder\'s intention with respect to the licensing of its necessary patent claims.
   No actual license is implied by submission of this template. 
   Please complete and submit a separate template for each IETF document or contribution to which the
   disclosed patent information relates.'''
    
    legacy_links = (
        (ipr_dtl.legacy_url_1 or '', ipr_dtl.legacy_title_1 or ''),
        (ipr_dtl.legacy_url_2 or '', ipr_dtl.legacy_title_2 or ''),
    )

    comply_statement = '' if ipr_dtl.comply else mark_safe('<div class="alert">This IPR disclosure does not comply with the formal requirements of Section 6, "IPR Disclosures," of RFC 3979, "Intellectual Property Rights in IETF Technology."</div>')

    # FIXME: header_text is assembled in perl code but never printed
    if ipr_dtl.legacy_url_0:
        #header_text = header_text + '''
        header_text = '''
     This IPR disclosure was submitted by e-mail.<br>
    %s
    Sections %s of "The Patent Disclosure and Licensing Declaration Template for %s" have been completed for this IPR disclosure. Additional information may be available in the original submission.<br>
     Click <a href="%s">here</a> to view the content of the original IPR disclosure.''' % (comply_statement, displaying_section, temp_name, ipr_dtl.legacy_url_0)
    else:
        #header_text = header_text + '''
        header_text = '''
    Only those sections of the "Patent Disclosure and Licensing Declaration Template for %s" where the submitter provided information are displayed.''' % temp_name
    
    if not ipr_dtl.generic or not (not ipr_dtl.legacy_url_0 and (ipr_dtl.notes or ipr_dtl.patents)):
        # FIXME: behavior as perl, but is quite confusing and seems wrong
        if contact_one and contact_one[0].name:
            contact_one = contact_one[0]
            contact_one_data = [
                ('II. Patent Holder\'s Contact for License Application:'),
                ('Name:', contact_one.name),
                ('Title:', contact_one.title),
                ('Department:', contact_one.department),
                ('Address1:', contact_one.address1),
                ('Address2:', contact_one.address2),
                ('Telephone:', contact_one.telephone),
                ('Fax:', contact_one.fax),
                ('Email:', contact_one.email)
            ]

    if not ipr_dtl.generic:
                  
        if contact_two and contact_two[0].name:
            contact_two = contact_two[0]
            contact_two_data = [
                ('III. Contact Information for the IETF Participant Whose Personal Belief Triggered this Disclosure:'),
                ('Name:', contact_two.name),
                ('Title:', contact_two.title),
                ('Department:', contact_two.department),
                ('Address1:', contact_two.address1),
                ('Address2:', contact_two.address2),
                ('Telephone:', contact_two.telephone),
                ('Fax:', contact_two.fax),
                ('Email:', contact_two.email)
            ]

        # conversion
        #rfcs = ipr_dtl.rfcs.all()
        #drafts = ipr_dtl.drafts.all()
        rfcs = ipr_dtl.documents.filter(doc_alias__name__startswith='rfc')
        drafts = ipr_dtl.documents.exclude(doc_alias__name__startswith='rfc')
        titles_data, rfcs_data, drafts_data, designations_data = (), (), (), ()
        rfc_titles, draft_titles = [], []
        if rfcs:
            rfc_titles = [
                rfc.doc_alias.document.title for rfc in rfcs
            ]
            rfcs_data = tuple([
                'RFC Number:',
                [get_rfc_num(rfc.doc_alias.document) for rfc in rfcs]
            ])
        if drafts:
            draft_titles = [
                draft.doc_alias.document.title for draft in drafts
            ]
            drafts_data = tuple([
                'ID Filename:',
                [draft.doc_alias.document.name+'.txt' for draft in drafts]
            ])
        if ipr_dtl.other_designations:
            designations_data = tuple([
                'Designations for Other Contributions:',
                ipr_dtl.other_designations
            ])
        if drafts or rfcs:
            titles_data = tuple([
                'Title:',
                rfc_titles + draft_titles
            ])

        if rfcs_data or drafts_data or designations_data:
            document_data = [
                ('IV. IETF Document or Other Contribution to Which this IPR Disclosure Relates'),
                titles_data,
                rfcs_data,
                drafts_data,
                designations_data,
            ]
                  
    if not ipr_dtl.legacy_url_0 and (ipr_dtl.notes or ipr_dtl.patents):
        if ipr_dtl.generic:
            disclosure_c = (
                'C. Does this disclosure apply to all IPR owned by the submitter?',
                'YES' if ipr_dtl.applies_to_all else 'NO' 
            )
        else:
            disclosure_c = (
                '''C. If an Internet-Draft or RFC includes multiple parts and it is not
   reasonably apparent which part of such Internet-Draft or RFC is alleged
   to be covered by the patent information disclosed in Section
   V(A) or V(B), it is helpful if the discloser identifies here the sections of
   the Internet-Draft or RFC that are alleged to be so
   covered.''', 
                ipr_dtl.document_sections
            )
        disclosure_data = [
            ('V. Disclosure of Patent Information (i.e., patents or patent applications required to be disclosed by Section 6 of RFC 3979)'),
            ('A. For granted patents or published pending patent applications, please provide the following information', ''),
            ('Patent, Serial, Publication, Registration, or Application/File number(s):', ipr_dtl.patents),
            ('Date(s) granted or applied for:', ipr_dtl.date_applied),
            ('Country:', ipr_dtl.country),
            ('Additional Notes:', ipr_dtl.notes),
            #('B. Does your disclosure relate to an unpublished pending patent application?', 'YES' if ipr_dtl.applies_to_all else 'NO'),
            ('B. Does your disclosure relate to an unpublished pending patent application?', 'YES' if ipr_dtl.is_pending == 1 else 'NO'),
            disclosure_c
        ]

    if not ipr_dtl.third_party and ipr_dtl.licensing_option: 
        lic_idx = ipr_dtl.licensing_option
        chosen_declaration = LICENSE_CHOICES[lic_idx-1][1]
        sub_opt = bool(
            lic_idx == 0 and ipr_dtl.lic_opt_a_sub
            or lic_idx == 1 and ipr_dtl.lic_opt_b_sub
            or lic_idx == 2 and ipr_dtl.lic_opt_c_sub
        )
        chosen_declaration += STDONLY_CHOICES[1][1] if sub_opt else ''
        chosen_declaration = (mark_safe("<strong>%s</strong>" % chosen_declaration), '')

        comments = ipr_dtl.comments or None
        lic_checkbox = ipr_dtl.lic_checkbox or None
        if comments or lic_checkbox:
            comments_notes_label = ('Licensing information, comments, notes or URL for further information:'),
            comments_notes = (mark_safe(
                "<strong>%s<br /><br />%s</strong>" % (
                    comments,
                    'The individual submitting this template represents and warrants that all terms and conditions that must be satisfied for implementers of any covered IETF specification to obtain a license have been disclosed in this IPR disclosure statement.' if lic_checkbox else ''
                )),
                ''
            )
        else:
            comments_notes_label = comments_notes = ''

        licensing_data = [
           ('VI. Licensing Declaration:'),
           ('The Patent Holder states that its position with respect to licensing any patent claims contained in the patent(s) or patent application(s) disclosed above that would necessarily be infringed by implementation of the technology required by the relevant IETF specification ("Necessary Patent Claims"), for the purpose of implementing such specification, is as follows(select one licensing declaration option only):', ''), 
            chosen_declaration,
            comments_notes_label,
            comments_notes 
        ]

    if contact_three and contact_three[0].name:
        contact_three = contact_three[0]
        contact_three_data = [
            ('VII. Contact Information of Submitter of this Form (if different from IETF Participant in Section III above):'),
            ('Name:', contact_three.name),
            ('Title:', contact_three.title),
            ('Department:', contact_three.department),
            ('Address1:', contact_three.address1),
            ('Address2:', contact_three.address2),
            ('Telephone:', contact_three.telephone),
            ('Fax:', contact_three.fax),
            ('Email:', contact_three.email)
        ]
    
    if ipr_dtl.other_notes:
        notes_data = (
            ('VIII. Other Notes:'),
            (mark_safe("<strong>%s</strong>" % ipr_dtl.other_notes), '')
        )    

    if not (not ipr_dtl.legacy_url_0 and (ipr_dtl.notes or ipr_dtl.patents)):
        # FIXME: behavior as perl, but is quite confusing and seems wrong
        licensing_data = contact_three_data = notes_data = ()


    page_data = [
        [
           ('I. %sPatent Holder/Applicant ("Patent Holder"):' % possible),
           ('Legal Name:', ipr_dtl.legal_name),
        ],
        contact_one_data,
        contact_two_data,
        document_data,
        disclosure_data,
        licensing_data,
        contact_three_data,
        notes_data,
    ]
    return dict(
        ipr_title = ipr_dtl.title,
        header_text = header_text,
        legacy_links = legacy_links,
        submitted_date = ipr_dtl.submitted_date,
        page_data = page_data,
        footer_text = footer_text,
        controls = controls,
    )
# end admin_detail

@template('ipradmin/create.html')
def admin_create(request):
    if request.method == 'POST':
        ipr_detail_form = IprDetailForm(request.POST, request.FILES, formtype='create')
        ipr_contact_formset = IPRContactFormset(request.POST)
        if ipr_detail_form.is_valid() and \
                ipr_contact_formset.forms[0].is_valid():
            ipr_detail = ipr_detail_form.save()
            ipr_contact_formset.forms[0].save(ipr_detail)
            if ipr_contact_formset.forms[1].is_valid():
                ipr_contact_formset.forms[1].save(ipr_detail)
            if ipr_contact_formset.forms[2].is_valid():
                ipr_contact_formset.forms[2].save(ipr_detail)
            return HttpResponseRedirect(reverse('ipr_admin_list'))
    else:
        ipr_detail_form = IprDetailForm(formtype='create')
        ipr_contact_formset = IPRContactFormset(initial=[
                {'contact_type' : 1, 'legend' : "II. Patent Holder's Contact for License Application "},
                {'contact_type' : 2, 'legend' : "III. Contact Information for the IETF Participant Whose Personal Belief Triggered the Disclosure in this Template (Optional): "},
                {'contact_type' : 3, 'legend' : "VII. Contact Information of Submitter of this Form (if different from IETF Participant in Section III above)"}])
    return dict(licensing_option_labels = ('a', 'b', 'c', 'd', 'e', 'f'),
                ipr_detail_form = ipr_detail_form,
                ipr_contact_formset = ipr_contact_formset)
# end admin_create

@template('ipradmin/update.html')
def admin_update(request, ipr_id):
    if request.method == 'POST':
        ipr_detail_form = IprDetailForm(
            request.POST, 
            request.FILES, 
            formtype='update', 
            instance=IprDetail.objects.get(ipr_id=ipr_id)
        )
        ipr_contact_formset = IPRContactFormset(
            request.POST, 
        )
        if ipr_detail_form.is_valid() and \
           ipr_contact_formset.forms[0].is_valid():
            ipr_detail = ipr_detail_form.save(commit=False)
            if 'update_ipr' in request.POST:
                if ipr_detail.third_party:
                    return HttpResponseRedirect('/ipradmin/admin/notify/%s?from=update' % ipr_id)
                else:
                    redirect_url = ''
            else: # remove
                redirect_url = reverse('ipr_admin_list')
                if 'admin_remove_ipr' in request.POST:
                    ipr_detail.status = 2
                elif 'request_remove_ipr' in request.POST:
                    ipr_detail.status = 3
            ipr_detail.save()
            ipr_contact_formset.forms[0].save(ipr_detail)
            if ipr_contact_formset.forms[1].is_valid():
                ipr_contact_formset.forms[1].save(ipr_detail)
            if ipr_contact_formset.forms[2].is_valid():
                ipr_contact_formset.forms[2].save(ipr_detail)
            return HttpResponseRedirect(redirect_url)
        else:
            pass
    else: # GET
        ipr_detail_form = IprDetailForm(
            formtype='update', 
            instance=IprDetail.objects.get(ipr_id=ipr_id)
        )
        ipr_contact_formset = IPRContactFormset(
            initial = get_contact_initial_data(ipr_id)
        )
    return dict(licensing_option_labels = ('a', 'b', 'c', 'd', 'e', 'f'),
                ipr_detail_form = ipr_detail_form,
                ipr_contact_formset = ipr_contact_formset)
# end admin_update

def get_contact_initial_data(ipr_id):
    c1_data, c2_data, c3_data = (
        {'contact_type' : '1', 'legend' : "II. Patent Holder's Contact for License Application "},
        {'contact_type' : '2', 'legend' : "III. Contact Information for the IETF Participant Whose Personal Belief Triggered the Disclosure in this Template (Optional): "},
        {'contact_type' : '3', 'legend' : "VII. Contact Information of Submitter of this Form (if different from IETF Participant in Section III above)"}
    )
    ipr_dtl = IprDetail.objects.get(ipr_id=ipr_id)
    c1, c2, c3 = [ipr_dtl.contact.filter(contact_type=x).order_by('-pk') for x in [1,2,3]]
    if c1:
        c1 = c1[0]
        c1_data.update({
            'name': c1.name,
            'title': c1.title,
            'department': c1.department,
            'address1': c1.address1,
            'address2': c1.address2,
            'telephone': c1.telephone,
            'fax': c1.fax,
            'email': c1.email
        })
    if c2:
        c2 = c2[0]
        c2_data.update({
            'name': c2.name,
            'title': c2.title,
            'department': c2.department,
            'address1': c2.address1,
            'address2': c2.address2,
            'telephone': c2.telephone,
            'fax': c2.fax,
            'email': c2.email
        })
    if c3:
        c3 = c3[0]
        c3_data.update({
            'name': c3.name,
            'title': c3.title,
            'department': c3.department,
            'address1': c3.address1,
            'address2': c3.address2,
            'telephone': c3.telephone,
            'fax': c3.fax,
            'email': c3.email
        })
    return [c1_data, c2_data, c3_data]

@jsonapi
def ajax_rfc_num(request):
    if request.method != 'GET' or not request.GET.has_key('term'):
        return { 'success' : False, 'error' : 'No term submitted or not GET' }
    q = request.GET.get('term')
    
    results = DocAlias.objects.filter(name__startswith='rfc%s' % q)
    if results.count() > 20:
        results = results[:20]
    elif results.count() == 0:
        return { 'success' : False, 'error' : "No results" }
    response = [ dict(id=r.id, label=unicode(r.name)+" "+r.document.title) for r in results ]

    return response

@jsonapi
def ajax_internet_draft(request):
    if request.method != 'GET' or not request.GET.has_key('term'):
        return { 'success' : False, 'error' : 'No term submitted or not GET' }
    q = request.GET.get('term')

    results = DocAlias.objects.filter(name__icontains=q)
    if results.count() > 20:
        results = results[:20]
    elif results.count() == 0:
        return { 'success' : False, 'error' : "No results" }

    response = [dict(id=r.id, label = r.name) for r in results]
    return response
