from django.db.models.manager import Manager
from django.db.models.query import QuerySet

class TranslatingQuerySet(QuerySet):
    def translated_kwargs(self, kwargs):
        trans = self.translated_attrs
        res = dict()
        for k, v in kwargs.iteritems():
            if k in trans:
                t = trans[k]
                if callable(t):
                    t, v = t(v)

                res[t] = v
            else:
                res[k] = v
        return res

    # overridden methods
    def _clone(self, *args, **kwargs):
        c = super(self.__class__, self)._clone(*args, **kwargs)
        c.translated_attrs = self.translated_attrs
        return c

    def dates(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).dates(*args, **kwargs)

    def distinct(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).distinct(*args, **kwargs)

    def extra(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).extra(*args, **kwargs)

    def get(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).get(*args, **kwargs)

    def get_or_create(self, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).get_or_create(**kwargs)

    def create(self, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).create(**kwargs)

    def filter(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).filter(*args, **kwargs)

    def aggregate(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).aggregate(*args, **kwargs)

    def annotate(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).annotate(*args, **kwargs)

    def complex_filter(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).complex_filter(*args, **kwargs)

    def exclude(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).exclude(*args, **kwargs)

    def in_bulk(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).in_bulk(*args, **kwargs)

    def iterator(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).iterator(*args, **kwargs)

    def latest(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).latest(*args, **kwargs)

    def order_by(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).order_by(*args, **kwargs)

    def select_related(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).select_related(*args, **kwargs)

    def values(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).values(*args, **kwargs)

    def values_list(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).values_list(*args, **kwargs)

    def update(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).update(*args, **kwargs)

    def reverse(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).reverse(*args, **kwargs)

    def defer(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).defer(*args, **kwargs)

    def only(self, *args, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self).only(*args, **kwargs)

    def _insert(self, values, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return insert_query(self.model, values, **kwargs)

    def _update(self, values, **kwargs):
        kwargs = self.translated_kwargs(kwargs)
        return super(self.__class__, self)._update(values, **kwargs)

class TranslatingManager(Manager):
    """Translates keyword arguments for the ORM, for use in proxy
    wrapping, e.g. given trans={'foo': 'bar'} it will transform a
    lookup of the field foo to a lookup on the field bar. The right
    hand side can either be a string or a function which is called
    with the right-hand side to transform it."""
    
    def __init__(self, trans):
        super(self.__class__, self).__init__()
        self.translated_attrs = trans

    def get_query_set(self):
        qs = TranslatingQuerySet(self.model)
        qs.translated_attrs = self.translated_attrs
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
