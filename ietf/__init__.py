# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from . import checks                           # pyflakes:ignore

# Version must stay in single quotes for automatic CI replace
# Don't add patch number here:
__version__ = '7.0.0-dev'

# Release hash must stay in single quotes for automatic CI replace
__release_hash__ = ''

# Release branch must stay in single quotes for automatic CI replace
__release_branch__ = ''

# set this to ".p1", ".p2", etc. after patching
__patch__   = ""

# Testing - do not commit
__release_hash__ = 'd489391b66bd67d8d702d82ef9f21006e9415385'
__release_branch__ = 'feat/bs5'