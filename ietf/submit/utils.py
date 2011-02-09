import re

def check_idnits_success(idnits_message):
    success_re = re.compile('\s+Summary:\s+0\s+|No nits found')
    if success_re.search(idnits_message):
        return True
    return False
