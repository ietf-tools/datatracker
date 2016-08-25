# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


content ='''The Internet Engineering Task Force (IETF) provides a forum for working groups to coordinate technical development of new protocols. Its most important function is the development and selection of standards within the Internet protocol suite.

The IETF began in January 1986 as a forum for technical coordination by contractors for the then US Defense Advanced Research Projects Agency (DARPA), working on the ARPANET, US Defense Data Network (DDN), and the Internet core gateway system. Since that time, the IETF has grown into a large open international community of network designers, operators, vendors, and researchers concerned with the evolution of the Internet architecture and the smooth operation of the Internet.

The IETF mission includes:

* Identifying and proposing solutions to pressing operational and technical problems in the Internet
* Specifying the development or usage of protocols and the near-term architecture, to solve technical problems for the Internet
* Facilitating technology transfer from the Internet Research Task Force (IRTF) to the wider Internet community;and
* Providing a forum for the exchange of relevant information within the Internet community between vendors, users, researchers, agency contractors, and network managers.

Technical activities in the IETF are addressed within working groups. All working groups are organized roughly by function into seven areas. Each area is led by one or more Area Directors who have primary responsibility for that one area of IETF activity. Together with the Chair of the IETF/IESG, these Area Directors comprise the Internet Engineering Steering Group (IESG).

===================  ===================================  ========================
Name                 Area                                 Email
===================  ===================================  ========================
Jari Arkko           IETF Chair                           chair@ietf.org
Jari Arkko           General Area                         jari.arkko@piuha.net
Alia Atlas           Routing Area                         akatlas@gmail.com
Deborah Brungard     Routing Areas                        db3546@att.com
Ben Campbell         Applications and Real-Time Area      ben@nostrum.com
Benoit Claise        Operations and Management Area       bclaise@cisco.com
Alissa Cooper        Applications and Real-Time Area      alissa@cooperw.in
Spencer Dawkins      Transport Area                       spencerdawkins.ietf@gmail.com
Stephen Farrell      Security Area                        stephen.farrell@cs.tcd.ie
Joel Jaeggli         Operations and Management Area       joelja@bogus.com
Suresh Krishnan      Internet Area                        suresh.krishnan@ericsson.com
Mirja Kühlewind      Transport Area                       ietf@kuehlewind.net
Terry Manderson      Internet Area                        terry.manderson@icann.org
Alexey Melnikov      Applications and Real-Time Area      aamelnikov@fastmail.fm
Kathleen Moriarty    Security Area                        Kathleen.Moriarty.ietf@gmail.com
Alvaro Retana        Routing Area                         aretana@cisco.com
===================  ===================================  ========================


Liaison and ex-officio members include:

===================  ===================================  ========================
Olaf Kolkman         IAB Chair                            iab-chair@iab.org
Danny McPherson      IAB Liaison                          danny@tcb.net
Michelle Cotton      IANA Liaison                         iana@iana.org
Sandy Ginoza         RFC Editor Liaison                   rfc-editor@rfc-editor.org
Alexa Morris         IETF Secretariat Liaison             exec-director@ietf.org
===================  ===================================  ========================


The IETF has a Secretariat, which is managed by Association Management Solutions, LLC (AMS) in Fremont, California.The IETF Executive Director is Alexa Morris (exec-director@ietf.org).


Other personnel that provide full-time support to the Secretariat include:

=========================  ===================================
Senior Meeting Planner     Marcia Beaulieu
Project Manager            Stephanie McCammon
Meeting Regsitrar          Maddy Conner
Project Manager            Cindy Morgan
Project Manager            Amy Vezza
=========================  ===================================

To contact the Secretariat, please refer to the addresses and URLs provided on the IETF Secretariat Web page.

The IETF also has a general Administrative Support Activity headed by the IETF Administrative Director, Ray Pelletier iad@ietf.org

The working groups conduct their business during the tri-annual IETF meetings, at interim working group meetings, and via electronic mail on mailing lists established for each group. The tri-annual IETF meetings are 4.5 days in duration, and consist of working group sessions, training sessions, and plenary sessions. The plenary sessions include technical presentations, status reports, and an open IESG meeting.

Following each meeting, the IETF Secretariat publishes meeting proceedings, which contain reports from all of the groups that met, as well as presentation slides, where available. The proceedings also include a summary of the standards-related activities that took place since the previous IETF meeting.

Meeting minutes, working group charters (including information about the working group mailing lists), and general information on current IETF activities are available on the IETF Web site at https://www.ietf.org.
'''

def forward(apps, schema_editor):
    DBTemplate = apps.get_model("dbtemplate", "DBTemplate")
    Group = apps.get_model("group", "Group")
    Meeting = apps.get_model("meeting", "Meeting")
    group = Group.objects.get(acronym='ietf')
    template = DBTemplate.objects.create(
        content=content,
        group=group,
        path='/meeting/proceedings/defaults/overview.rst',
        title='Proceedings Overview Template',
        type_id='rst')

    # make copies for 95-97
    for n in (95,96,97):
        template.id = None
        template.path = '/meeting/proceedings/%s/overview.rst' % (n)
        template.title = 'IETF %s Proceedings Overview' % (n)
        template.save()
        meeting = Meeting.objects.get(number=n)
        meeting.overview = template
        meeting.save()

def reverse(apps, schema_editor):
    DBTemplate = apps.get_model("dbtemplate", "DBTemplate")
    Meeting = apps.get_model("meeting", "Meeting")
    DBTemplate.objects.get(path='/meeting/proceedings/defaults/overview.rst').delete()
    for n in (95,96,97):
        meeting = Meeting.objects.get(number=n)
        meeting.overview = None
        meeting.save()
    DBTemplate.objects.get(path='/meeting/proceedings/95/overview.rst').delete()
    DBTemplate.objects.get(path='/meeting/proceedings/96/overview.rst').delete()
    DBTemplate.objects.get(path='/meeting/proceedings/97/overview.rst').delete()
    
class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0034_auto_20160818_1555'),
    ]

    operations = [
        migrations.RunPython(forward,reverse),
    ]
