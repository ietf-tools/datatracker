import sys
import sqlparse

from django import template

register = template.Library()

@register.filter(name='timesum')
def timesum(value):
    """
    Sum the times in a list of dicts; used for sql query debugging info"""
    sum = 0.0
    for v in value:
        sum += float(v['time'])
    return sum


@register.filter()
def expand_comma(value):
    """
    Adds a space after each comma, to allow word-wrapping of
    long comma-separated lists."""
    return value.replace(",", ", ")


def get_sql_parts(sql):
    q = {}
    s = sqlparse.parse(sql)[0]      # assuming there's only one statement
    q['where'] = None
    q['from'] = None
    # use sqlparse to pick out some interesting parts of the statement
    state = None
    for e in s:
        if e.is_whitespace:
            continue
        if state == None:
            if e.is_keyword:
                key = e.normalized.lower()
                state = 'value'
            elif e.is_group and e[0].is_keyword:
                key = e[0].normalized.lower()
                val = str(e)
                state = 'store'
            else:
                pass
        elif state == 'value':
            val = str(e)
            state = 'store'
        else:
            sys.stderr.write("Unexpected sqlparse iteration state in annotate_sql_queries(): '%s'" % state )
        if state == 'store':
            q[key] = val
            state = None
    return q

@register.filter()
def annotate_sql_queries(queries):
    counts  = {}
    timeacc = {}
    for q in queries:
        sql = q['sql']
        q.update(get_sql_parts(sql))
        if not sql in counts:
            counts[sql] = 0;
        counts[sql] += 1
        if not sql in timeacc:
            timeacc[sql] = 0.0;
        timeacc[sql] += float(q['time'])
    for q in queries:
        if q.get('loc', None) == None:
            q['loc'] = 'T'            # template
        sql = q['sql']
        q['count'] = str(counts[sql])
        q['time_accum'] = "%4.3f" % timeacc[sql]
    return queries
