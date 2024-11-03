# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from . import checks                           # pyflakes:ignore

# Version must stay in single quotes for automatic CI replace
# Don't add patch number here:
__version__ = '1.0.0-dev'

# Release hash must stay in single quotes for automatic CI replace
__release_hash__ = ''

# Release branch must stay in single quotes for automatic CI replace
__release_branch__ = ''

# set this to ".p1", ".p2", etc. after patching
__patch__   = ""

if __version__ == '1.0.0-dev' and __release_hash__ == '' and __release_branch__ == '':
    import subprocess
    branch = subprocess.run(
        ["/usr/bin/git", "branch", "--show-current"],
        capture_output=True,
    ).stdout.decode().strip()
    git_hash = subprocess.run(
        ["/usr/bin/git", "rev-parse", "head"],
        capture_output=True,
    ).stdout.decode().strip()
    rev = subprocess.run(
        ["/usr/bin/git", "describe", "--tags", git_hash],
        capture_output=True,
    ).stdout.decode().strip().split('-', 1)[0]
    __version__ = f"{rev}-dev"
    __release_branch__ = branch
    __release_hash__ = git_hash


# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celeryapp import app as celery_app

__all__ = ('celery_app',)
