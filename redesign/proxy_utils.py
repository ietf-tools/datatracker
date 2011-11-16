from django.db.models.manager import Manager
from django.db.models.query import QuerySet

def proxy_personify_role(role):
    """Turn role into person with email() method using email from role."""
    p = role.person
    p.email = lambda: (p.name, role.email.address)
    return p

def proxy_role_email(e):
    """Add email() method to person on email."""
    e.person.email = lambda: (e.person.name, e.address)
    return e

def chunks(l, n):
    """Split list l up in chunks of max size n."""
    return (l[i:i+n] for i in range(0, len(l), n))

class TranslatingQuerySet(QuerySet):
    def translated_args(self, args):
        trans = self.translated_attrs
        res = []
        for a in args:
            if a.startswith("-"):
                prefix = "-"
                a = a[1:]
            else:
                prefix = ""
                
            if a in trans:
                t = trans[a]
                if callable(t):
                    t, _ = t(None)

                if t:
                    res.append(prefix + t)
            else:
                res.append(prefix + a)
        return res

    def translated_kwargs(self, kwargs):
        trans = self.translated_attrs
        res = dict()
        for k, v in kwargs.iteritems():
            if k in trans:
                t = trans[k]
                if callable(t):
                    ts = t(v)
                else:
                    ts = (t, v)

                for t, v in chunks(ts, 2):
                    if t:
                        res[t] = v
            else:
                res[k] = v
        return res

    # overridden methods
    def _clone(self, *args, **kwargs):
        c = super(TranslatingQuerySet, self)._clone(*args, **kwargs)
        c.translated_attrs = self.translated_attrs
        return c

    def dates(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).dates(*args, **kwargs)

    def distinct(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).distinct(*args, **kwargs)

    def extra(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).extra(*args, **kwargs)

    def get(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).get(*args, **kwargs)

    def get_or_create(self, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).get_or_create(**kwargs)

    def create(self, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).create(**kwargs)

    def filter(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).filter(*args, **kwargs)

    def aggregate(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).aggregate(*args, **kwargs)

    def annotate(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).annotate(*args, **kwargs)

    def complex_filter(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).complex_filter(*args, **kwargs)

    def exclude(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).exclude(*args, **kwargs)

    def in_bulk(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).in_bulk(*args, **kwargs)

    def iterator(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).iterator(*args, **kwargs)

    def latest(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).latest(*args, **kwargs)

    def order_by(self, *args, **kwargs):
        args = self.translated_args(args)
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).order_by(*args, **kwargs)

    def select_related(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).select_related(*args, **kwargs)

    def values(self, *args, **kwargs):
        args = self.translated_args(args)
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).values(*args, **kwargs)

    def values_list(self, *args, **kwargs):
        args = self.translated_args(args)
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).values_list(*args, **kwargs)

    def update(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).update(*args, **kwargs)

    def reverse(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).reverse(*args, **kwargs)

    def defer(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).defer(*args, **kwargs)

    def only(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self).only(*args, **kwargs)

    def _insert(self, values, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return insert_query(self.model, values, **kwargs)

    def _update(self, values, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(TranslatingQuerySet, self)._update(values, **kwargs)

class TranslatingManager(Manager):
    """Translates keyword arguments for the ORM, for use in proxy
    wrapping, e.g. given trans={'foo': 'bar'} it will transform a
    lookup of the field foo to a lookup on the field bar. The right
    hand side can either be a string or a function which is called
    with the right-hand side to transform it."""
    
    def __init__(self, trans, always_filter=None):
        super(TranslatingManager, self).__init__()
        self.translated_attrs = trans
        self.always_filter = always_filter

    def get_query_set(self):
        qs = TranslatingQuerySet(self.model)
        qs.translated_attrs = self.translated_attrs
        if self.always_filter:
            qs = qs.filter(**self.always_filter)
        return qs
    
    # def dates(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().dates(*args, **kwargs)

    # def distinct(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().distinct(*args, **kwargs)

    # def extra(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().extra(*args, **kwargs)

    # def get(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().get(*args, **kwargs)

    # def get_or_create(self, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().get_or_create(**kwargs)

    # def create(self, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().create(**kwargs)

    # def filter(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().filter(*args, **kwargs)

    # def aggregate(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().aggregate(*args, **kwargs)

    # def annotate(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().annotate(*args, **kwargs)

    # def complex_filter(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().complex_filter(*args, **kwargs)

    # def exclude(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().exclude(*args, **kwargs)

    # def in_bulk(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().in_bulk(*args, **kwargs)

    # def iterator(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().iterator(*args, **kwargs)

    # def latest(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().latest(*args, **kwargs)

    # def order_by(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().order_by(*args, **kwargs)

    # def select_related(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().select_related(*args, **kwargs)

    # def values(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().values(*args, **kwargs)

    # def values_list(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().values_list(*args, **kwargs)

    # def update(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().update(*args, **kwargs)

    # def reverse(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().reverse(*args, **kwargs)

    # def defer(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().defer(*args, **kwargs)

    # def only(self, *args, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set().only(*args, **kwargs)

    # def _insert(self, values, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return insert_query(self.model, values, **kwargs)

    # def _update(self, values, **kwargs):
    #     kwargs = self.translated_kwargs(kwargs)
    #     return self.get_query_set()._update(values, **kwargs)
