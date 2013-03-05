from ietf import settings
from django.core import management
management.setup_environ(settings)

from ietf.group.models import *

import sys

def output_charter(group):
    report = render_to_string('groups/text_charter.txt', context)
    
    return report    
    
group = Group.objects.get(acronym='alto')
output_charter(group)