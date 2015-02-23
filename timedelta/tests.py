from unittest import TestCase
import datetime
import doctest

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import six

from .fields import TimedeltaField
import timedelta.helpers
import timedelta.forms
import timedelta.widgets

class MinMaxTestModel(models.Model):
    min = TimedeltaField(min_value=datetime.timedelta(1))
    max = TimedeltaField(max_value=datetime.timedelta(1))
    minmax = TimedeltaField(min_value=datetime.timedelta(1), max_value=datetime.timedelta(7))

class IntTestModel(models.Model):
    field = TimedeltaField(min_value=1, max_value=86400)

class FloatTestModel(models.Model):
    field = TimedeltaField(min_value=1.0, max_value=86400.0)

class TimedeltaModelFieldTest(TestCase):
    def test_validate(self):
        test = MinMaxTestModel(
            min=datetime.timedelta(1),
            max=datetime.timedelta(1),
            minmax=datetime.timedelta(1)
        )
        test.full_clean() # This should have met validation requirements.
        
        test.min = datetime.timedelta(hours=23)
        self.assertRaises(ValidationError, test.full_clean)
        
        test.min = datetime.timedelta(hours=25)
        test.full_clean()
        
        test.max = datetime.timedelta(11)
        self.assertRaises(ValidationError, test.full_clean)
        
        test.max = datetime.timedelta(hours=20)
        test.full_clean()
        
        test.minmax = datetime.timedelta(0)
        self.assertRaises(ValidationError, test.full_clean)
        test.minmax = datetime.timedelta(22)
        self.assertRaises(ValidationError, test.full_clean)
        test.minmax = datetime.timedelta(6, hours=23, minutes=59, seconds=59)
        test.full_clean()
    
    def test_from_int(self):
        """
        Check that integers can be used to define the min_value and max_value
        arguments, and that when assigned an integer, TimedeltaField converts
        to timedelta.
        """

        test = IntTestModel()

        # valid
        test.field = 3600
        self.assertEquals(test.field, datetime.timedelta(seconds=3600))
        test.full_clean()
        
        # invalid
        test.field = 0
        self.assertRaises(ValidationError, test.full_clean)

        # also invalid
        test.field = 86401
        self.assertRaises(ValidationError, test.full_clean)

    def test_from_float(self):
        """
        Check that floats can be used to define the min_value and max_value
        arguments, and that when assigned a float, TimedeltaField converts
        to timedelta.
        """

        test = FloatTestModel()

        # valid
        test.field = 3600.0
        self.assertEquals(test.field, datetime.timedelta(seconds=3600))
        test.full_clean()
        
        # invalid
        test.field = 0.0
        self.assertRaises(ValidationError, test.full_clean)

        # also invalid
        test.field = 86401.0
        self.assertRaises(ValidationError, test.full_clean)
        
    def test_deconstruct(self):
        """
        Check that the deconstruct() method of TimedeltaField is returning the
        min_value, max_value and default kwargs as floats.
        """

        field = TimedeltaField(
            min_value=datetime.timedelta(minutes=5),
            max_value=datetime.timedelta(minutes=15),
            default=datetime.timedelta(minutes=30),
        )

        kwargs = field.deconstruct()[3]
        self.assertEqual(kwargs['default'], 1800.0)
        self.assertEqual(kwargs['max_value'], 900.0)
        self.assertEqual(kwargs['min_value'], 300.0)

    def test_load_from_db(self):
        obj = MinMaxTestModel.objects.create(min='2 days', max='2 minutes', minmax='3 days')
        self.assertEquals(datetime.timedelta(2), obj.min)
        self.assertEquals(datetime.timedelta(0, 120), obj.max)
        self.assertEquals(datetime.timedelta(3), obj.minmax)
        
        obj = MinMaxTestModel.objects.get()
        self.assertEquals(datetime.timedelta(2), obj.min)
        self.assertEquals(datetime.timedelta(0, 120), obj.max)
        self.assertEquals(datetime.timedelta(3), obj.minmax)

def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(timedelta.helpers))
    tests.addTests(doctest.DocTestSuite(timedelta.forms))
    return tests
