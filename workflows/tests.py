# django imports
from django.contrib.contenttypes.models import ContentType
from django.contrib.flatpages.models import FlatPage
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.sessions.backends.file import SessionStore
from django.core.handlers.wsgi import WSGIRequest
from django.test.client import Client

# workflows import
import permissions.utils
import workflows.utils
from workflows.models import State
from workflows.models import StateInheritanceBlock
from workflows.models import StatePermissionRelation
from workflows.models import StateObjectRelation
from workflows.models import Transition
from workflows.models import Workflow
from workflows.models import WorkflowModelRelation
from workflows.models import WorkflowObjectRelation
from workflows.models import WorkflowPermissionRelation

class WorkflowTestCase(TestCase):
    """Tests a simple workflow without permissions.
    """
    def setUp(self):
        """
        """
        create_workflow(self)

    def test_get_states(self):
        """
        """
        states = self.w.states.all()
        self.assertEqual(states[0], self.private)
        self.assertEqual(states[1], self.public)

    def test_unicode(self):
        """
        """
        self.assertEqual(self.w.__unicode__(), u"Standard")

class PermissionsTestCase(TestCase):
    """Tests a simple workflow with permissions.
    """
    def setUp(self):
        """
        """
        create_workflow(self)

        # Register roles
        self.anonymous = permissions.utils.register_role("Anonymous")
        self.owner = permissions.utils.register_role("Owner")

        self.user = User.objects.create(username="john")
        permissions.utils.add_role(self.user, self.owner)

        # Example content type
        self.page_1 = FlatPage.objects.create(url="/page-1/", title="Page 1")

        # Registers permissions
        self.view = permissions.utils.register_permission("View", "view")
        self.edit = permissions.utils.register_permission("Edit", "edit")

        # Add all permissions which are managed by the workflow
        wpr = WorkflowPermissionRelation.objects.create(workflow=self.w, permission=self.view)
        wpr = WorkflowPermissionRelation.objects.create(workflow=self.w, permission=self.edit)

        # Add permissions for single states
        spr = StatePermissionRelation.objects.create(state=self.public, permission=self.view, role=self.owner)
        spr = StatePermissionRelation.objects.create(state=self.private, permission=self.view, role=self.owner)
        spr = StatePermissionRelation.objects.create(state=self.private, permission=self.edit, role=self.owner)

        # Add inheritance block for single states
        sib = StateInheritanceBlock.objects.create(state=self.private, permission=self.view)
        sib = StateInheritanceBlock.objects.create(state=self.private, permission=self.edit)
        sib = StateInheritanceBlock.objects.create(state=self.public, permission=self.edit)

        workflows.utils.set_workflow(self.page_1, self.w)

    def test_set_state(self):
        """
        """
        # Permissions
        result = permissions.utils.has_permission(self.page_1, self.user, "edit")
        self.assertEqual(result, True)

        result = permissions.utils.has_permission(self.page_1, self.user, "view")
        self.assertEqual(result, True)

        # Inheritance
        result = permissions.utils.is_inherited(self.page_1, "view")
        self.assertEqual(result, False)

        result = permissions.utils.is_inherited(self.page_1, "edit")
        self.assertEqual(result, False)

        # Change state
        workflows.utils.set_state(self.page_1, self.public)

        # Permissions
        result = permissions.utils.has_permission(self.page_1, self.user, "edit")
        self.assertEqual(result, False)

        result = permissions.utils.has_permission(self.page_1, self.user, "view")
        self.assertEqual(result, True)

        # Inheritance
        result = permissions.utils.is_inherited(self.page_1, "view")
        self.assertEqual(result, True)

        result = permissions.utils.is_inherited(self.page_1, "edit")
        self.assertEqual(result, False)

    def test_set_initial_state(self):
        """
        """
        state = workflows.utils.get_state(self.page_1)
        self.assertEqual(state.name, self.private.name)

        workflows.utils.do_transition(self.page_1, self.make_public, self.user)
        state = workflows.utils.get_state(self.page_1)
        self.assertEqual(state.name, self.public.name)

        workflows.utils.set_initial_state(self.page_1)
        state = workflows.utils.get_state(self.page_1)
        self.assertEqual(state.name, self.private.name)

    def test_do_transition(self):
        """
        """
        state = workflows.utils.get_state(self.page_1)
        self.assertEqual(state.name, self.private.name)

        # by transition
        workflows.utils.do_transition(self.page_1, self.make_public, self.user)

        state = workflows.utils.get_state(self.page_1)
        self.assertEqual(state.name, self.public.name)

        # by name
        workflows.utils.do_transition(self.page_1, "Make private", self.user)

        state = workflows.utils.get_state(self.page_1)
        self.assertEqual(state.name, self.private.name)

        # name which does not exist
        result = workflows.utils.do_transition(self.page_1, "Make pending", self.user)
        self.assertEqual(result, False)

        wrong = Transition.objects.create(name="Wrong", workflow=self.w, destination = self.public)

        # name which does not exist
        result = workflows.utils.do_transition(self.page_1, wrong, self.user)
        self.assertEqual(result, False)

class UtilsTestCase(TestCase):
    """Tests various methods of the utils module.
    """
    def setUp(self):
        """
        """
        create_workflow(self)
        self.user = User.objects.create()

    def test_workflow(self):
        """
        """
        workflows.utils.set_workflow(self.user, self.w)
        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, self.w)

    def test_state(self):
        """
        """
        result = workflows.utils.get_state(self.user)
        self.assertEqual(result, None)

        workflows.utils.set_workflow(self.user, self.w)
        result = workflows.utils.get_state(self.user)
        self.assertEqual(result, self.w.initial_state)

    def test_set_workflow_1(self):
        """Set worklow by object
        """
        ctype = ContentType.objects.get_for_model(self.user)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, None)

        wp = Workflow.objects.create(name="Portal")

        # Set for model
        workflows.utils.set_workflow_for_model(ctype, wp)

        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, wp)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, wp)

        # Set for object
        workflows.utils.set_workflow_for_object(self.user, self.w)
        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, self.w)

        # The model still have wp
        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, wp)

    def test_set_workflow_2(self):
        """Set worklow by name
        """
        ctype = ContentType.objects.get_for_model(self.user)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, None)

        wp = Workflow.objects.create(name="Portal")

        # Set for model
        workflows.utils.set_workflow_for_model(ctype, "Portal")

        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, wp)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, wp)

        # Set for object
        workflows.utils.set_workflow_for_object(self.user, "Standard")
        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, self.w)

        # The model still have wp
        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, wp)

        # Workflow which does not exist
        result = workflows.utils.set_workflow_for_model(ctype, "Wrong")
        self.assertEqual(result, False)

        result = workflows.utils.set_workflow_for_object(self.user, "Wrong")
        self.assertEqual(result, False)

    def test_get_objects_for_workflow_1(self):
        """Workflow is added to object.
        """
        result = workflows.utils.get_objects_for_workflow(self.w)
        self.assertEqual(result, [])

        workflows.utils.set_workflow(self.user, self.w)
        result = workflows.utils.get_objects_for_workflow(self.w)
        self.assertEqual(result, [self.user])

    def test_get_objects_for_workflow_2(self):
        """Workflow is added to content type.
        """
        result = workflows.utils.get_objects_for_workflow(self.w)
        self.assertEqual(result, [])

        ctype = ContentType.objects.get_for_model(self.user)
        workflows.utils.set_workflow(ctype, self.w)
        result = workflows.utils.get_objects_for_workflow(self.w)
        self.assertEqual(result, [self.user])

    def test_get_objects_for_workflow_3(self):
        """Workflow is added to content type and object.
        """
        result = workflows.utils.get_objects_for_workflow(self.w)
        self.assertEqual(result, [])

        workflows.utils.set_workflow(self.user, self.w)
        result = workflows.utils.get_objects_for_workflow(self.w)
        self.assertEqual(result, [self.user])

        ctype = ContentType.objects.get_for_model(self.user)
        workflows.utils.set_workflow(ctype, self.w)
        result = workflows.utils.get_objects_for_workflow(self.w)
        self.assertEqual(result, [self.user])

    def test_get_objects_for_workflow_4(self):
        """Get workflow by name
        """
        result = workflows.utils.get_objects_for_workflow("Standard")
        self.assertEqual(result, [])

        workflows.utils.set_workflow(self.user, self.w)
        result = workflows.utils.get_objects_for_workflow("Standard")
        self.assertEqual(result, [self.user])

        # Workflow which does not exist
        result = workflows.utils.get_objects_for_workflow("Wrong")
        self.assertEqual(result, [])

    def test_remove_workflow_from_model(self):
        """
        """
        ctype = ContentType.objects.get_for_model(self.user)

        result = workflows.utils.get_workflow(ctype)
        self.assertEqual(result, None)

        workflows.utils.set_workflow_for_model(ctype, self.w)

        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, self.w)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, self.w)

        workflows.utils.remove_workflow_from_model(ctype)

        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, None)

        result = workflows.utils.get_workflow_for_object(self.user)
        self.assertEqual(result, None)

    def test_remove_workflow_from_object(self):
        """
        """
        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, None)

        workflows.utils.set_workflow_for_object(self.user, self.w)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, self.w)

        result = workflows.utils.remove_workflow_from_object(self.user)
        self.assertEqual(result, None)

    def test_remove_workflow_1(self):
        """Removes workflow from model
        """
        ctype = ContentType.objects.get_for_model(self.user)

        result = workflows.utils.get_workflow(ctype)
        self.assertEqual(result, None)

        workflows.utils.set_workflow_for_model(ctype, self.w)

        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, self.w)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, self.w)

        workflows.utils.remove_workflow(ctype)

        result = workflows.utils.get_workflow_for_model(ctype)
        self.assertEqual(result, None)

        result = workflows.utils.get_workflow_for_object(self.user)
        self.assertEqual(result, None)

    def test_remove_workflow_2(self):
        """Removes workflow from object
        """
        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, None)

        workflows.utils.set_workflow_for_object(self.user, self.w)

        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, self.w)

        result = workflows.utils.remove_workflow(self.user)
        self.assertEqual(result, None)

    def test_get_allowed_transitions(self):
        """Tests get_allowed_transitions method
        """
        page_1 = FlatPage.objects.create(url="/page-1/", title="Page 1")
        role_1 = permissions.utils.register_role("Role 1")
        permissions.utils.add_role(self.user, role_1)

        view = permissions.utils.register_permission("Publish", "publish")

        transitions = self.private.get_allowed_transitions(page_1, self.user)
        self.assertEqual(len(transitions), 1)

        # protect the transition with a permission
        self.make_public.permission = view        
        self.make_public.save()

        # user has no transition
        transitions = self.private.get_allowed_transitions(page_1, self.user)
        self.assertEqual(len(transitions), 0)

        # grant permission
        permissions.utils.grant_permission(page_1, role_1, view)

        # user has transition again
        transitions = self.private.get_allowed_transitions(page_1, self.user)
        self.assertEqual(len(transitions), 1)

    def test_get_workflow_for_object(self):
        """
        """
        result = workflows.utils.get_workflow(self.user)
        self.assertEqual(result, None)
        
        # Set workflow for a user
        workflows.utils.set_workflow_for_object(self.user, self.w)
        
        # Get workflow for the user        
        result = workflows.utils.get_workflow_for_object(self.user)
        self.assertEqual(result, self.w)

        # Set workflow for a FlatPage
        page_1 = FlatPage.objects.create(url="/page-1/", title="Page 1")
        workflows.utils.set_workflow_for_object(page_1, self.w)

        result = workflows.utils.get_workflow_for_object(self.user)
        self.assertEqual(result, self.w)

        result = workflows.utils.get_workflow_for_object(page_1)
        self.assertEqual(result, self.w)

class StateTestCase(TestCase):
    """Tests the State model
    """
    def setUp(self):
        """
        """
        create_workflow(self)
        self.user = User.objects.create()
        self.role_1 = permissions.utils.register_role("Role 1")
        permissions.utils.add_role(self.user, self.role_1)
        self.page_1 = FlatPage.objects.create(url="/page-1/", title="Page 1")

    def test_unicode(self):
        """
        """
        self.assertEqual(self.private.__unicode__(), u"Private (Standard)")

    def test_transitions(self):
        """
        """
        transitions = self.public.transitions.all()
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0], self.make_private)

        transitions = self.private.transitions.all()
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0], self.make_public)

    def test_get_transitions(self):
        """
        """
        transitions = self.private.get_allowed_transitions(self.page_1, self.user)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0], self.make_public)

        transitions = self.public.get_allowed_transitions(self.page_1, self.user)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0], self.make_private)

    def test_get_allowed_transitions(self):
        """
        """
        self.view = permissions.utils.register_permission("Publish", "publish")
        transitions = self.private.get_allowed_transitions(self.page_1, self.user)
        self.assertEqual(len(transitions), 1)

        # protect the transition with a permission
        self.make_public.permission = self.view
        self.make_public.save()

        # user has no transition
        transitions = self.private.get_allowed_transitions(self.page_1, self.user)
        self.assertEqual(len(transitions), 0)

        # grant permission
        permissions.utils.grant_permission(self.page_1, self.role_1, self.view)

        # user has transition again
        transitions = self.private.get_allowed_transitions(self.page_1, self.user)
        self.assertEqual(len(transitions), 1)

class TransitionTestCase(TestCase):
    """Tests the Transition model
    """
    def setUp(self):
        """
        """
        create_workflow(self)

    def test_unicode(self):
        """
        """
        self.assertEqual(self.make_private.__unicode__(), u"Make private")

class RelationsTestCase(TestCase):
    """Tests various Relations models.
    """
    def setUp(self):
        """
        """
        create_workflow(self)
        self.page_1 = FlatPage.objects.create(url="/page-1/", title="Page 1")

    def test_unicode(self):
        """
        """
        # WorkflowObjectRelation
        workflows.utils.set_workflow(self.page_1, self.w)
        wor = WorkflowObjectRelation.objects.filter()[0]
        self.assertEqual(wor.__unicode__(), "flat page 1 - Standard")

        # StateObjectRelation
        workflows.utils.set_state(self.page_1, self.public)
        sor = StateObjectRelation.objects.filter()[0]
        self.assertEqual(sor.__unicode__(), "flat page 1 - Public")

        # WorkflowModelRelation
        ctype = ContentType.objects.get_for_model(self.page_1)
        workflows.utils.set_workflow(ctype, self.w)
        wmr = WorkflowModelRelation.objects.filter()[0]
        self.assertEqual(wmr.__unicode__(), "flat page - Standard")

        # WorkflowPermissionRelation
        self.view = permissions.utils.register_permission("View", "view")
        wpr = WorkflowPermissionRelation.objects.create(workflow=self.w, permission=self.view)
        self.assertEqual(wpr.__unicode__(), "Standard View")

        # StatePermissionRelation
        self.owner = permissions.utils.register_role("Owner")
        spr = StatePermissionRelation.objects.create(state=self.public, permission=self.view, role=self.owner)
        self.assertEqual(spr.__unicode__(), "Public Owner View")

# Helpers ####################################################################

def create_workflow(self):
    self.w = Workflow.objects.create(name="Standard")

    self.private = State.objects.create(name="Private", workflow= self.w)
    self.public = State.objects.create(name="Public", workflow= self.w)

    self.make_public = Transition.objects.create(name="Make public", workflow=self.w, destination = self.public)
    self.make_private = Transition.objects.create(name="Make private", workflow=self.w, destination = self.private)

    self.private.transitions.add(self.make_public)
    self.public.transitions.add(self.make_private)

    self.w.initial_state = self.private
    self.w.save()

# Taken from "http://www.djangosnippets.org/snippets/963/"
class RequestFactory(Client):
    """
    Class that lets you create mock Request objects for use in testing.

    Usage:

    rf = RequestFactory()
    get_request = rf.get('/hello/')
    post_request = rf.post('/submit/', {'foo': 'bar'})

    This class re-uses the django.test.client.Client interface, docs here:
    http://www.djangoproject.com/documentation/testing/#the-test-client

    Once you have a request object you can pass it to any view function,
    just as if that view had been hooked up using a URLconf.

    """
    def request(self, **request):
        """
        Similar to parent class, but returns the request object as soon as it
        has created it.
        """
        environ = {
            'HTTP_COOKIE': self.cookies,
            'PATH_INFO': '/',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': 80,
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }
        environ.update(self.defaults)
        environ.update(request)
        return WSGIRequest(environ)

def create_request():
    """
    """
    rf = RequestFactory()
    request = rf.get('/')
    request.session = SessionStore()

    user = User()
    user.is_superuser = True
    user.save()
    request.user = user

    return request
