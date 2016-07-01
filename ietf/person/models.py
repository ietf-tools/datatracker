# Copyright The IETF Trust 2007, All Rights Reserved

import datetime
from hashids import Hashids
from unidecode import unidecode
from urlparse import urljoin

from django.conf import settings

from django.db import models
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.utils.text import slugify


from ietf.person.name import name_parts, initials
from ietf.utils.mail import send_mail_preformatted
from ietf.utils.storage import NoLocationMigrationFileSystemStorage

class PersonInfo(models.Model):
    time = models.DateTimeField(default=datetime.datetime.now)      # When this Person record entered the system
    # The normal unicode form of the name.  This must be
    # set to the same value as the ascii-form if equal.
    name = models.CharField("Full Name (Unicode)", max_length=255, db_index=True, help_text="Preferred form of name.")
    # The normal ascii-form of the name.
    ascii = models.CharField("Full Name (ASCII)", max_length=255, help_text="Name as rendered in ASCII (Latin, unaccented) characters.")
    # The short ascii-form of the name.  Also in alias table if non-null
    ascii_short = models.CharField("Abbreviated Name (ASCII)", max_length=32, null=True, blank=True, help_text="Example: A. Nonymous.  Fill in this with initials and surname only if taking the initials and surname of the ASCII name above produces an incorrect initials-only form. (Blank is OK).")
    affiliation = models.CharField(max_length=255, blank=True, help_text="Employer, university, sponsor, etc.")
    address = models.TextField(max_length=255, blank=True, help_text="Postal mailing address.")
    biography = models.TextField(blank=True, help_text="Short biography for use on leadership pages. Use plain text or reStructuredText markup.")
    photo = models.ImageField(storage=NoLocationMigrationFileSystemStorage(location=settings.PHOTOS_DIR),upload_to=settings.PHOTOS_DIRNAME,blank=True, default=None)
    photo_thumb = models.ImageField(storage=NoLocationMigrationFileSystemStorage(location=settings.PHOTOS_DIR),upload_to=settings.PHOTOS_DIRNAME,blank=True, default=None)

    def __unicode__(self):
        return self.plain_name()
    def name_parts(self):
        return name_parts(self.name)
    def ascii_parts(self):
        return name_parts(self.ascii)
    def short(self):
        if self.ascii_short:
            return self.ascii_short
        else:
            prefix, first, middle, last, suffix = self.ascii_parts()
            return (first and first[0]+"." or "")+(middle or "")+" "+last+(suffix and " "+suffix or "")
    def plain_name(self):
        if not hasattr(self, '_cached_plain_name'):
            prefix, first, middle, last, suffix = name_parts(self.name)
            self._cached_plain_name = u" ".join([first, last])
        return self._cached_plain_name
    def ascii_name(self):
        if not hasattr(self, '_cached_ascii_name'):
            if self.ascii:
                # It's possibly overkill with unidecode() here, but needed until
                # we're validating the content of the ascii field, and have
                # verified that the field is ascii clean in the database:
                self._cached_ascii_name = unidecode(self.ascii) 
            else:
                self._cached_ascii_name = unidecode(self.plain_name())
        return self._cached_ascii_name
    def initials(self):
        return initials(self.ascii or self.name)
    def last_name(self):
        return name_parts(self.name)[3]
    def role_email(self, role_name, group=None):
        """Lookup email for role for person, optionally on group which
        may be an object or the group acronym."""
        if group:
            from ietf.group.models import Group
            if isinstance(group, str) or isinstance(group, unicode):
                group = Group.objects.get(acronym=group)
            e = Email.objects.filter(person=self, role__group=group, role__name=role_name)
        else:
            e = Email.objects.filter(person=self, role__group__state="active", role__name=role_name)
        if e:
            return e[0]
        # no cigar, try the complete set before giving up
        e = self.email_set.order_by("-active", "-time")
        if e:
            return e[0]
        return None
    def email(self):
        e = self.email_set.filter(primary=True).first()
        if not e:
            e = self.email_set.filter(active=True).order_by("-time").first()
        return e
    def email_address(self):
        e = self.email()
        if e:
            return e.address
        else:
            return ""
    def formatted_email(self):
        e = self.email_set.filter(primary=True).first()
        if not e:
            e = self.email_set.order_by("-active", "-time").first()
        if e:
            return e.formatted_email()
        else:
            return ""
    def full_name_as_key(self):
        # this is mostly a remnant from the old views, needed in the menu
        return self.plain_name().lower().replace(" ", ".")

    def photo_name(self,thumb=False):
        hasher = Hashids(salt='Person photo name salt',min_length=5)
        _, first, _, last, _ = name_parts(self.ascii)
        return u'%s-%s%s' % ( slugify(u"%s %s" % (first, last)), hasher.encode(self.id), '-th' if thumb else '' )

    class Meta:
        abstract = True

class Person(PersonInfo):
    user = models.OneToOneField(User, blank=True, null=True)

    def save(self, *args, **kwargs):
        created = not self.pk
        super(Person, self).save(*args, **kwargs)
        if created:
            if Person.objects.filter(name=self.name).count() > 1 :
                msg = render_to_string('person/mail/possible_duplicates.txt',
                                       dict(name=self.name,
                                            persons=Person.objects.filter(name=self.name),
                                            settings=settings
                                            ))
                send_mail_preformatted(None, msg)
        if not self.name in [ a.name for a in self.alias_set.filter(name=self.name) ]:
            self.alias_set.create(name=self.name)
        if self.ascii and self.name != self.ascii:
            if not self.ascii in [ a.name for a in self.alias_set.filter(name=self.ascii) ]:
                self.alias_set.create(name=self.ascii)

    #this variable, if not None, may be used by url() to keep the sitefqdn.
    default_hostscheme = None

    @property
    def defurl(self):
        return urljoin(self.default_hostscheme,self.json_url())

    def json_url(self):
        return "/person/%s.json" % (self.id, )

    # return info about the person
    def json_dict(self, hostscheme):
        ct1 = dict()
        ct1['person_id'] = self.id
        ct1['href']      = urljoin(hostscheme, self.json_url())
        ct1['name']      = self.name
        ct1['ascii']     = self.ascii
        ct1['affiliation']= self.affiliation
        return ct1

class PersonHistory(PersonInfo):
    person = models.ForeignKey(Person, related_name="history_set")
    user = models.ForeignKey(User, blank=True, null=True)

class Alias(models.Model):
    """This is used for alternative forms of a name.  This is the
    primary lookup point for names, and should always contain the
    unicode form (and ascii form, if different) of a name which is
    recorded in the Person record.
    """
    person = models.ForeignKey(Person)
    name = models.CharField(max_length=255, db_index=True)

    def save(self, *args, **kwargs):
        created = not self.pk
        super(Alias, self).save(*args, **kwargs)
        if created:
            if Alias.objects.filter(name=self.name).exclude(person=self.person).count() > 0 :
                msg = render_to_string('person/mail/possible_duplicates.txt',
                                       dict(name=self.name,
                                            persons=Person.objects.filter(alias__name=self.name),
                                            settings=settings
                                            ))
                send_mail_preformatted(None, msg)


    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Aliases"

class Email(models.Model):
    address = models.CharField(max_length=64, primary_key=True)
    person = models.ForeignKey(Person, null=True)
    time = models.DateTimeField(auto_now_add=True)
    primary = models.BooleanField(default=False)
    active = models.BooleanField(default=True)      # Old email addresses are *not* purged, as history
                                        # information points to persons through these
    def __unicode__(self):
        return self.address or "Email object with id: %s"%self.pk

    def get_name(self):
        return self.person.plain_name() if self.person else self.address

    def formatted_email(self):
        if self.person and self.person.ascii:
            return u'"%s" <%s>' % (self.person.ascii, self.address)
        else:
            return self.address

    def invalid_address(self):
        # we have some legacy authors with unknown email addresses
        return self.address.startswith("unknown-email") and "@" not in self.address

    def email_address(self):
        """Get valid, current email address; in practise, for active,
        non-invalid addresses it is just the address field. In other
        cases, we default to person's email address."""
        if self.invalid_address() or not self.active:
            if self.person:
                return self.person.email_address()
            return
        return self.address

