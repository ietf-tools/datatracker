# Copyright The IETF Trust 2007-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re

def normalize_draftname(string):
    string = string.strip()
    string = re.sub(r"\.txt$","",string)
    string = re.sub(r"-\d\d$","",string)
    return string
