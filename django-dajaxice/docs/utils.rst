Utils
=====

dajaxice.utils.deserialize_form
-------------------------------

Using ``deserialize_form`` you will be able to deserialize a query_string and use it as input of a Form::

    from dajaxice.utils import deserialize_form

    @dajaxice_register
    def send_form(request, form):
        form = ExampleForm(deserialize_form(form))
        if form.is_valid():
            ...
        ...
