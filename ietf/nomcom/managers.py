# Copyright The IETF Trust 2013-2019, All Rights Reserved
from django.db import models
from django.db.models.query import QuerySet

import debug  # pyflakes:ignore


class MixinManager(object):
    def __getattr__(self, attr):
        if attr.startswith("__"):
            return getattr(self.__class__, attr)
        else:
            try:
                return getattr(self.__class__, attr)
            except AttributeError:
                return getattr(self.get_queryset(), attr)


class NomineePositionQuerySet(QuerySet):

    def get_by_nomcom(self, nomcom):
        return self.filter(position__nomcom=nomcom)

    def by_state(self, state):
        return self.filter(state=state)

    def accepted(self):
        """only accepted objects"""
        return self.by_state("accepted")

    def pending(self):
        """only pending objects"""
        return self.by_state("pending")

    def declined(self):
        """only declined objects"""
        return self.by_state("declined")

    def not_duplicated(self):
        return self.filter(nominee__duplicated__isnull=True)

    def with_questionnaire_response(self):
        return self.filter(
            nominee__feedback__type="questio",
            nominee__feedback__positions=models.F("position"),
        ).distinct()

    def without_questionnaire_response(self):
        with_ids = self.with_questionnaire_response().values_list("id", flat=True)
        return self.exclude(id__in=with_ids)


class NomineePositionManager(models.Manager, MixinManager):
    def get_queryset(self):
        return NomineePositionQuerySet(self.model)


class NomineeManagerQuerySet(QuerySet):

    def get_by_nomcom(self, nomcom):
        return self.filter(nomcom=nomcom)

    def not_duplicated(self):
        return self.filter(duplicated__isnull=True)


class NomineeManager(models.Manager, MixinManager):
    def get_queryset(self):
        return NomineeManagerQuerySet(self.model)


class PositionQuerySet(QuerySet):

    def get_by_nomcom(self, nomcom):
        return self.filter(nomcom=nomcom)


class PositionManager(models.Manager, MixinManager):
    def get_queryset(self):
        return PositionQuerySet(self.model)


class FeedbackQuerySet(QuerySet):

    def get_by_nomcom(self, nomcom):
        return self.filter(nomcom=nomcom)

    def by_type(self, type):
        return self.filter(type=type)

    def comments(self):
        return self.by_type("comment")

    def questionnaires(self):
        return self.by_type("questio")

    def nominations(self):
        return self.by_type("nomina")


class FeedbackManager(models.Manager, MixinManager):
    def get_queryset(self):
        return FeedbackQuerySet(self.model)
