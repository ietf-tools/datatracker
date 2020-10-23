# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-

"""Custom tags for the agenda filter template"""

from django import template

register = template.Library()

@register.filter
def agenda_width_scale(filter_categories, spacer_scale):
    """Compute the width scale for the agenda filter button table
    
    Button columns are spacer_scale times as wide as the spacer columns between
    categories. There is one fewer spacer column than categories.
    """
    category_count = len(filter_categories)
    column_count = sum([len(cat) for cat in filter_categories])
    # Refuse to return less than 1 to avoid width calculation problems.
    return max(spacer_scale * column_count + category_count - 1, 1) 
