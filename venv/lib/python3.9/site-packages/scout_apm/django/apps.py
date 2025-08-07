# coding=utf-8

import sys

import django
from django.apps import AppConfig
from django.conf import settings
from django.core.signals import got_request_exception
from django.test.signals import setting_changed

if django.VERSION < (3, 1):
    from django.views.debug import get_safe_settings
else:
    from django.views.debug import SafeExceptionReporterFilter

    def get_safe_settings():
        return SafeExceptionReporterFilter().get_safe_settings()


import scout_apm.core
from scout_apm.core.config import scout_config
from scout_apm.core.error import ErrorMonitor
from scout_apm.django.instruments.huey import ensure_huey_instrumented
from scout_apm.django.instruments.sql import ensure_sql_instrumented
from scout_apm.django.instruments.template import ensure_templates_instrumented
from scout_apm.django.request import get_request_components


class ScoutApmDjangoConfig(AppConfig):
    name = "scout_apm"
    verbose_name = "Scout Apm (Django)"

    def ready(self):
        self.update_scout_config_from_django_settings()
        setting_changed.connect(self.on_setting_changed)

        # Finish installing the agent. If the agent isn't installed for any
        # reason, return without installing instruments
        installed = scout_apm.core.install()
        if not installed:
            return

        if scout_config.value("errors_enabled"):
            got_request_exception.connect(self.on_got_request_exception)

        self.install_middleware()

        # Setup Instruments
        ensure_huey_instrumented()
        ensure_sql_instrumented()
        ensure_templates_instrumented()

    def update_scout_config_from_django_settings(self, **kwargs):
        for name in dir(settings):
            self.on_setting_changed(name)

    def on_got_request_exception(self, request, **kwargs):
        """
        Process this exception with the error monitoring solution.
        """
        ErrorMonitor.send(
            sys.exc_info(),
            request_components=get_request_components(request),
            request_path=request.path,
            request_params=dict(request.GET.lists()),
            session=dict(request.session.items())
            if hasattr(request, "session")
            else None,
            environment=get_safe_settings(),
        )

    def on_setting_changed(self, setting, **kwargs):
        cast = None
        if setting == "BASE_DIR":
            scout_name = "application_root"
            cast = str
        elif setting.startswith("SCOUT_"):
            scout_name = setting.replace("SCOUT_", "").lower()
        else:
            return

        try:
            value = getattr(settings, setting)
        except AttributeError:
            # It was removed
            scout_config.unset(scout_name)
        else:
            if cast is not None:
                value = cast(value)
            scout_config.set(**{scout_name: value})

    def install_middleware(self):
        """
        Attempts to insert the ScoutApm middleware as the first middleware
        (first on incoming requests, last on outgoing responses).
        """
        from django.conf import settings

        # If MIDDLEWARE is set, update that, with handling of tuple vs array forms
        if getattr(settings, "MIDDLEWARE", None) is not None:
            timing_middleware = "scout_apm.django.middleware.MiddlewareTimingMiddleware"
            view_middleware = "scout_apm.django.middleware.ViewTimingMiddleware"

            if isinstance(settings.MIDDLEWARE, tuple):
                if timing_middleware not in settings.MIDDLEWARE:
                    settings.MIDDLEWARE = (timing_middleware,) + settings.MIDDLEWARE
                if view_middleware not in settings.MIDDLEWARE:
                    settings.MIDDLEWARE = settings.MIDDLEWARE + (view_middleware,)
            else:
                if timing_middleware not in settings.MIDDLEWARE:
                    settings.MIDDLEWARE.insert(0, timing_middleware)
                if view_middleware not in settings.MIDDLEWARE:
                    settings.MIDDLEWARE.append(view_middleware)

        # Otherwise, we're doing old style middleware, do the same thing with
        # the same handling of tuple vs array forms
        else:
            timing_middleware = (
                "scout_apm.django.middleware.OldStyleMiddlewareTimingMiddleware"
            )
            view_middleware = "scout_apm.django.middleware.OldStyleViewMiddleware"

            if isinstance(settings.MIDDLEWARE_CLASSES, tuple):
                if timing_middleware not in settings.MIDDLEWARE_CLASSES:
                    settings.MIDDLEWARE_CLASSES = (
                        timing_middleware,
                    ) + settings.MIDDLEWARE_CLASSES

                if view_middleware not in settings.MIDDLEWARE_CLASSES:
                    settings.MIDDLEWARE_CLASSES = settings.MIDDLEWARE_CLASSES + (
                        view_middleware,
                    )
            else:
                if timing_middleware not in settings.MIDDLEWARE_CLASSES:
                    settings.MIDDLEWARE_CLASSES.insert(0, timing_middleware)
                if view_middleware not in settings.MIDDLEWARE_CLASSES:
                    settings.MIDDLEWARE_CLASSES.append(view_middleware)
