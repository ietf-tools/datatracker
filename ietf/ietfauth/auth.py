# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.auth.backends import ModelBackend
from django.core.validators import email_re
from django.contrib.auth.models import User

def crypt_check_password(user, raw_password):
    """
    Returns a boolean of whether the raw_password was correct. Handles
    crypt format only, and updates the password to the hashed version
    on first use.  This is like User.check_password().
    """
    enc_password = user.password
    algo, salt, hsh = enc_password.split('$')
    if algo == 'crypt':
        import crypt
        is_correct = ( salt + hsh == crypt.crypt(raw_password, salt) )
	if is_correct:
	    user.set_password(raw_password)
	    user.save()
	return is_correct
    return user.check_password(raw_password)

# Based on http://www.djangosnippets.org/snippets/74/
#  but modified to use crypt_check_password for all users.
class EmailBackend(ModelBackend):
    def authenticate(self, username=None, password=None):
	try:
	    if email_re.search(username):
                user = User.objects.get(email__iexact=username)
	    else:
		user = User.objects.get(username__iexact=username)
	except User.DoesNotExist:
	    return None
	if crypt_check_password(user, password):
	    return user
        return None

    def get_user(self, user_id):
	try:
	    return User.objects.get(pk=user_id)
	except User.DoesNotExist:
	    return None

