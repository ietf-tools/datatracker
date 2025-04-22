# Copyright The IETF Trust 2007-2019, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf import __version__
from ietf.settings import *                                          # pyflakes:ignore

STATIC_URL = "https://static.ietf.org/dt/%s/"%__version__
STATIC_ROOT = os.path.abspath(BASE_DIR + "/../static/")
