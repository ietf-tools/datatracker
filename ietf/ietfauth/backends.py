# Copyright The IETF Trust 2023-2026, All Rights Reserved
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest


# From https://simpleisbetterthancomplex.com/tutorial/2017/02/06/how-to-implement-case-insensitive-username.html
class CaseInsensitiveModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        try:
            case_insensitive_username_field = '{}__iexact'.format(UserModel.USERNAME_FIELD)
            user = UserModel._default_manager.get(**{case_insensitive_username_field: username})
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (#20760).
            UserModel().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user


class UnsafeAllowAnyModelBackend(ModelBackend):
    """UNSAFE backend that allows login with the password "password"

    Will not work except in dev mode.
    """

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> AbstractBaseUser | None:
        if settings.SERVER_MODE not in ("development", "test"):
            raise ImproperlyConfigured(f"Cannot use {self.__class__.__name__} backend when SERVER_MODE={settings.SERVER_MODE}")
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None:
            return None
        try:
            case_insensitive_username_field = '{}__iexact'.format(UserModel.USERNAME_FIELD)
            user = UserModel._default_manager.get(**{case_insensitive_username_field: username})
        except UserModel.DoesNotExist:
            return None
        if self.user_can_authenticate(user):
            # DOES NOT CHECK PASSWORD (this is intentional, but not ok for production)
            return user
        return None
