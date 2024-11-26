# Copyright The IETF Trust 2010-2022, All Rights Reserved
# -*- coding: utf-8 -*-


import email.utils
import email.header
import jsonfield
import uuid

from hashids import Hashids
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import CICharField
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse as urlreverse
from django.utils import timezone
from django.utils.encoding import smart_bytes
from django.utils.text import slugify

from simple_history.models import HistoricalRecords

import debug                            # pyflakes:ignore

from ietf.name.models import ExtResourceName
from ietf.person.name import name_parts, initials, plain_name
from ietf.utils.mail import send_mail_preformatted
from ietf.utils.storage import NoLocationMigrationFileSystemStorage
from ietf.utils.mail import formataddr
from ietf.person.name import unidecode_name
from ietf.utils import log
from ietf.utils.models import ForeignKey, OneToOneField


def name_character_validator(value):
    disallowed = "@:/"
    found = set(disallowed).intersection(value)
    if len(found) > 0:
        raise ValidationError(
            f"This name cannot contain the characters {', '.join(disallowed)}"
        )


class Person(models.Model):
    history = HistoricalRecords()
    user = OneToOneField(User, blank=True, null=True, on_delete=models.SET_NULL)
    time = models.DateTimeField(default=timezone.now)      # When this Person record entered the system
    # The normal unicode form of the name.  This must be
    # set to the same value as the ascii-form if equal.
    name = models.CharField("Full Name (Unicode)", max_length=255, db_index=True, help_text="Preferred long form of name.", validators=[name_character_validator])
    plain = models.CharField("Plain Name correction (Unicode)", max_length=64, default='', blank=True, help_text="Use this if you have a Spanish double surname.  Don't use this for nicknames, and don't use it unless you've actually observed that the datatracker shows your name incorrectly.", validators=[name_character_validator])
    # The normal ascii-form of the name.
    ascii = models.CharField("Full Name (ASCII)", max_length=255, help_text="Name as rendered in ASCII (Latin, unaccented) characters.", validators=[name_character_validator])
    # The short ascii-form of the name.  Also in alias table if non-null
    ascii_short = models.CharField("Abbreviated Name (ASCII)", max_length=32, null=True, blank=True, help_text="Example: A. Nonymous.  Fill in this with initials and surname only if taking the initials and surname of the ASCII name above produces an incorrect initials-only form. (Blank is OK).", validators=[name_character_validator])
    pronouns_selectable = jsonfield.JSONCharField("Pronouns", max_length=120, blank=True, null=True, default=list )
    pronouns_freetext = models.CharField(" ", max_length=30, null=True, blank=True, help_text="Optionally provide your personal pronouns. These will be displayed on your public profile page and alongside your name in Meetecho and, in future, other systems. Select any number of the checkboxes OR provide a custom string up to 30 characters.")
    biography = models.TextField(blank=True, help_text="Short biography for use on leadership pages. Use plain text or reStructuredText markup.")
    photo = models.ImageField(storage=NoLocationMigrationFileSystemStorage(), upload_to=settings.PHOTOS_DIRNAME, blank=True, default=None)
    photo_thumb = models.ImageField(storage=NoLocationMigrationFileSystemStorage(), upload_to=settings.PHOTOS_DIRNAME, blank=True, default=None)
    name_from_draft = models.CharField("Full Name (from submission)", null=True, max_length=255, editable=False, help_text="Name as found in an Internet-Draft submission.")

    def __str__(self):
        return self.plain_name()
    def get_absolute_url(self):
        return urlreverse('ietf.person.views.profile', kwargs={'email_or_name': self.name})
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
            if self.plain:
                self._cached_plain_name = self.plain
            else:
                self._cached_plain_name = plain_name(self.name)
        return self._cached_plain_name
    def ascii_name(self):
        if not hasattr(self, '_cached_ascii_name'):
            if self.ascii:
                # It's possibly overkill with unidecode() here, but needed until
                # we're validating the content of the ascii field, and have
                # verified that the field is ascii clean in the database:
                if not all(ord(c) < 128 for c in self.ascii):
                    self._cached_ascii_name = unidecode_name(self.ascii)
                else:
                    self._cached_ascii_name = self.ascii
            else:
                self._cached_ascii_name = unidecode_name(self.plain_name())
        return self._cached_ascii_name
    def plain_ascii(self):
        if not hasattr(self, '_cached_plain_ascii'):
            if self.ascii:
                if isinstance(self.ascii, bytes):
                    ascii = unidecode_name(self.ascii.decode('utf-8'))
                else:
                    ascii = unidecode_name(self.ascii)
            else:
                ascii = unidecode_name(self.name)
            prefix, first, middle, last, suffix = name_parts(ascii)
            self._cached_plain_ascii = (" ".join([first, last])).strip()
        return self._cached_plain_ascii
    def initials(self):
        return initials(self.ascii or self.name)
    def last_name(self):
        return name_parts(self.name)[3]
    def first_name(self):
        return name_parts(self.name)[1]
    def aliases(self):
        return [ str(a) for a in self.alias_set.all() ]

    def pronouns(self):
        if self.pronouns_selectable:
            return ", ".join(self.pronouns_selectable)
        else:
            return self.pronouns_freetext

    def role_email(self, role_name, group=None):
        """Lookup email for role for person, optionally on group which
        may be an object or the group acronym."""
        if group:
            from ietf.group.models import Group
            if isinstance(group, str):
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
        if not hasattr(self, '_cached_email'):
            e = self.email_set.filter(primary=True).first()
            if not e:
                e = self.email_set.filter(active=True).order_by("-time").first()
            self._cached_email = e
        return self._cached_email
    def email_allowing_inactive(self):
        if not hasattr(self, "_cached_email_allowing_inactive"):
            e = self.email()
            if not e:
                e = self.email_set.order_by("-time").first()
            log.assertion(statement="e is not None", note=f"Person {self.pk} has no Email objects")
            self._cached_email_allowing_inactive = e
        return self._cached_email_allowing_inactive
    def email_address(self):
        e = self.email()
        if e:
            return e.address
        else:
            return ""
    def formatted_ascii_email(self):
        e = self.email_set.filter(primary=True).first()
        if not e or not e.active:
            e = self.email_set.order_by("-active", "-time").first()
        if e:
            return e.formatted_ascii_email()
        else:
            return ""
    def formatted_email(self):
        e = self.email_set.filter(primary=True).first()
        if not e or not e.active:
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
        return '%s-%s%s' % ( slugify("%s %s" % (first, last)), hasher.encode(self.id), '-th' if thumb else '' )

    def has_drafts(self):
        from ietf.doc.models import Document
        return Document.objects.filter(documentauthor__person=self, type='draft').exists()

    def rfcs(self):
        from ietf.doc.models import Document
        rfcs = list(Document.objects.filter(documentauthor__person=self, type='rfc'))
        rfcs.sort(key=lambda d: d.name )
        return rfcs

    def active_drafts(self):
        from ietf.doc.models import Document

        return (
            Document.objects.filter(
                documentauthor__person=self,
                type="draft",
                states__type="draft",
                states__slug="active",
            )
            .distinct()
            .order_by("-time")
        )

    def expired_drafts(self):
        from ietf.doc.models import Document

        return (
            Document.objects.filter(
                documentauthor__person=self,
                type="draft",
                states__type="draft",
                states__slug__in=["repl", "expired", "auth-rm", "ietf-rm"],
            )
            .distinct()
            .order_by("-time")
        )

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

    def available_api_endpoints(self):
        from ietf.ietfauth.utils import has_role
        return list(set([ (v, n) for (v, n, r) in PERSON_API_KEY_VALUES if r==None or has_role(self.user, r) ]))

    def cdn_photo_url(self, size=80):
        if self.photo:
            if settings.SERVE_CDN_PHOTOS:
                source_url = self.photo.url
                if source_url.startswith(settings.IETF_HOST_URL):
                    source_url = source_url[len(settings.IETF_HOST_URL):]
                elif source_url.startswith('/'):
                    source_url = source_url[1:]
                return f'{settings.IETF_HOST_URL}cdn-cgi/image/fit=scale-down,width={size},height={size}/{source_url}'
            else:
                datatracker_photo_path = urlreverse('ietf.person.views.photo', kwargs={'email_or_name': self.email()})
                datatracker_photo_url = settings.IDTRACKER_BASE_URL + datatracker_photo_path
            return datatracker_photo_url
        else:
            return ''


class PersonExtResource(models.Model):
    person = ForeignKey(Person)
    name = models.ForeignKey(ExtResourceName, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=255, default='', blank=True)
    value = models.CharField(max_length=2083) # 2083 is the maximum legal URL length
    def __str__(self):
        priority = self.display_name or self.name.name
        return u"%s (%s) %s" % (priority, self.name.slug, self.value)

class Alias(models.Model):
    """This is used for alternative forms of a name.  This is the
    primary lookup point for names, and should always contain the
    unicode form (and ascii form, if different) of a name which is
    recorded in the Person record.
    """
    person = ForeignKey(Person)
    name = models.CharField(max_length=255, db_index=True)

    def save(self, *args, **kwargs):
        created = not self.pk
        super(Alias, self).save(*args, **kwargs)
        if created:
            if Alias.objects.filter(name=self.name).exclude(person=self.person).count() > 0 :
                msg = render_to_string('person/mail/possible_duplicates.txt',
                                       dict(name=self.name,
                                            persons=Person.objects.filter(alias__name=self.name).distinct(),
                                            settings=settings
                                            ))
                send_mail_preformatted(None, msg)


    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Aliases"

class Email(models.Model):
    history = HistoricalRecords()
    address = CICharField(max_length=64, primary_key=True, validators=[validate_email])
    person = ForeignKey(Person, null=True)
    time = models.DateTimeField(auto_now_add=True)
    primary = models.BooleanField(default=False)
    origin = models.CharField(max_length=150, blank=False, help_text="The origin of the address: the user's email address, or 'author: DRAFTNAME' if an Internet-Draft, or 'role: GROUP/ROLE' if a role.")       # User.username or Document.name
    active = models.BooleanField(default=True)      # Old email addresses are *not* purged, as history
                                                    # information points to persons through these

    def __str__(self):
        return self.address or "Email object with id: %s"%self.pk

    def get_name(self):
        return self.person.plain_name() if self.person else self.address

    def formatted_ascii_email(self):
        if self.person:
                return email.utils.formataddr((self.person.plain_ascii(), self.address))
        else:
            return self.address

    def name_and_email(self):
        """
        Returns name and email, e.g.: u'Ano Nymous <ano@nymous.org>'
        Is intended for display use, not in email context.
        Use self.formatted_email() for that.
        """
        if self.person:
            return "%s <%s>" % (self.person.plain_name(), self.address)
        else:
            return "<%s>" % self.address

    def formatted_email(self):
        """
        Similar to name_and_email(), but with email header-field
        encoded words (RFC 2047) and quotes as needed.
        """
        if self.person:
            return formataddr((self.person.plain_name(), self.address))
        else:
            return self.address

    def email_address(self):
        """Get valid, current email address; in practise, for active,
        non-invalid addresses it is just the address field. In other
        cases, we default to person's email address."""
        if not self.active:
            if self.person:
                return self.person.email_address()
            return
        return self.address

    def save(self, *args, **kwargs):
        if not self.origin:
            log.assertion('self.origin')
        super(Email, self).save(*args, **kwargs)

# "{key.id}{salt}{hash}
KEY_STRUCT = "i12s32s"

def salt():
    return uuid.uuid4().bytes[:12]

# Manual maintenance: List all endpoints that use @require_api_key here
PERSON_API_KEY_VALUES = [
    ("/api/iesg/position", "/api/iesg/position", "Area Director"),
    ("/api/v2/person/person", "/api/v2/person/person", "Robot"),
    ("/api/meeting/session/video/url", "/api/meeting/session/video/url", "Recording Manager"),
    ("/api/meeting/session/recording-name", "/api/meeting/session/recording-name", "Recording Manager"),
    ("/api/notify/meeting/registration", "/api/notify/meeting/registration", "Robot"),
    ("/api/notify/meeting/bluesheet", "/api/notify/meeting/bluesheet", "Recording Manager"),
    ("/api/notify/session/attendees", "/api/notify/session/attendees", "Recording Manager"),
    ("/api/notify/session/chatlog", "/api/notify/session/chatlog", "Recording Manager"),
    ("/api/notify/session/polls", "/api/notify/session/polls", "Recording Manager"),
    ("/api/appauth/authortools", "/api/appauth/authortools", None),
    ("/api/appauth/bibxml", "/api/appauth/bibxml", None),
]
PERSON_API_KEY_ENDPOINTS = sorted(list(set([ (v, n) for (v, n, r) in PERSON_API_KEY_VALUES ])))

class PersonalApiKey(models.Model):
    person   = ForeignKey(Person, related_name='apikeys')
    endpoint = models.CharField(max_length=128, null=False, blank=False, choices=PERSON_API_KEY_ENDPOINTS)
    created  = models.DateTimeField(default=timezone.now, null=False)
    valid    = models.BooleanField(default=True)
    salt     = models.BinaryField(default=salt, max_length=12, null=False, blank=False)
    count    = models.IntegerField(default=0, null=False, blank=False)
    latest   = models.DateTimeField(blank=True, null=True)

    @classmethod
    def validate_key(cls, s):
        import struct, hashlib, base64
        assert isinstance(s, bytes)
        try:
            key = base64.urlsafe_b64decode(s)
            id, salt, hash = struct.unpack(KEY_STRUCT, key)
        except Exception:
            return None
        k = cls.objects.filter(id=id)
        if not k.exists():
            return None
        k = k.first()
        if not k.valid:
            return None
        check = hashlib.sha256()
        for v in (str(id), str(k.person.id), k.created.isoformat(), k.endpoint, str(k.valid), salt, settings.SECRET_KEY):
            v = smart_bytes(v)
            check.update(v)
        return k if check.digest() == hash else None

    def hash(self):
        import struct, hashlib, base64
        if not hasattr(self, '_cached_hash'):
            hash = hashlib.sha256()
            # Hash over: ( id, person, created, endpoint, valid, salt, secret )
            for v in (str(self.id), str(self.person.id), self.created.isoformat(), self.endpoint, str(self.valid), self.salt, settings.SECRET_KEY):
                v = smart_bytes(v)
                hash.update(v)
            key = struct.pack(KEY_STRUCT, self.id, bytes(self.salt), hash.digest())
            self._cached_hash =  base64.urlsafe_b64encode(key).decode('ascii')
        return self._cached_hash

    def __str__(self):
        return "%s %-24s %-32s(%6d): %s ..." % (self.created.strftime("%Y-%m-%d %H:%M"), self.person.name, self.endpoint, self.count, self.hash()[:16])

PERSON_EVENT_CHOICES = [
    ("apikey_login", "API key login"),
    ("email_address_deactivated", "Email address deactivated"),
    ]

class PersonEvent(models.Model):
    person = ForeignKey(Person)
    time = models.DateTimeField(default=timezone.now, help_text="When the event happened")
    type = models.CharField(max_length=50, choices=PERSON_EVENT_CHOICES)
    desc = models.TextField()

    def __str__(self):
        return "%s %s at %s" % (self.person.plain_name(), self.get_type_display().lower(), self.time)

    class Meta:
        ordering = ['-time', '-id']
        indexes = [
            models.Index(fields=['-time', '-id']),
        ]

class PersonApiKeyEvent(PersonEvent):
    key = ForeignKey(PersonalApiKey)

