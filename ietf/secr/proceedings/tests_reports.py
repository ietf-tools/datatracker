import datetime
import debug    # pyflakes:ignore

from ietf.doc.factories import DocumentFactory,NewRevisionDocEventFactory
from ietf.secr.proceedings.reports import report_id_activity, report_progress_report
from ietf.utils.test_utils import TestCase
from ietf.meeting.factories import MeetingFactory

class ReportsTestCase(TestCase):

    def test_report_id_activity(self):

        today = datetime.datetime.today()
        yesterday = today - datetime.timedelta(days=1)
        last_quarter = today - datetime.timedelta(days=3*30)
        next_week = today+datetime.timedelta(days=7)

        m1 = MeetingFactory(type_id='ietf',date=last_quarter)
        m2 = MeetingFactory(type_id='ietf',date=next_week,number=int(m1.number)+1)

        doc = DocumentFactory(type_id='draft',time=yesterday,rev="00")
        NewRevisionDocEventFactory(doc=doc,time=today,rev="01")
        result = report_id_activity(m1.date.strftime("%Y-%m-%d"),m2.date.strftime("%Y-%m-%d"))
        self.assertTrue('IETF Activity since last IETF Meeting' in result)

    def test_report_progress_report(self):
        today = datetime.datetime.today()
        last_quarter = today - datetime.timedelta(days=3*30)
        next_week = today+datetime.timedelta(days=7)

        m1 = MeetingFactory(type_id='ietf',date=last_quarter)
        m2 = MeetingFactory(type_id='ietf',date=next_week,number=int(m1.number)+1)
        result = report_progress_report(m1.date.strftime('%Y-%m-%d'),m2.date.strftime('%Y-%m-%d'))
        self.assertTrue('IETF Activity since last IETF Meeting' in result)
