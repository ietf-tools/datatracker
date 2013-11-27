import time, random, hashlib

from django.conf import settings

def generate_random_key(max_length=32):
    """Generate a random access token."""
    return hashlib.sha256(settings.SECRET_KEY + ("%.16f" % time.time()) + ("%.16f" % random.random())).hexdigest()[:max_length]

def generate_access_token(key, max_length=32):
    """Make an access token out of key."""
    assert key, "key must not be empty"
    # we hash it with the private key to make sure only we can
    # generate and use the final token - so storing the key in the
    # database is safe
    return hashlib.sha256(settings.SECRET_KEY + key).hexdigest()[:max_length]
