# Copyright The IETF Trust 2015, All Rights Reserved

from inspect import getsourcelines

from django.shortcuts import render

from ietf.eventmail.models import Recipe, Ingredient

def show_patterns(request, eventmail_slug=None):
    recipes = Recipe.objects.all()
    if eventmail_slug:
        recipes = recipes.filter(slug=eventmail_slug) # TODO better 404 behavior here and below
    return render(request,'eventmail/show_patterns.html',{'eventmail_slug':eventmail_slug,
                                                          'recipes':recipes})
def show_ingredients(request, ingredient_slug=None):
    ingredients = Ingredient.objects.all()
    if ingredient_slug:
        ingredients = ingredients.filter(slug=ingredient_slug)
    for ingredient in ingredients:
        fname = 'gather_%s'%ingredient.slug
        if hasattr(ingredient,fname):
            ingredient.code = ''.join(getsourcelines(getattr(ingredient,fname))[0])
    return render(request,'eventmail/ingredient.html',{'ingredient_slug':ingredient_slug,
                                                            'ingredients':ingredients})
