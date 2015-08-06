
from django.core.exceptions import ObjectDoesNotExist

from ietf.eventmail.models import Recipe

def gather_addresses(slug,**kwargs):
    
    addrs = []

    try:
       recipe = Recipe.objects.get(slug=slug)
    except ObjectDoesNotExist:
       # TODO remove the raise here, or find a better way to detect runtime misconfiguration
       raise
       return addrs

    for ingredient in recipe.ingredients.all():
        addrs.extend(ingredient.gather(**kwargs))

    return addrs
