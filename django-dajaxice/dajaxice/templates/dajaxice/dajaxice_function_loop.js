{% for function_name, function in module.functions.items %}
    {{ function_name }}: function(callback_function, argv, custom_settings){
        return Dajaxice.call('{{ function.name }}', '{{ function.method }}', callback_function, argv, custom_settings);
    }{% if not forloop.last or top or module.submodules %},{% endif %}
{% endfor %}
