from django.db import models
from django.db.models.query import QuerySet


class MixinManager(object):
    def __getattr__(self, attr, *args):
        try:
            return getattr(self.__class__, attr, *args)
        except AttributeError:
            return getattr(self.get_query_set(), attr, *args)


class NomineePositionQuerySet(QuerySet):

    def get_by_nomcom(self, nomcom):
        return self.filter(position__nomcom=nomcom)

    def by_state(self, state):
        return self.filter(state=state)

    def accepted(self):
        """ only accepted objects """
        return self.by_state('accepted')

    def pending(self):
        """ only pending objects """
        return self.by_state('pending')

    def declined(self):
        """ only draft objects """
        return self.by_state('declined')


class NomineePositionManager(models.Manager, MixinManager):
    def get_query_set(self):
        return NomineePositionQuerySet(self.model)


class NomineeManager(models.Manager):
    def get_by_nomcom(self, nomcom):
        return self.filter(nominee_position__nomcom=nomcom)


class PositionQuerySet(QuerySet):

    def get_by_nomcom(self, nomcom):
        return self.filter(nomcom=nomcom)

    def opened(self):
        """ only opened positions """
        return self.filter(is_open=True)

    def closed(self):
        """ only closed positions """
        return self.filter(is_open=False)


class PositionManager(models.Manager, MixinManager):
    def get_query_set(self):
        return PositionQuerySet(self.model)


class FeedbackQuerySet(QuerySet):

    def get_by_nomcom(self, nomcom):
        return self.filter(nomcom=nomcom)

    def by_type(self, type):
        return self.filter(type=type)

    def comments(self):
        return self.by_type('comment')

    def questionnaires(self):
        return self.by_type('questio')

    def nominations(self):
        return self.by_type('nomina')


class FeedbackManager(models.Manager, MixinManager):
    def get_query_set(self):
        return FeedbackQuerySet(self.model)
