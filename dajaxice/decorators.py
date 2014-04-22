import functools

from dajaxice.core import dajaxice_functions


def dajaxice_register(*dargs, **dkwargs):
    """ Register some function as a dajaxice function

    For legacy purposes, if only a function is passed register it a simple
    single ajax function using POST, i.e:

    @dajaxice_register
    def ajax_function(request):
        ...

    After 0.5, dajaxice allow to customize the http method and the final name
    of the registered function. This decorator covers both the legacy and
    the new functionality, i.e:

    @dajaxice_register(method='GET')
    def ajax_function(request):
        ...

    @dajaxice_register(method='GET', name='my.custom.name')
    def ajax_function(request):
        ...

    You can also register the same function to use a different http method
    and/or use a different name.

    @dajaxice_register(method='GET', name='users.get')
    @dajaxice_register(method='POST', name='users.update')
    def ajax_function(request):
        ...
    """

    if len(dargs) and not dkwargs:
        function = dargs[0]
        dajaxice_functions.register(function)
        return function

    def decorator(function):
        @functools.wraps(function)
        def wrapper(request, *args, **kwargs):
            return function(request, *args, **kwargs)
        dajaxice_functions.register(function, *dargs, **dkwargs)
        return wrapper
    return decorator
