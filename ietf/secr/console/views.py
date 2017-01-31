
from django.shortcuts import render

from ietf.doc.models import DocEvent
from ietf.ietfauth.utils import role_required

@role_required('Secretariat')
def main(request):
    '''
    Main view for the Console
    '''

    latest_docevent = DocEvent.objects.all().order_by('-time')[0]
    
    return render(request, 'console/main.html', {
        'latest_docevent': latest_docevent},
    )
