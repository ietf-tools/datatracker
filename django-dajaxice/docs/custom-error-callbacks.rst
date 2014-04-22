Custom error callbacks
======================


How dajaxice handle errors
--------------------------

When one of your functions raises an exception dajaxice returns as response the ``DAJAXICE_EXCEPTION`` message.
On every response ``dajaxice.core.js`` checks if that response was an error or not and shows the user a default
error message ``Something goes wrong``.


Customize the default error message
-----------------------------------
This behaviour is configurable using the new ``Dajaxice.setup`` function.

.. code-block:: javascript

    Dajaxice.setup({'default_exception_callback': function(){ alert('Error!'); }});

Customize error message per call
--------------------------------
In this new version you can also specify an error callback per dajaxice call.

.. code-block:: javascript

    function custom_error(){
        alert('Custom error of my_function.');
    }

    Dajaxice.simple.my_function(callback, {'user': 'tom'}, {'error_callback': custom_error});
