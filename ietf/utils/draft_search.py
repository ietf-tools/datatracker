# Copyright The IETF Trust 2007-2019, All Rights Reserved
import re

def normalize_draftname(string):
    string = string.strip()
    string = re.sub(r"\.txt$","",string)
    string = re.sub(r"-\d\d$","",string)
    return string
