# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-
# -*- check-flake8 -*-


from django.db.models import Q
from django.template.loader import render_to_string

from ietf.doc.models import RelatedDocument


class Edge(object):
    def __init__(self, relateddocument):
        self.relateddocument = relateddocument

    def __hash__(self):
        return hash("|".join([str(hash(nodename(self.relateddocument.source.name))),
                             str(hash(nodename(self.relateddocument.target.document.name))),
                             self.relateddocument.relationship.slug]))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    def sourcename(self):
        return nodename(self.relateddocument.source.name)

    def targetname(self):
        return nodename(self.relateddocument.target.document.name)

    def styles(self):

        # Note that the old style=dotted, color=red styling is never used

        if self.relateddocument.is_downref():
            return { 'color': 'red', 'arrowhead': 'normalnormal' }
        else:
            styles = { 'refnorm' : { 'color': 'blue'   },
                       'refinfo' : { 'color': 'green'  },
                       'refold'  : { 'color': 'orange' },
                       'refunk'  : { 'style': 'dashed' },
                       'replaces': { 'color': 'pink', 'style': 'dashed', 'arrowhead': 'diamond' },
                     }
            return styles[self.relateddocument.relationship.slug]


def nodename(name):
    return name.replace('-', '_')


def get_node_styles(node, group):

    styles = dict()

    # Shape and style (note that old diamond shape is never used

    styles['style'] = 'filled'

    if node.get_state('draft').slug == 'rfc':
        styles['shape'] = 'box'
    elif not node.get_state('draft-iesg').slug in ['idexists', 'watching', 'dead']:
        styles['shape'] = 'parallelogram'
    elif node.get_state('draft').slug == 'expired':
        styles['shape'] = 'house'
        styles['style'] = 'solid'
        styles['peripheries'] = 3
    elif node.get_state('draft').slug == 'repl':
        styles['shape'] = 'ellipse'
        styles['style'] = 'solid'
        styles['peripheries'] = 3
    else:
        pass                            # quieter form of styles['shape'] = 'ellipse'

    # Color (note that the old 'Flat out red' is never used
    if node.group.acronym == 'none':
        styles['color'] = '"#FF800D"'   # orangeish
    elif node.group == group:
        styles['color'] = '"#0AFE47"'   # greenish
    else:
        styles['color'] = '"#9999FF"'   # blueish

    # Label
    label = node.name
    if label.startswith('draft-'):
        if label.startswith('draft-ietf-'):
            label = label[11:]
        else:
            label = label[6:]
        try:
            t = label.index('-')
            label = r"%s\n%s" % (label[:t], label[t+1:])
        except:
            pass
    if node.group.acronym != 'none' and node.group != group:
        label = "(%s) %s" % (node.group.acronym, label)
    if node.get_state('draft').slug == 'rfc':
        label = "%s\\n(%s)" % (label, node.canonical_name())
    styles['label'] = '"%s"' % label

    return styles


def make_dot(group):
    references = Q(source__group=group, source__type='draft', relationship__slug__startswith='ref')
    both_rfcs  = Q(source__states__slug='rfc', target__docs__states__slug='rfc')
    inactive   = Q(source__states__slug__in=['expired', 'repl'])
    attractor  = Q(target__name__in=['rfc5000', 'rfc5741'])
    removed    = Q(source__states__slug__in=['auth-rm', 'ietf-rm'])
    relations  = ( RelatedDocument.objects.filter(references).exclude(both_rfcs)
                            .exclude(inactive).exclude(attractor).exclude(removed) )

    edges = set()
    for x in relations:
        target_state = x.target.document.get_state_slug('draft')
        if target_state != 'rfc' or x.is_downref():
            edges.add(Edge(x))

    replacements = RelatedDocument.objects.filter(relationship__slug='replaces',
                            target__docs__in=[x.relateddocument.target.document for x in edges])

    for x in replacements:
        edges.add(Edge(x))

    nodes = set([x.relateddocument.source for x in edges]).union([x.relateddocument.target.document for x in edges])

    for node in nodes:
        node.nodename = nodename(node.name)
        node.styles = get_node_styles(node, group)

    return render_to_string('group/dot.txt',
                             dict( nodes=nodes, edges=edges )
                            )


