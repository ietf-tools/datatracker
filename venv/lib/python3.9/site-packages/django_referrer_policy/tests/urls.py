from django.conf.urls import url
from django.http import HttpResponse


def view(request):
    """
    A minimal view for use in testing.

    """
    return HttpResponse('Content.')


urlpatterns = [
    url(r'^referrer-policy-middleware$',
        view,
        name='test-referrer-policy-middleware'),
]
