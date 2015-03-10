# -*- coding: utf-8 -*-
from __future__ import unicode_literals

#from django.db import models, migrations # pyflakes:ignore
from django.db import migrations 
from django.conf import settings

from ietf.utils.mail import send_mail_text

# Tiny detail: making the text below look nice is of course dependent on
# how long the email addresses and draft name which are inserted into the
# text actually turn out to be.  Rather than bothering to re-flow the text,
# it can be noted that the average email address length, calculated over the
# addresses this will be run for, was 21, and the length of the string
# '%(inacive_email)s' is 18, so just formatting naturally should come out
# pretty nicely in most cases.


email_template = """
Hi,

As part of a review of active and inactive email addresses in the datatracker,
it has been found that your address <%(inactive_email)s>, which is mentioned
in the active draft %(draft_name)s, was set to inactive.

As a consequence of this, it would not be receiving notifications related to
that draft, from the datatracker or through the draft aliases.  The
notifications and aliases would instead have used <%(primary_email)s>.

This most likely was not what you intended when you used <%(inactive_email)s>
in the draft, so that address has now been set to active. The datatracker and
draft aliases will now use it.

If you have a datatracker account, and had manually set the status for
<%(inactive_email)s> to inactive, we apologize for interfering.  Please set it
to inactive again, by using https://datatracker.ietf.org/accounts/profile/. We
don't anticipate changing it automatically again.

If you don't have a datatracker account, then all should be good -- we've
simply set things to be the way they were expected to be.


Best regards,

    Henrik, via the inactive email migration script

"""

def activate_draft_email(apps, schema_editor):
    Document = apps.get_model("doc", "Document")
    print("\nSetting email addresses to active ...")
    change_count = 0
    notify_user_count = 0
    for doc in Document.objects.filter(type__slug='draft', states__slug='active').order_by('-time'):
        for email in doc.authors.all():
            if email.active == False:
                person = email.person
                primary = person.email_set.filter(active=True).order_by('-time').first()
                email.active = True
                email.save()
                change_count += 1
                # If there isn't a primary address, ther's no active
                # addresses, and it can't be other than right to change the
                # draft email address to active.  Otherwise, notify the owner.
                if primary:
                    notify_user_count +=1
                    primary_email = primary.address
                    inactive_email = email.address
                    if settings.SERVER_MODE == 'production':
                        context = dict(
                            primary_email=primary_email,
                            inactive_email=inactive_email,
                            draft_name=doc.name,
                            )
                        send_mail_text(
                            request=None,
                            to=[ primary_email, inactive_email ],
                            frm="Henrik Levkowetz <henrik@levkowetz.com>",
                            subject="Changed email settings for you in the datatracker",
                            txt= email_template % context,
                            extra={"Reply-To": "Secretariat <ietf-action@ietf.org>"},
                        )
                        print("Set %s email addresses to active" % change_count)
                        print("Notified %s users, who had at least one other active email." % notify_user_count)

def deactivate_draft_email(apps, scema_editor):
    """
    The backwards migration doesn't touch the active field of any email addresses.
    We don't have the information to exactly undo what the forward migration did,
    and on 08 Mar 2015, there were 1178 inactive email addresses coupled to active
    drafts, and 4237 active addresses coupled to active drafts.  The harm would
    be substantial if those active addresses were set to inactive.
    """
#     Document = apps.get_model("doc", "Document")
#     print(" Not setting email addresses to inactive")
#     count = 0
#     for doc in Document.objects.filter(type__slug='draft', states__slug='active'):
#         for email in doc.authors.all():
#             if email.active == True:
#                 #print email.address
#                 count += 1
#     print("Left %s active email addresses untouched " % count)

class Migration(migrations.Migration):

    dependencies = [
        ('person', '0003_auto_20150304_0829'),
        ('doc', '0002_auto_20141222_1749'),
    ]

    operations = [
        migrations.RunPython(
            activate_draft_email,
            deactivate_draft_email),
    ]
