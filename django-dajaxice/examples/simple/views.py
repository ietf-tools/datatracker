# Create your views here.
from django.shortcuts import render

from dajaxice.core import dajaxice_functions


def index(request):

    return render(request, 'simple/index.html')
