# coding=utf-8

from scout_apm.core.web_requests import RequestComponents


def get_controller_name(request):
    view_func = request.resolver_match.func
    view_name = request.resolver_match._func_path
    if hasattr(view_func, "view_class"):
        view_func = view_func.view_class
        view_name = "{}.{}".format(view_func.__module__, view_func.__name__)

    django_admin_components = _get_django_admin_components(view_func)
    if django_admin_components:
        view_name = "{}.{}.{}".format(
            django_admin_components.module,
            django_admin_components.controller,
            django_admin_components.action,
        )

    django_rest_framework_components = _get_django_rest_framework_components(
        request, view_func
    )
    if django_rest_framework_components is not None:
        view_name = "{}.{}.{}".format(
            django_rest_framework_components.module,
            django_rest_framework_components.controller,
            django_rest_framework_components.action,
        )

    # Seems to be a Tastypie Resource. Need to resort to some stack inspection
    # to find a better name since its decorators don't wrap very well
    if view_name == "tastypie.resources.wrapper":
        tastypie_components = _get_tastypie_components(request, view_func)
        if tastypie_components is not None:
            view_name = "{}.{}.{}".format(
                tastypie_components.module,
                tastypie_components.controller,
                tastypie_components.action,
            )

    return "Controller/{}".format(view_name)


def get_request_components(request):
    if not request.resolver_match:
        return None
    view_func = request.resolver_match.func
    view_name = request.resolver_match._func_path
    if hasattr(view_func, "view_class"):
        view_func = view_func.view_class
    request_components = RequestComponents(
        module=view_func.__module__,
        controller=view_func.__name__,
        action=request.method,
    )

    django_admin_components = _get_django_admin_components(view_func)
    if django_admin_components:
        request_components = django_admin_components

    django_rest_framework_components = _get_django_rest_framework_components(
        request, view_func
    )
    if django_rest_framework_components is not None:
        request_components = django_rest_framework_components

    # Seems to be a Tastypie Resource. Need to resort to some stack inspection
    # to find a better name since its decorators don't wrap very well
    if view_name == "tastypie.resources.wrapper":
        tastypie_components = _get_tastypie_components(request, view_func)
        if tastypie_components is not None:
            request_components = tastypie_components
    return request_components


def _get_django_admin_components(view_func):
    if hasattr(view_func, "model_admin"):
        # Seems to comes from Django admin (attribute only set on Django 1.9+)
        admin_class = view_func.model_admin.__class__
        return RequestComponents(
            module=admin_class.__module__,
            controller=admin_class.__name__,
            action=view_func.__name__,
        )
    return None


def _get_django_rest_framework_components(request, view_func):
    try:
        from rest_framework.viewsets import ViewSetMixin
    except ImportError:
        return None

    kls = getattr(view_func, "cls", None)
    if isinstance(kls, type) and not issubclass(kls, ViewSetMixin):
        return None

    # Get 'actions' set in ViewSetMixin.as_view
    actions = getattr(view_func, "actions", None)
    if not actions or not isinstance(actions, dict):
        return None

    method_lower = request.method.lower()
    if method_lower not in actions:
        return None

    return RequestComponents(
        module=view_func.__module__,
        controller=view_func.__name__,
        action=actions[method_lower],
    )


def _get_tastypie_components(request, view_func):
    try:
        from tastypie.resources import Resource
    except ImportError:
        return None

    try:
        wrapper = view_func.__wrapped__
    except AttributeError:
        return None

    if not hasattr(wrapper, "__closure__") or len(wrapper.__closure__) != 2:
        return None

    instance = wrapper.__closure__[0].cell_contents
    if not isinstance(instance, Resource):  # pragma: no cover
        return None

    method_name = wrapper.__closure__[1].cell_contents
    if not isinstance(method_name, str):  # pragma: no cover
        return None

    if method_name.startswith("dispatch_"):  # pragma: no cover
        method_name = request.method.lower() + method_name.split("dispatch", 1)[1]

    return RequestComponents(
        module=instance.__module__,
        controller=instance.__class__.__name__,
        action=method_name,
    )
