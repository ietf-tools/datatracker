# Copyright The IETF Trust 2007, All Rights Reserved

from django.db import models

class Redirect(models.Model):
    """Mapping of CGI script to url.  The "rest" is a
    sprintf-style string with %(param)s entries to insert
    parameters from the request, and is appended to the
    url.  An exception in formatting "rest" results in
    just the bare url being used.  "remove" is removed
    from the end of the resulting url before redirecting,
    in case some values of "rest" add too much.

    If there is a "command" parameter, a matching row is
    searched for in the Command table to see if there
    is a different value of rest= and remove=.
    """
    cgi = models.CharField(max_length=50, unique=True, blank=True)
    url = models.CharField(max_length=255)
    rest = models.CharField(max_length=100, blank=True)
    remove = models.CharField(max_length=50, blank=True)
    def __str__(self):
	return "%s -> %s/%s" % (self.cgi, self.url, self.rest)
    class Admin:
        pass

class Suffix(models.Model):
    """This is a "rest" and "remove" (see Redirect class)
    for requests with command=.
    """
    rest = models.CharField(max_length=100, blank=True)
    remove = models.CharField(max_length=50, blank=True)
    def __str__(self):
	return "-> %s - %s" % (self.rest, self.remove)
    class Meta:
        verbose_name_plural="Suffixes"
    class Admin:
        pass

class Command(models.Model):
    """When a request comes in with a command= argument,
    the command is looked up in this table to see if there
    are more specific "rest" and "remove" arguments to
    use than those specified in the Redirect class that
    matched.  The optional "url" is prepended to the "rest".
    """
    command = models.CharField(max_length=50)
    url = models.CharField(max_length=50, blank=True)
    script = models.ForeignKey(Redirect, related_name='commands', editable=False)
    suffix = models.ForeignKey(Suffix, null=True, blank=True)
    def __str__(self):
	ret = "%s?command=%s" % (self.script.cgi, self.command)
	if self.suffix_id:
	    ret += " %s" % (self.suffix)
	return ret
    class Meta:
	unique_together = (("script", "command"), )
    class Admin:
	pass

# changes done by convert-096.py:changed maxlength to max_length
# removed core
# removed edit_inline
