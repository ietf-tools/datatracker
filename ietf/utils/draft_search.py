# Copyright The IETF Trust 2007, All Rights Reserved
import re
from ietf.idtracker.models import InternetDraft

def normalize_draftname(string):
    string = string.strip()
    string = re.sub("\.txt$","",string)
    string = re.sub("-\d\d$","",string)
    return string

def draft_search(string):
    drafts = []
    if string:
        string = normalize_draftname(string)
        drafts = InternetDraft.objects.filter(filename__contains=string)
    return drafts
    