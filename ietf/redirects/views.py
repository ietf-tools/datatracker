from django.http import HttpResponseRedirect,Http404
import re

from ietf.redirects.models import Redirect, Command

def redirect(request, path="", script=""):
    if path:
	script = path + "/" + script
    try:
	redir = Redirect.objects.get(cgi=script)
    except Redirect.DoesNotExist:
	raise Http404
    url = redir.url + "/"
    (rest, remove) = (redir.rest, redir.remove)
    try:
	cmd = redir.commands.all().get(command=request.REQUEST['command'])
	if cmd.url:
	    rest = cmd.url + "/" + cmd.suffix.rest
	else:
	    rest = cmd.suffix.rest
	remove = cmd.suffix.remove
    except Command.DoesNotExist:
	pass	# it's ok, there's no more-specific request.
    except IndexError:
	pass	# it's ok, request didn't have 'command'.
    try:
	url += rest % request.REQUEST
    except:
	# rest had something in it that request didn't have, so just
	# redirect to the root of the tool.
	pass
    if remove:
	url = re.sub(re.escape(remove) + "/?$", "", url)
    return HttpResponseRedirect(url)
