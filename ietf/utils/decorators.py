# Copyright The IETF Trust 2016, All Rights Reserved

from decorator import decorator

from django.conf import settings

from test_runner import set_coverage_checking

@decorator
def skip_coverage(f, *args, **kwargs):
    if settings.TEST_CODE_COVERAGE_CHECKER:
        set_coverage_checking(False)
        result = f(*args, **kwargs)
        set_coverage_checking(True)
        return result
    else:
        return  f(*args, **kwargs)

@decorator
def person_required(f, request, *args, **kwargs):
    from ietf.person.models import Person
    from django.shortcuts import render
    if not request.user.is_authenticated:
        raise ValueError("The @person_required decorator should be called after @login_required.")
    try:
        request.user.person
    except Person.DoesNotExist:
        return render(request, 'registration/missing_person.html')
    return  f(request, *args, **kwargs)
    
@decorator
def verify_user_api_key(f, request, *args, **kwargs):
    from ietf.person.models import Person, PersonalApiKey
    from django.shortcuts import render
    if not request.user.is_authenticated:
        raise ValueError("The @verify_user_api_key decorator should be called after @login_required.")
    try:
        person = request.user.person
    except Person.DoesNotExist:
        return render(request, 'registration/missing_person.html')
    if request.method == 'POST':
        hash = request.POST['apikey']
    elif request.method == 'GET':
        hash = request.GET['apikey']
    else:
        return render(request, 'base.html', {
            'content': """
                <h1>Missing API key</h1>
                
                <p>
                  There is no apikey provided with this call.
                  Please create a valid Personal API key and use that with your request.
                  </p>
                """,
        })
    key = PersonalApiKey.validate_key(hash)
    if key and key.person == person:
        return f(request, key, *args, **kwargs)
    else:
        return render(request, 'base.html', {
            'content': """
                <h1>Bad API key</h1>
                
                <p>
                  The API key provided with this cal is invalid.
                  Please create a valid Personal API key and use that with your request.
                  </p>
                """,
        })
