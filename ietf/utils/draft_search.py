# Copyright The IETF Trust 2007, All Rights Reserved
import re
from ietf.idtracker.models import InternetDraft

def draft_search(s):
    drafts = []
    if s:
        # normalize the draft name.
        s = s.strip()
        s = re.sub("\.txt$","",s)
        s = re.sub("-\d\d$","",s)
        drafts = InternetDraft.objects.filter(filename__contains=s)
    return drafts
    