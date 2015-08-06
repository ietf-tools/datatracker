from django.core.urlresolvers import reverse as urlreverse

from ietf.utils.test_utils import TestCase
from ietf.utils.test_data import make_test_data
from ietf.eventmail.models import Ingredient

class EventMailTests(TestCase):

    def setUp(self):
        make_test_data()

    def test_show_patterns(self):

        url = urlreverse('ietf.eventmail.views.show_patterns')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('ballot_saved_cc' in r.content)
   
        url = urlreverse('ietf.eventmail.views.show_patterns',kwargs=dict(eventmail_slug='ballot_saved_cc'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('ballot_saved_cc' in r.content)

    def test_show_recipients(self):

        url = urlreverse('ietf.eventmail.views.show_ingredients')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('bogus' in r.content)
   
        url = urlreverse('ietf.eventmail.views.show_ingredients',kwargs=dict(ingredient_slug='bogus'))
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue('bogus' in r.content)

class IngredientTests(TestCase):

    def test_ingredient_functions(self):
        draft = make_test_data()
        ingredient = Ingredient.objects.first()
        for funcname in [name for name in dir(ingredient) if name.startswith('gather_')]:
            func=getattr(ingredient,funcname)
            func(**{'doc':draft,'group':draft.group})
