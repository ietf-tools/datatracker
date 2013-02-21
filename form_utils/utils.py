"""
utility functions for django-form-utils

Time-stamp: <2009-03-26 12:32:41 carljm utils.py>

"""
from django.template import loader

def select_template_from_string(arg):
    """
    Select a template from a string, which can include multiple
    template paths separated by commas.
    
    """
    if ',' in arg:
        tpl = loader.select_template(
            [tn.strip() for tn in arg.split(',')])
    else:
        tpl = loader.get_template(arg)
    return tpl
