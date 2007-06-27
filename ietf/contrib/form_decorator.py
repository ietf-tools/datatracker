# Copyright The IETF Trust 2007, All Rights Reserved

## formfield_callback generator
## http://www.djangosnippets.org/snippets/59/
def form_decorator(fields = {}, attrs = {}, widgets = {}, 
    labels = {}, choices = {}, querysets = {}):
    
    """
    This function helps to add overrides when creating forms from models/instances.
    Pass in dictionary of fields to override certain fields altogether, otherwise
    add widgets or labels as desired.
    
    For example:
    
    class Project(models.Model):
    
        name = models.CharField(maxlength = 100)
        description = models.TextField()
        owner = models.ForeignKey(User)
   
    project_fields = dict(
        owner = None
    )
    
    project_widgets = dict(
        name = forms.TextInput({"size":40}),
        description = forms.Textarea({"rows":5, "cols":40}))
    
    project_labels = dict(
        name = "Enter your project name here"
    )
    
    callback = form_decorator(project_fields, project_widgets, project_labels)
    project_form = forms.form_for_model(Project, formfield_callback = callback)
    
    This saves having to redefine whole fields for example just to change a widget
    setting or label.
    """
    
    def formfields_callback(f, **kw):
    
        if f.name in fields:
            
            # replace field altogether
            field = fields[f.name]
            f.initial = kw.pop("initial", None)
            return field
        
        if f.name in widgets:
            
            kw["widget"] = widgets[f.name]

        if f.name in attrs:
            
            widget = kw.pop("widget", f.formfield().widget)
            if widget :
                widget.attrs.update(attrs[f.name])
                kw["widget"] = widget

        if f.name in labels:
        
            kw["label"] = labels[f.name]
        
        if f.name in choices:
        
            choice_set = choices[f.name]
            if callable(choice_set) : choice_set = choice_set()
            kw["choices"] = choice_set

        if f.name in querysets:
        
            kw["queryset"] = querysets[f.name]
            
                
        return f.formfield(**kw)
    
    return formfields_callback

