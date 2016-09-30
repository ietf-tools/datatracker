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


@register.filter()
def annotate_sql_queries(queries):
    counts  = {}
    timeacc = {}
    for q in queries:
        sql = q['sql']
        if not sql in counts:
            counts[sql] = 0;
        counts[sql] += 1
        if not sql in timeacc:
            timeacc[sql] = 0.0;
        timeacc[sql] += float(q['time'])
    for q in queries:
        sql = q['sql']
        q['count'] = str(counts[sql])
        q['time_accum'] = "%4.3f" % timeacc[sql]
    return queries
