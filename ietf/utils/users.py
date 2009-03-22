# Copyright The IETF Trust 2007, All Rights Reserved
#

from ietf.ietfauth.models import UserMap
from ietf.ietfauth.auth import set_password
from django.contrib.auth.models import User
from django.template import defaultfilters

class UserAlreadyExists(Exception):
    pass

def create_user(user, email, person, pw=None, cryptpw=None):
    try:
	umap = UserMap.objects.get(person = person)
	u = umap.user
	raise UserAlreadyExists("Already in system as %s when adding %s (%s)" % ( u.username, user, email ), u)
    except UserMap.DoesNotExist:
	pass
    if user is None or '@' in user:
	# slugify to remove non-ASCII; slugify uses hyphens but
	# user schema says underscore.
	user = defaultfilters.slugify(str(person)).replace("-", "_")
    if email is None:
	email = person.email()[1]
    # Make sure the username is unique.
    # If it already exists, 
    #  1. if the email is the same then skip, it's the same person
    #  2. otherwise, add a number to the end of the username
    #     and loop.
    add = ''
    while True:
	try:
	    t = user
	    if add:
		t += "%d" % ( add )
	    u = User.objects.get(username__iexact = t)
	except User.DoesNotExist:
	    u = None
	    user = t
	    break
	if u.email == email:
	    break
	else:
	    if add == '':
		add = 2
	    else:
		add = add + 1
    if not u:
	try:
	    map = UserMap.objects.get(person = person)
	    u = map.user
	except UserMap.DoesNotExist:
	    pass
    if u:
	# Fill in the user's name from the IETF data
	if u.first_name != person.first_name or u.last_name != person.last_name:
	    u.first_name = person.first_name
	    u.last_name = person.last_name
	    u.save()
	# make sure that the UserMap gets created
	umap, created = UserMap.objects.get_or_create(user = u,
					defaults={'person': person})
	if not created:
	    umap.person = person
	    umap.save()
	raise UserAlreadyExists("Already in system as %s when adding %s (%s)" % ( u.username, user, email ), u)
    else:
	if cryptpw:
	    password = 'crypt$%s$%s' % ( cryptpw[:2], cryptpw[2:] )
	else:
	    password = '!' # no hash
	u = User(username = user, email = email, password = password, first_name = person.first_name, last_name = person.last_name )
	if pw:
	    set_password(u, pw)
	#print "Saving user: username='%s', email='%s'" % ( u.username, u.email )
	u.save()
    umap, created = UserMap.objects.get_or_create(user = u,
				defaults={'person': person})
    if not created:
	umap.person = person
	umap.save()

    return u
