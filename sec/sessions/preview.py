from django.contrib import messages
from django.contrib.formtools.preview import FormPreview
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from models import *

from sec.utils.shortcuts import get_group_or_404

class SessionFormPreview(FormPreview):
    form_template = 'sessions/new_preview.html'
    
    def parse_params(self, *args, **kwargs):
        group_id = kwargs.pop('group_id')
        
        group = get_group_or_404(group_id)
        group_name = str(group)
        #session_conflicts = session_conflicts_as_string(group)
        meeting = Meeting.objects.all().order_by('-meeting_num')[0]
    
        self.state['meeting'] = meeting
        self.state['group'] = group
        
    
    def preview_get(self, request):
        "Displays the form"
        f = self.form(auto_id=AUTO_ID)
        return render_to_response(self.form_template,
            {'form': f, 'stage_field': self.unused_name('stage'), 'state': self.state},
            context_instance=RequestContext(request))

    def done(self, request, cleaned_data):

        messages.success(request, 'Your request has been sent to %s' % 'XXX')
        url = reverse('sessions_main')
        return HttpResponseRedirect(url)
