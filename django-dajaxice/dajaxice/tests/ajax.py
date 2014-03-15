from django.utils import simplejson
from dajaxice.decorators import dajaxice_register


@dajaxice_register
def test_registered_function(request):
    return ""


@dajaxice_register
def test_string(request):
    return simplejson.dumps({'string': 'hello world'})


@dajaxice_register
def test_ajax_exception(request):
    raise Exception()


@dajaxice_register
def test_foo(request):
    return simplejson.dumps({'foo': 'bar'})


@dajaxice_register
def test_foo_with_params(request, param1):
    return simplejson.dumps({'param1': param1})


@dajaxice_register(method='GET')
def test_get_register(request):
    return simplejson.dumps({'foo': 'user'})


@dajaxice_register(method='GET', name="get_user_data")
def test_get_with_name_register(request):
    return simplejson.dumps({'bar': 'user'})


@dajaxice_register(method='GET', name="get_multi")
@dajaxice_register(name="post_multi")
def test_multi_register(request):
    return simplejson.dumps({'foo': 'multi'})
