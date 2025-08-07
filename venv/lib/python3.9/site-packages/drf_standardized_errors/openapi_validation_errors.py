import copy
import inspect
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union

from drf_spectacular.drainage import error, warn
from drf_spectacular.openapi import AutoSchema
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSetMixin

from .types import SetValidationErrorsKwargs

V = TypeVar("V", bound=Union[Type[APIView], Callable[..., Any]])


def extend_validation_errors(
    error_codes: List[str],
    field_name: Optional[str] = None,
    actions: Optional[List[str]] = None,
    methods: Optional[List[str]] = None,
    versions: Optional[List[str]] = None,
) -> Callable[[V], V]:
    """
    A view/viewset decorator for adding extra error codes to validation errors.
    This decorator does not override error codes already collected by
    drf-standardized-errors.

    :param error_codes: list of error codes to add.
    :param field_name: name of serializer or form field to which the error codes
        will be added. It can be set to ``"non_field_errors"`` when the error codes
        correspond to validation inside ``Serializer.validate`` or ``"__all__"`` when
        they correspond to validation inside ``Form.clean``. It can also be left
        as ``None`` when the validation is not linked to any serializer or form
        (for example, raising ``serializers.ValidationError`` inside the view
        or viewset directly).
    :param actions: can be set when decorating a viewset. Limits the added error
        codes to the specified actions. Defaults to adding the error codes to all
        actions.
    :param methods: Limits the added error codes to the specified methods (get,
        post, ...). Defaults to adding the error codes regardless of the method.
    :param versions: Limits the added error codes to the specified versions.
        Defaults to adding the error codes regardless of the version.
    """
    if methods:
        methods = [method.lower() for method in methods]

    def wrapper(view):  # type: ignore
        # special case for @api_view. Decorate the WrappedAPIView class
        if callable(view) and hasattr(view, "cls"):
            extend_validation_errors(
                error_codes, field_name, actions, methods, versions
            )(view.cls)
            return view

        if not inspect.isclass(view) or (
            inspect.isclass(view) and not issubclass(view, APIView)
        ):
            error(
                "`@extend_validation_errors` can only be applied to APIViews or "
                "ViewSets or function-based views already decorated with @api_view. "
                f"{view.__name__} is none of these."
            )
            return view

        if not error_codes:
            error(
                "No error codes are passed to the `@extend_validation_errors` "
                f"decorator that is applied to {view.__name__}."
            )
            return view

        kwargs: SetValidationErrorsKwargs = {
            "error_codes": error_codes,
            "field_name": field_name,
            "actions": actions,
            "methods": methods,
            "versions": versions,
        }
        if actions and issubclass(view, ViewSetMixin):
            # validate the actions provided are indeed defined on the viewset class
            possible_actions = get_action_names(view)
            unknown_actions = set(actions).difference(possible_actions)
            if unknown_actions:
                is_or_are = "is" if len(unknown_actions) == 1 else "are"
                warn(
                    f"'{', '.join(unknown_actions)}' {is_or_are} not in the list of "
                    f"actions defined on the viewset {view.__name__}. The actions "
                    "specified will be ignored."
                )
                kwargs["actions"] = None
        elif actions:
            warn(
                "The 'actions' argument of 'extend_validation_errors' should only be "
                f"set when decorating viewsets. '{view.__name__}' is not a viewset. "
                "The actions specified will be ignored."
            )
            kwargs["actions"] = None

        if methods:
            # validate that the methods are in the list of allowed methods
            allowed_methods = get_allowed_http_methods(view)
            unknown_methods = set(methods).difference(allowed_methods)
            if unknown_methods:
                is_or_are = "is" if len(unknown_methods) == 1 else "are"
                warn(
                    f"'{', '.join(unknown_methods)}' {is_or_are} not in the list of "
                    f"allowed http methods of {view.__name__}. The methods specified "
                    "will be ignored."
                )
                kwargs["methods"] = None

        # now that all checks are done, let's set the extra validation error
        # on the view to later add them to the schema
        set_validation_errors(view, **kwargs)

        return view

    return wrapper


def get_action_names(viewset: Type[ViewSetMixin]) -> List[str]:
    # based on drf_spectacular.drainage.get_view_method_names
    builtin_action_names = ["list"] + list(viewset.schema.method_mapping.values())
    return [
        item
        for item in dir(viewset)
        if callable(getattr(viewset, item))
        and (item in builtin_action_names or is_custom_action(viewset, item))
    ]


def is_custom_action(viewset: Type[ViewSetMixin], method_name: str) -> bool:
    # i.e. defined using the @action decorator
    return hasattr(getattr(viewset, method_name), "mapping")


def get_allowed_http_methods(view: Type[APIView]) -> List[str]:
    if issubclass(view, ViewSetMixin):
        return view.http_method_names
    else:
        # based on drf_spectacular.drainage.get_view_method_names
        return [
            item
            for item in dir(view)
            if callable(getattr(view, item)) and item in view.http_method_names
        ]


def set_validation_errors(
    view: Type[APIView],
    error_codes: List[str],
    field_name: Optional[str],
    actions: Optional[List[str]],
    methods: Optional[List[str]],
    versions: Optional[List[str]],
) -> None:
    if hasattr(view, "_standardized_errors"):
        if "_standardized_errors" not in vars(view):
            # that means it is defined on a parent class, so we first create
            # a copy of it to avoid the validation error showing for the parent
            # class as well
            view._standardized_errors = copy.deepcopy(view._standardized_errors)
    else:
        view._standardized_errors = defaultdict(list)

    errors = generate_standardized_errors(
        error_codes, field_name, actions, methods, versions
    )

    # errors are stored in a list to preserve order. When determining the error
    # codes for each field for a specific operation, we will traverse this list
    # in reverse order and pick the first encountered error that is in scope
    # of the operation in question. The reason we do this in reverse order is
    # to account the ability to override error codes in a child view.
    view._standardized_errors[field_name].extend(errors)


def generate_standardized_errors(
    error_codes: List[str],
    field_name: Optional[str],
    actions: Optional[List[str]],
    methods: Optional[List[str]],
    versions: Optional[List[str]],
) -> "List[StandardizedError]":
    actions = actions or [None]  # type: ignore
    methods = methods or [None]  # type: ignore
    versions = versions or [None]  # type: ignore

    return [
        StandardizedError(set(error_codes), field_name, action, method, version)
        for action in actions
        for method in methods
        for version in versions
    ]


def get_validation_errors(view: APIView) -> "Dict[str, List[StandardizedError]]":
    return getattr(view, "_standardized_errors", {})


@dataclass
class StandardizedError:
    error_codes: Set[str]
    field_name: Optional[str] = None
    action: Optional[str] = None
    method: Optional[str] = None
    version: Optional[str] = None

    def is_in_scope(self, schema: AutoSchema) -> bool:
        """Determine if the error is in scope of the current operation"""
        view = schema.view
        api_version, _ = view.determine_version(view.request, **view.kwargs)
        version_in_scope = self.version is None or self.version == api_version
        method_in_scope = self.method is None or self.method == schema.method.lower()

        if isinstance(view, ViewSetMixin):
            action_in_scope = self.action is None or self.action == view.action
            return action_in_scope and method_in_scope and version_in_scope
        else:
            return method_in_scope and version_in_scope
