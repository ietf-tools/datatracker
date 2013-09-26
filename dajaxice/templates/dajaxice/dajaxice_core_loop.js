{{ module.name }}: {
    {% for function in module.functions %}
            {% if function.doc and DAJAXICE_JS_DOCSTRINGS %}/* {{ function.doc|default:'' }}*/ {% endif %}
            {{ function.name }}: function(callback_function, argv, exception_callback){
                Dajaxice.call('{{function.get_callable_path}}', callback_function, argv, exception_callback);
            }{% if not forloop.last %},{% endif %}
    {% endfor %}
            
    {% for sub_module in module.sub_modules %}
    {% with "dajaxice/dajaxice_core_loop.js" as filename %}  
    {% with sub_module as module %}
        {% include filename %}
    {% endwith %}
    {% endwith %}
    {% endfor %}
        }{% if not forloop.last %},{% endif %}