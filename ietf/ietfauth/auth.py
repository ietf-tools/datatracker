# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.auth.backends import ModelBackend
from django.core.validators import email_re
from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from ietf.ietfauth.models import UserMap
import md5

def compat_check_password(user, raw_password):
    """
    Returns a boolean of whether the raw_password was correct. Handles
    crypt and htdigest formats, and updates the password to htdigest
    on first use.  This is like User.check_password().
    """
    enc_password = user.password
    algo, salt, hsh = enc_password.split('$')
    if algo == 'crypt':
        import crypt
        is_correct = ( salt + hsh == crypt.crypt(raw_password, salt) )
	if is_correct:
	    # upgrade to htdigest
	    set_password(user, raw_password)
	return is_correct
    if algo == 'htdigest':
	# Check username hash.
	is_correct = ( hsh == htdigest( user.username, raw_password ) )
	if not is_correct:
	    # Try to check email hash, which we stored in the profile.
	    # If the profile doesn't exist, that's odd but we shouldn't
	    # completely fail, so try/except it.
	    try:
		is_correct = ( user.get_profile().email_htdigest == htdigest( user.email, raw_password ) )
	    except ObjectDoesNotExist:
		# no user profile to store the htdigest, so can't check it.
		pass
	return is_correct
    # permit django passwords, but upgrade to htdigest
    is_correct = user.check_password(raw_password)
    if is_correct:
	# upgrade to htdigest
	set_password(user, raw_password)
    return is_correct

# Based on http://www.djangosnippets.org/snippets/74/
#  but modified to use compat_check_password for all users.
class EmailBackend(ModelBackend):
    def authenticate(self, username=None, password=None):
	try:
	    if email_re.search(username):
                user = User.objects.get(email__iexact=username)
	    else:
		user = User.objects.get(username__iexact=username)
	except User.DoesNotExist:
	    #
	    # See if there's an IETF person with this address:
	    try:
		usermap = UserMap.objects.distinct().get(person__emailaddress__address__iexact=username)
	    except UserMap.DoesNotExist:
		return None
	    except AssertionError:
		# multiple UserMaps, should never happen!
		return None
	    user = usermap.user
	if compat_check_password(user, password):
	    return user
        return None

    def get_user(self, user_id):
	try:
	    return User.objects.get(pk=user_id)
	except User.DoesNotExist:
	    return None

def htdigest( username, password, realm=None ):
    """Returns a hashed password in the Apache htdigest format, which
    is used in an AuthDigestFile ."""
    if realm is None:
	try:
	    realm = settings.DIGEST_REALM
	except AttributeError:
	    realm = 'IETF'
    return md5.md5( ':'.join( [ username, realm, password ] ) ).hexdigest()

def set_password( user, password, realm=None ):
    # The username-hashed digest goes in the user database;
    # the email-address-hashed digest goes in the userprof.
    user.password = '$'.join( [ 'htdigest', '',
   		 htdigest( user.username, password, realm ) ] )
    user.save()
    ( userprof, created ) = UserMap.objects.get_or_create( user=user )
    userprof.email_htdigest = htdigest( user.email, password, realm )
    userprof.rfced_htdigest = htdigest( user.email, password, 'RFC Editor' )
    userprof.save()
