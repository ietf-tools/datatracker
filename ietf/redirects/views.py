# Copyright The IETF Trust 2007, All Rights Reserved

from django.http import HttpResponsePermanentRedirect, Http404, BadHeaderError
from django.shortcuts import get_object_or_404
import re

from ietf.redirects.models import Redirect, Command

def redirect(request, path="", script=""):
    if path:
	script = path + "/" + script
    redir = get_object_or_404(Redirect, cgi=script)
    url = "/" + redir.url + "/"
    (rest, remove) = (redir.rest, redir.remove)
    remove_args = []
    cmd = None
    #
    # First look for flag items, stored in the database
    # as a command with a leading "^".
    for flag in redir.commands.all().filter(command__startswith='^'):
	fc = flag.command[1:].split("^")
	if len(fc) > 1:
	    if request.REQUEST.get('command') != fc[1]:
		continue
	if request.REQUEST.has_key(fc[0]):
	    remove_args.append(fc[0])
	    num = re.match('(\d+)', request.REQUEST[fc[0]])
	    if (num and int(num.group(1))) or (num is None):
		cmd = flag
	    break
    #
    # If that search didn't result in a match, then look
    # for an exact match for the command= parameter.
    if cmd is None:
	try:
	    cmd = redir.commands.all().get(command=request.REQUEST['command'])
	except Command.DoesNotExist:
	    pass	# it's ok, there's no more-specific request.
	except KeyError:
	    pass	# it's ok, request didn't have 'command'.
	except:
	    pass	# strange exception like the one described in
	    		# http://merlot.tools.ietf.org/tools/ietfdb/ticket/179 ?
			# just ignore the command string.
    if cmd is not None:
	remove_args.append('command')
	if cmd.url:
	    rest = cmd.url + "/"
	else:
	    rest = ""
	if cmd.suffix:
	    rest = rest + cmd.suffix.rest
	    remove = cmd.suffix.remove
	else:
	    remove = ""
    try:
        # This throws exception (which gets caught below) if request 
        # contains non-ASCII characters. The old scripts didn't support 
        # non-ASCII characters anyway, so there's no need to handle 
        # them fully correctly in these redirects.
	url += str(rest % request.REQUEST)
	url += "/"
    except:
	# rest had something in it that request didn't have, so just
	# redirect to the root of the tool.
	pass
    # Be generous in what you accept: collapse multiple slashes
    url = re.sub(r'/+', '/', url)
    if remove:
	url = re.sub(re.escape(remove) + "/?$", "", url)
    # If there is a dot in the last url segment, remove the
    # trailing slash.  This is basically the inverse of the
    # APPEND_SLASH middleware.
    if '/' in url and '.' in url.split('/')[-2]:
	url = url.rstrip('/')
    # Copy the GET arguments, remove all the ones we were
    # expecting and if there are any left, add them to the URL.
    get = request.GET.copy()
    remove_args += re.findall(r'%\(([^)]+)\)', rest)
    for arg in remove_args:
	if get.has_key(arg):
	    get.pop(arg)
    if get:
	url += '?' + get.urlencode()
    try:
        return HttpResponsePermanentRedirect(url)
    except BadHeaderError, e:
        raise Http404
