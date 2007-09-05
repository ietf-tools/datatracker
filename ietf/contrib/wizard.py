# Copyright The IETF Trust 2007, All Rights Reserved

##
## django form wizard
## http://code.djangoproject.com/ticket/3218
"""
TODO:
    !!!! documentation !!!! including examples

USAGE:
    urls: (replace wizard.Wizard with something that overrides its done() method,
            othervise it will complain at the end that __call__ does not return HttpResponse)

        ( r'^$', MyWizard( [MyForm, MyForm, MyForm] ) ),

    template:
        <form action="." method="POST">
        FORM( {{ step }} ): {{ form }}
        
        step_info : <input type="hidden" name="{{ step_field }}" value="{{ step }}" />

        previous_fields: {{ previous_fields }}

        <input type="submit">
        </form>
        
"""
from django.conf import settings
from django.http import Http404
from django.shortcuts import render_to_response
from django.template.context import RequestContext

from django import newforms as forms
#import cPickle as pickle
import md5

class Wizard( object ):
    PREFIX="%d"
    STEP_FIELD="wizard_step"

    # METHODS SUBCLASSES SHOULDN'T OVERRIDE ###################################
    def __init__( self, form_list, initial=None ):
        " Pass list of Form classes (not instances !) "
        self.form_list = form_list[:]
        self.initial = initial or {}

    def __repr__( self ):
        return "step: %d\nform_list: %s\ninitial_data: %s" % ( self.step, self.form_list, self.initial )
    
    def get_form( self, step, data=None ):
        " Shortcut to return form instance. "
        return self.form_list[step]( data, prefix=self.PREFIX % step, initial=self.initial.get( step, None ) )

    def __call__( self, request, *args, **kwargs ):
        """
        Main function that does all the hard work:
            - initializes the wizard object (via parse_params())
            - veryfies (using security_hash()) that noone has tempered with the data since we last saw them
                calls failed_hash() if it is so
                calls process_step() for every previously submitted form
            - validates current form and
                returns it again if errors were found
                returns done() if it was the last form
                returns next form otherwise
        """
        # add extra_context, we don't care if somebody overrides it, as long as it remains a dict 
        self.extra_context = kwargs.get( 'extra_context', {} )

        self.parse_params( request, *args, **kwargs )

        # we only accept POST method for form delivery  no POST, no data
        if not request.POST:
            self.step = 0
            return self.render( self.get_form( 0 ), request )

        # verify old steps' hashes
        for i in range( self.step ):
            form = self.get_form( i, request.POST )
            # somebody is trying to corrupt our data
            if request.POST.get( "hash_%d" % i, '' ) != self.security_hash( request, form ):
                # revert to the corrupted step
                return self.failed_hash( request, i )
            self.process_step( request, form, i )

        # process current step
        form = self.get_form( self.step, request.POST )
        if form.is_valid():
            self.process_step( request, form, self.step )
            self.step += 1
            # this was the last step
            if self.step == len( self.form_list ):
                return self.done(  request, [ self.get_form( i, request.POST ) for i in range( len( self.form_list ) ) ] )
            form = self.get_form( self.step )
        return self.render( form, request )
                
    def render( self, form, request ):
        """
        Prepare the form and call the render_template() method to do tha actual rendering.
        """
        if self.step >= len( self.form_list ):
            raise Http404

        old_data = request.POST
        prev_fields = ''
        if old_data:
            # old data
            prev_fields = '\n'.join( 
                    bf.as_hidden() for i in range(self.step) for bf in self.get_form( i, old_data )
                )
            # hashes for old forms
            hidden = forms.widgets.HiddenInput()
            prev_fields += '\n'.join( 
                    hidden.render( "hash_%d" % i, old_data.get( "hash_%d" % i, self.security_hash( request, self.get_form( i, old_data ) ) ) ) 
                        for i in range( self.step) 
                )
        return self.render_template( request, form, prev_fields )

        
    # METHODS SUBCLASSES MIGHT OVERRIDE IF APPROPRIATE ########################

    def failed_hash( self, request, i ):
        """
        One of the hashes verifying old data doesn't match.
        """
        self.step = i
        return self.render( self.get_form(self.step), request )

    def security_hash(self, request, form):
        """
        Calculates the security hash for the given Form instance.

        This creates a list of the form field names/values in a deterministic
        order, pickles the result with the SECRET_KEY setting and takes an md5
        hash of that.

        Subclasses may want to take into account request-specific information
        such as the IP address.
        """
	data = []
	for bf in form:
	    if bf.data is None:
		d = ''
	    else:
		# Hidden inputs strip trailing carraige returns
		# so we exclude those from the hash.
	    	d = bf.data.rstrip("\r\n")
	    data.append((bf.name, d))
	data.append(settings.SECRET_KEY)
        # Use HIGHEST_PROTOCOL because it's the most efficient. It requires
        # Python 2.3, but Django requires 2.3 anyway, so that's OK.
        #pickled = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        pickled = str(data)     #XXX
        return md5.new(pickled).hexdigest()

    def parse_params( self, request, *args, **kwargs ):
        """
        Set self.step, process any additional info from parameters and/or form data
        """
        if request.POST:
            self.step = int( request.POST.get( self.STEP_FIELD, 0 ) )
        else:
            self.step = 0

    def get_template( self ):
        """
        Return name of the template to be rendered, use self.step to get the step number.
        """
        return "wizard.html"

    def render_template( self, request, form, previous_fields ):
        """
        Render template for current step, override this method if you wish to add custom context, return a different mimetype etc.

        If you only wish to override the template name, use get_template

        Some additional items are added to the context: 
            'step_field' is the name of the hidden field containing step
            'step' holds the current step
            'form' containing the current form to be processed (either empty or with errors)
            'previous_data' contains all the addtitional information, including
                hashes for finished forms and old data in form of hidden fields
            any additional data stored in self.extra_context
        """
        return render_to_response( self.get_template(), dict( 
                    step_field=self.STEP_FIELD,
                    step=self.step,
                    form=form,
                    previous_fields=previous_fields,
                    ** self.extra_context
                ), context_instance=RequestContext( request ) )

    def process_step( self, request, form, step ):
        """
        This should not modify any data, it is only a hook to modify wizard's internal state
        (such as dynamically generating form_list based on previously submited forms).
        It can also be used to add items to self.extra_context base on the contents of previously submitted forms.

        Note that this method is called every time a page is rendered for ALL submitted steps.

        Only valid data enter here.
        """
        pass

    # METHODS SUBCLASSES MUST OVERRIDE ########################################

    def done( self, request, form_list ):
        """
        this method must be overriden, it is responsible for the end processing - it will be called with instances of all form_list with their data
        """
        raise NotImplementedError('You must define a done() method on your %s subclass.' % self.__class__.__name__)

