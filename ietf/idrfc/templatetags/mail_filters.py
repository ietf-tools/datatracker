from django import template
from django.core.cache import cache
from django.template import loader
from ietf.idtracker.models import Area

register = template.Library()

@register.filter(name='std_level_prompt')
def std_level_prompt(doc):
    """
    Returns the name from the std level names table corresponding
    to the object's intended_std_level (with the word RFC appended in some
    cases), or a prompt requesting that the intended_std_level be set."""
    
    prompt = "*** YOU MUST SELECT AN INTENDED STATUS FOR THIS DRAFT AND REGENERATE THIS TEXT ***"

    if doc.intended_std_level:
       prompt = doc.intended_std_level.name
       if doc.intended_std_level_id in ('inf','exp','hist'):
         prompt = prompt + " RFC"

    return prompt


@register.filter(name='std_level_prompt_with_article')
def std_level_prompt_with_article(doc):
    """
    Returns the standard level prompt prefixed with an appropriate article."""

    # This is a very crude way to select between "a" and "an", but will
    # work for the standards levels in the standards level names table
    # Grammar war alert: This will generate "an historic"
    article = ""
    if doc.intended_std_level:
       article = "a"
       if doc.intended_std_level.name[0].lower() in "aehiou":
         article = "an"
    return article+" "+std_level_prompt(doc)

