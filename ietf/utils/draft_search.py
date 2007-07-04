# Copyright The IETF Trust 2007, All Rights Reserved
import re

def normalize_draftname(string):
    string = string.strip()
    string = re.sub("\.txt$","",string)
    string = re.sub("-\d\d$","",string)
    return string
