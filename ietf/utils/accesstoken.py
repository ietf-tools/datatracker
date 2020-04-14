# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import time, random, hashlib

from django.conf import settings
from django.utils.encoding import force_bytes, force_text


def generate_random_key(max_length=32):
    """Generate a random access token."""
    return hashlib.sha256(force_bytes(settings.SECRET_KEY) + (b"%.16f" % time.time()) + (b"%.16f" % random.random())).hexdigest()[:max_length]

def generate_access_token(key, max_length=32):
    """Make an access token out of key."""
    assert key, "key must not be empty"
    # we hash it with the private key to make sure only we can
    # generate and use the final token - so storing the key in the
    # database is safe
    return force_text(hashlib.sha256(force_bytes(settings.SECRET_KEY) + force_bytes(key)).hexdigest()[:max_length])
