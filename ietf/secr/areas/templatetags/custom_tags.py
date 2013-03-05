from django import template
from ietf.secr.areas import models

register = template.Library()

@register.inclusion_tag('areas/directors.html')
def display_directors(area_id):
    area = models.Area.objects.get(area_acronym__exact=area_id)
    directors = models.AreaDirector.objects.filter(area=area)    
    return { 'directors': directors } 
