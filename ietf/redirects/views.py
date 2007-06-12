from django.http import HttpResponsePermanentRedirect,Http404
import re

from ietf.redirects.models import Redirect, Command

def redirect(request, path="", script=""):
    if path:
	script = path + "/" + script
    try:
	redir = Redirect.objects.get(cgi=script)
    except Redirect.DoesNotExist:
	raise Http404
    url = "/" + redir.url + "/"
    (rest, remove) = (redir.rest, redir.remove)
    cmd = None
    try:
	cmd = redir.commands.all().get(command=request.REQUEST['command'])
	if cmd.url:
	    rest = cmd.url + "/" + cmd.suffix.rest
	else:
	    rest = cmd.suffix.rest
	remove = cmd.suffix.remove
    except Command.DoesNotExist:
	pass	# it's ok, there's no more-specific request.
    except KeyError:
	pass	# it's ok, request didn't have 'command'.
    try:
	url += rest % request.REQUEST
	url += "/"
    except:
	# rest had something in it that request didn't have, so just
	# redirect to the root of the tool.
	pass
    # Be generous in what you accept: collapse multiple slashes
    url = re.sub(r'/+', '/', url)
    if remove:
	url = re.sub(re.escape(remove) + "/?$", "", url)
    # Copy the GET arguments, remove all the ones we were
    # expecting and if there are any left, add them to the URL.
    get = request.GET.copy()
    for arg in re.findall(r'%\(([^)]+)\)', rest):
	if get.has_key(arg):
	    get.pop(arg)
    # If we found a command in the database, there's no need to pass it along.
    if cmd and get.has_key('command'):
	get.pop('command')
    if get:
	url += '?' + get.urlencode()
    return HttpResponsePermanentRedirect(url)
