# Copyright The IETF Trust 2007-2019, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.settings_local import *                  # pyflakes:ignore

DJANGO_VITE["default"] |= {
    "dev_mode": True,
    "dev_server_port": 3000,
}
