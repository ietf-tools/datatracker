import time, random, hashlib

from django.conf import settings

def generate_unique_key(max_length=32):
    return hashlib.sha256(settings.SECRET_KEY + ("%.16f" % time.time()) + ("%.16f" % random.random())).hexdigest()[:max_length]

