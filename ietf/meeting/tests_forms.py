# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

import json

from datetime import date, timedelta
from unittest.mock import patch

from django import forms

import debug  # pyflakes: ignore
from ietf.group.factories import GroupFactory

from ietf.meeting.factories import MeetingFactory, TimeSlotFactory, RoomFactory, SessionFactory
from ietf.meeting.forms import (CsvModelPkInput, CustomDurationField, SwapTimeslotsForm, duration_string,
                                TimeSlotDurationField, TimeSlotEditForm, TimeSlotCreateForm, DurationChoiceField,
                                SessionDetailsForm, sessiondetailsformset_factory, SessionEditForm)
from ietf.name.models import SessionPurposeName
from ietf.utils.test_utils import TestCase


class CsvModelPkInputTests(TestCase):
    widget = CsvModelPkInput()

    def test_render_none(self):
        result = self.widget.render('csv_model', value=None)
        self.assertHTMLEqual(result, '<input type="text" name="csv_model" value="">')

    def test_render_value(self):
        result = self.widget.render('csv_model', value=[1, 2, 3])
        self.assertHTMLEqual(result, '<input type="text" name="csv_model" value="1,2,3">')

    def test_value_from_datadict(self):
        result = self.widget.value_from_datadict({'csv_model': '11,23,47'}, {}, 'csv_model')
        self.assertEqual(result, ['11', '23', '47'])


class SwapTimeslotsFormTests(TestCase):
    def setUp(self):
        super().setUp()
        self.meeting = MeetingFactory(type_id='ietf', populate_schedule=False)
        self.timeslots = TimeSlotFactory.create_batch(2, meeting=self.meeting)
        self.other_meeting_timeslot = TimeSlotFactory()

    def test_valid(self):
        form = SwapTimeslotsForm(
            meeting=self.meeting,
            data={
                'origin_timeslot': str(self.timeslots[0].pk),
                'target_timeslot': str(self.timeslots[1].pk),
                'rooms': ','.join(str(rm.pk) for rm in self.meeting.room_set.all()),
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid(self):
        # the magic numbers are (very likely) non-existent pks
        form = SwapTimeslotsForm(
            meeting=self.meeting,
            data={
                'origin_timeslot': '25',
                'target_timeslot': str(self.timeslots[1].pk),
                'rooms': ','.join(str(rm.pk) for rm in self.meeting.room_set.all()),
            }
        )
        self.assertFalse(form.is_valid())
        form = SwapTimeslotsForm(
            meeting=self.meeting,
            data={
                'origin_timeslot': str(self.timeslots[0].pk),
                'target_timeslot': str(self.other_meeting_timeslot.pk),
                'rooms': ','.join(str(rm.pk) for rm in self.meeting.room_set.all()),
            }
        )
        self.assertFalse(form.is_valid())
        form = SwapTimeslotsForm(
            meeting=self.meeting,
            data={
                'origin_timeslot': str(self.timeslots[0].pk),
                'target_timeslot': str(self.timeslots[1].pk),
                'rooms': '1034',
            }
        )
        self.assertFalse(form.is_valid())


class CustomDurationFieldTests(TestCase):
    def test_duration_string(self):
        self.assertEqual(duration_string(timedelta(hours=3, minutes=17)), '03:17')
        self.assertEqual(duration_string(timedelta(hours=3, minutes=17, seconds=43)), '03:17')
        self.assertEqual(duration_string(timedelta(days=1, hours=3, minutes=17, seconds=43)), '1 03:17')
        self.assertEqual(duration_string(timedelta(hours=3, minutes=17, seconds=43, microseconds=37438)), '03:17')

    def _render_field(self, field):
        """Helper to render a form containing a field"""

        class Form(forms.Form):
            f = field

        return str(Form()['f'])

    @patch('ietf.meeting.forms.duration_string', return_value='12:34')
    def test_render(self, mock_duration_string):
        self.assertHTMLEqual(
            self._render_field(CustomDurationField()),
            '<input id="id_f" name="f" type="text" placeholder="HH:MM" required>'
        )
        self.assertHTMLEqual(
            self._render_field(CustomDurationField(initial=timedelta(hours=1))),
            '<input id="id_f" name="f" type="text" placeholder="HH:MM" required value="12:34">',
            'Rendered value should come from duration_string when initial value is a timedelta'
        )
        self.assertHTMLEqual(
            self._render_field(CustomDurationField(initial="01:02")),
            '<input id="id_f" name="f" type="text" placeholder="HH:MM" required value="01:02">',
            'Rendered value should come from initial when it is not a timedelta'
        )


class TimeSlotDurationFieldTests(TestCase):
    def test_validation(self):
        field = TimeSlotDurationField()
        with self.assertRaises(forms.ValidationError):
            field.clean('-01:00')
        with self.assertRaises(forms.ValidationError):
                field.clean('12:01')
        self.assertEqual(field.clean('00:00'), timedelta(seconds=0))
        self.assertEqual(field.clean('01:00'), timedelta(hours=1))
        self.assertEqual(field.clean('12:00'), timedelta(hours=12))


class TimeSlotEditFormTests(TestCase):
    def test_location_options(self):
        meeting = MeetingFactory(type_id='ietf', populate_schedule=False)
        rooms = [
            RoomFactory(meeting=meeting, capacity=3),
            RoomFactory(meeting=meeting, capacity=123),
        ]
        ts = TimeSlotFactory(meeting=meeting)
        rendered = str(TimeSlotEditForm(instance=ts)['location'])
        # noinspection PyTypeChecker
        self.assertInHTML(
            f'<option value="{ts.location.pk}" selected>{ts.location.name} size: None</option>',
            rendered,
        )
        for room in rooms:
            # noinspection PyTypeChecker
            self.assertInHTML(
                f'<option value="{room.pk}">{room.name} size: {room.capacity}</option>',
                rendered,
            )


class TimeSlotCreateFormTests(TestCase):
    def setUp(self):
        super().setUp()
        self.meeting = MeetingFactory(type_id='ietf', date=date(2021, 11, 16), days=3, populate_schedule=False)

    def test_other_date(self):
        room = RoomFactory(meeting=self.meeting)

        # no other_date, no day selected
        form = TimeSlotCreateForm(
            self.meeting,
            data={
                'name': 'time slot',
                'type': 'regular',
                'time': '12:00',
                'duration': '01:00',
                'locations': [str(room.pk)],
        })
        self.assertFalse(form.is_valid())

        # no other_date, day is selected
        form = TimeSlotCreateForm(
            self.meeting,
            data={
                'name': 'time slot',
                'type': 'regular',
                'days': ['738111'],  # date(2021,11,17).toordinal()
                'time': '12:00',
                'duration': '01:00',
                'locations': [str(room.pk)],
        })
        self.assertTrue(form.is_valid())
        self.assertNotIn('other_date', form.cleaned_data)
        self.assertEqual(form.cleaned_data['days'], [date(2021, 11, 17)])

        # other_date given, no day is selected
        form = TimeSlotCreateForm(
            self.meeting,
            data={
                'name': 'time slot',
                'type': 'regular',
                'time': '12:00',
                'duration': '01:00',
                'locations': [str(room.pk)],
                'other_date': '2021-11-15',
        })
        self.assertTrue(form.is_valid())
        self.assertNotIn('other_date', form.cleaned_data)
        self.assertEqual(form.cleaned_data['days'], [date(2021, 11, 15)])

        # day is selected and other_date is given
        form = TimeSlotCreateForm(
            self.meeting,
            data={
                'name': 'time slot',
                'type': 'regular',
                'days': ['738111'],  # date(2021,11,17).toordinal()
                'time': '12:00',
                'duration': '01:00',
                'locations': [str(room.pk)],
                'other_date': '2021-11-15',
        })
        self.assertTrue(form.is_valid())
        self.assertNotIn('other_date', form.cleaned_data)
        self.assertCountEqual(form.cleaned_data['days'], [date(2021, 11, 17), date(2021, 11, 15)])

        # invalid other_date, no day selected
        form = TimeSlotCreateForm(
            self.meeting,
            data={
                'name': 'time slot',
                'type': 'regular',
                'time': '12:00',
                'duration': '01:00',
                'locations': [str(room.pk)],
                'other_date': 'invalid',
        })
        self.assertFalse(form.is_valid())

        # invalid other_date, day selected
        form = TimeSlotCreateForm(
            self.meeting,
            data={
                'name': 'time slot',
                'type': 'regular',
                'days': ['738111'],  # date(2021,11,17).toordinal()
                'time': '12:00',
                'duration': '01:00',
                'locations': [str(room.pk)],
                'other_date': 'invalid',
        })
        self.assertFalse(form.is_valid())

    def test_meeting_days(self):
        form = TimeSlotCreateForm(self.meeting)
        self.assertEqual(
            form.fields['days'].choices,
            [
                ('738110', 'Tuesday (2021-11-16)'),
                ('738111', 'Wednesday (2021-11-17)'),
                ('738112', 'Thursday (2021-11-18)'),
            ],
        )

    def test_locations(self):
        rooms = RoomFactory.create_batch(5, meeting=self.meeting)
        form = TimeSlotCreateForm(self.meeting)
        self.assertCountEqual(form.fields['locations'].queryset.all(), rooms)


class DurationChoiceFieldTests(TestCase):
    def test_choices_default(self):
        f = DurationChoiceField()
        self.assertEqual(f.choices, [('', '--Please select'), ('3600', '1 hour'), ('7200', '2 hours')])

    def test_choices(self):
        f = DurationChoiceField([60, 1800, 3600, 5400, 7260, 7261])
        self.assertEqual(
            f.choices,
            [
                ('', '--Please select'),
                ('60', '1 minute'),
                ('1800', '30 minutes'),
                ('3600', '1 hour'),
                ('5400', '1 hour 30 minutes'),
                ('7260', '2 hours 1 minute'),
                ('7261', '2 hours 1 minute'),
            ]
        )

    def test_bound_value(self):
        class Form(forms.Form):
            f = DurationChoiceField()
        form = Form(data={'f': '3600'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['f'], timedelta(hours=1))
        form = Form(data={'f': '7200'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['f'], timedelta(hours=2))
        self.assertFalse(Form(data={'f': '3601'}).is_valid())
        self.assertFalse(Form(data={'f': ''}).is_valid())
        self.assertFalse(Form(data={'f': 'bob'}).is_valid())


class SessionDetailsFormTests(TestCase):
    def setUp(self):
        super().setUp()
        self.meeting = MeetingFactory(type_id='ietf', populate_schedule=False)
        self.group = GroupFactory()

    def test_initial_purpose(self):
        """First session purpose for group should be default"""
        # change the session_purposes GroupFeature to check that it's being used
        self.group.features.session_purposes = ['coding', 'admin', 'closed_meeting']
        self.group.features.save()
        self.assertEqual(SessionDetailsForm(group=self.group).initial['purpose'], 'coding')
        self.group.features.session_purposes = ['admin', 'coding', 'closed_meeting']
        self.group.features.save()
        self.assertEqual(SessionDetailsForm(group=self.group).initial['purpose'], 'admin')

    def test_session_purposes(self):
        # change the session_purposes GroupFeature to check that it's being used
        self.group.features.session_purposes = ['coding', 'admin', 'closed_meeting']
        self.group.features.save()
        self.assertCountEqual(
            SessionDetailsForm(group=self.group).fields['purpose'].queryset.values_list('slug', flat=True),
            ['coding', 'admin', 'closed_meeting'],
        )
        self.group.features.session_purposes = ['admin', 'closed_meeting']
        self.group.features.save()
        self.assertCountEqual(
            SessionDetailsForm(group=self.group).fields['purpose'].queryset.values_list('slug', flat=True),
            ['admin', 'closed_meeting'],
        )

    def test_allowed_types(self):
        """Correct map from SessionPurposeName to allowed TimeSlotTypeName should be sent to JS"""
        # change the allowed map to a known and non-standard arrangement
        SessionPurposeName.objects.filter(slug='regular').update(timeslot_types=['other'])
        SessionPurposeName.objects.filter(slug='admin').update(timeslot_types=['break', 'regular'])
        SessionPurposeName.objects.exclude(slug__in=['regular', 'admin']).update(timeslot_types=[])
        # check that the map we just installed is actually passed along to the JS through a widget attr
        allowed = json.loads(SessionDetailsForm(group=self.group).fields['type'].widget.attrs['data-allowed-options'])
        self.assertEqual(allowed['regular'], ['other'])
        self.assertEqual(allowed['admin'], ['break', 'regular'])
        for purpose in SessionPurposeName.objects.exclude(slug__in=['regular', 'admin']):
            self.assertEqual(allowed[purpose.slug], [])

    def test_duration_options(self):
        self.assertTrue(self.group.features.acts_like_wg)
        self.assertEqual(
            SessionDetailsForm(group=self.group).fields['requested_duration'].choices,
            [('', '--Please select'), ('3600', '1 hour'), ('7200', '2 hours')],
        )
        self.group.features.acts_like_wg = False
        self.group.features.save()
        self.assertEqual(
            SessionDetailsForm(group=self.group).fields['requested_duration'].choices,
            [('', '--Please select'), ('1800', '30 minutes'),
             ('3600', '1 hour'), ('5400', '1 hour 30 minutes'),
             ('7200', '2 hours'), ('9000', '2 hours 30 minutes'),
             ('10800', '3 hours'), ('12600', '3 hours 30 minutes'),
             ('14400', '4 hours')],
        )

    def test_on_agenda(self):
        # new session gets its purpose's on_agenda value when True
        self.assertTrue(SessionPurposeName.objects.get(slug='regular').on_agenda)
        form = SessionDetailsForm(group=self.group, data={
            'name': 'blah',
            'purpose': 'regular',
            'type': 'regular',
            'requested_duration': '3600',
        })
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['on_agenda'])

        # new session gets its purpose's on_agenda value when False
        SessionPurposeName.objects.filter(slug='regular').update(on_agenda=False)
        form = SessionDetailsForm(group=self.group, data={
            'name': 'blah',
            'purpose': 'regular',
            'type': 'regular',
            'requested_duration': '3600',
        })
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['on_agenda'])

        # updated session keeps its on_agenda value, even if it differs from its purpose
        session = SessionFactory(meeting=self.meeting, add_to_schedule=False, on_agenda=True)
        form = SessionDetailsForm(
            group=self.group,
            instance=session,
            data={
                'name': 'blah',
                'purpose': 'regular',
                'type': 'regular',
                'requested_duration': '3600',
            },
        )
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['on_agenda'])

        # session gets purpose's on_agenda value if its purpose changes (changing the
        # purpose away from 'regular' so we can use the 'wg' type group that only allows
        # regular sessions)
        session.purpose_id = 'admin'
        session.save()
        form = SessionDetailsForm(
            group=self.group,
            instance=session,
            data={
                'name': 'blah',
                'purpose': 'regular',
                'type': 'regular',
                'requested_duration': '3600',
            },
        )
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['on_agenda'])

class SessionEditFormTests(TestCase):
    def test_rejects_group_mismatch(self):
        session = SessionFactory(meeting__type_id='ietf', meeting__populate_schedule=False, add_to_schedule=False)
        other_group = GroupFactory()
        with self.assertRaisesMessage(ValueError, 'Session group does not match group keyword'):
            SessionEditForm(instance=session, group=other_group)


class SessionDetailsInlineFormset(TestCase):
    def setUp(self):
        super().setUp()
        self.meeting = MeetingFactory(type_id='ietf', populate_schedule=False)
        self.group = GroupFactory()

    def test_initial_sessions(self):
        """Sessions for the correct meeting and group should be included"""
        sessions = SessionFactory.create_batch(2, meeting=self.meeting, group=self.group, add_to_schedule=False)
        SessionFactory(meeting=self.meeting, add_to_schedule=False)  # should be ignored
        SessionFactory(group=self.group, add_to_schedule=False)  # should be ignored
        formset_class = sessiondetailsformset_factory()
        formset = formset_class(group=self.group, meeting=self.meeting)
        self.assertCountEqual(formset.queryset.all(), sessions)

    def test_forms_created_with_group_kwarg(self):
        class MockFormClass(SessionDetailsForm):
            """Mock class to track the group that was passed to the init method"""
            def __init__(self, group, *args, **kwargs):
                self.init_group_argument = group
                super().__init__(group, *args, **kwargs)

        with patch('ietf.meeting.forms.SessionDetailsForm', MockFormClass):
            formset_class = sessiondetailsformset_factory()
            formset = formset_class(meeting=self.meeting, group=self.group)
            str(formset)  # triggers instantiation of forms
            self.assertGreaterEqual(len(formset), 1)
            for form in formset:
                self.assertEqual(form.init_group_argument, self.group)

    def test_add_instance(self):
        session = SessionFactory(meeting=self.meeting, group=self.group, add_to_schedule=False)
        formset_class = sessiondetailsformset_factory()
        formset = formset_class(group=self.group, meeting=self.meeting, data={
            'session_set-TOTAL_FORMS': '2',
            'session_set-INITIAL_FORMS': '1',
            'session_set-0-id': str(session.pk),
            'session_set-0-name': 'existing',
            'session_set-0-purpose': 'regular',
            'session_set-0-type': 'regular',
            'session_set-0-requested_duration': '3600',
            'session_set-1-name': 'new',
            'session_set-1-purpose': 'regular',
            'session_set-1-type': 'regular',
            'session_set-1-requested_duration': '3600',
        })
        formset.save()
        # make sure session created
        self.assertEqual(self.meeting.session_set.count(), 2)
        self.assertIn(session, self.meeting.session_set.all())
        self.assertEqual(len(formset.new_objects), 1)
        self.assertEqual(formset.new_objects[0].name, 'new')
        self.assertEqual(formset.new_objects[0].meeting, self.meeting)
        self.assertEqual(formset.new_objects[0].group, self.group)
