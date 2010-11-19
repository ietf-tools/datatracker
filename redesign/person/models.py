# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models

class Person(models.Model):
    time = models.DateTimeField(auto_now_add=True)      # When this Person record entered the system
    name = models.CharField(max_length=255)             # The normal unicode form of the name.  This must be
                                                        # set to the same value as the ascii-form if equal.
    ascii = models.CharField(max_length=255)            # The normal ascii-form of the name.
    ascii_short = models.CharField(max_length=32, null=True, blank=True)      # The short ascii-form of the name.  Also in alias table if non-null
    address = models.TextField(max_length=255, blank=True)
    def __unicode__(self):
        return self.name
    def _parts(self, name):
        prefix, first, middle, last, suffix = "", "", "", "", ""
        parts = name.split()
        if parts[0] in ["Mr", "Mr.", "Mrs", "Mrs.", "Ms", "Ms.", "Miss", "Dr.", "Doctor", "Prof", "Prof.", "Professor", "Sir", "Lady", "Dame", ]:
            prefix = parts[0];
            parts = parts[1:]
        if len(parts) > 2:
            if parts[-1] in ["Jr", "Jr.", "II", "2nd", "III", "3rd", ]:
                suffix = parts[-1]
                parts = parts[:-1]
        if len(parts) > 2:
            first = parts[0]
            last = parts[-1]
            middle = " ".join(parts[1:-1])
        elif len(parts) == 2:
            first, last = parts
        else:
            last = parts[0]
        return prefix, first, middle, last, suffix
    def name_parts(self):
        return self._parts(self.name)
    def ascii_parts(self):
        return self._parts(self.ascii)
    def short(self):
        if self.ascii_short:
            return self.ascii_short
        else:
            prefix, first, middle, last, suffix = self.ascii_parts()
            return (first and first[0]+"." or "")+(middle or "")+" "+last+(suffix and " "+suffix or "")

class Alias(models.Model):
    """This is used for alternative forms of a name.  This is the
    primary lookup point for names, and should always contain the
    unicode form (and ascii form, if different) of a name which is
    recorded in the Person record.
    """
    person = models.ForeignKey(Person)
    name = models.CharField(max_length=255)
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Aliases"

class Email(models.Model):
    address = models.CharField(max_length=64, primary_key=True)
    person = models.ForeignKey(Person, null=True)
    time = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)      # Old email addresses are *not* purged, as history
                                        # information points to persons through these
    def __unicode__(self):
        return self.address

    def get_name(self):
        return self.person.name if self.person else self.address
