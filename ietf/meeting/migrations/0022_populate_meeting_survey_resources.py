# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations

# Survey results links as published on https://www.ietf.org/meeting/past/ (October 2026)
SURVEY_RESULTS = [
    ("64", "https://www.ietf.org/media/documents/64-Vancouver-2005.pdf"),
    ("65", "https://www.ietf.org/media/documents/65-Dallas-2006.pdf"),
    ("68", "https://www.ietf.org/media/documents/68-Prague-2007.pdf"),
    ("70", "https://www.ietf.org/media/documents/70-Vancouver-2007.pdf"),
    ("73", "https://www.ietf.org/media/documents/73-Minneapolis-2008.pdf"),
    ("74", "https://www.ietf.org/media/documents/74-SanFrancisco-2009.pdf"),
    ("76", "https://www.ietf.org/media/documents/76-Hiroshima-2009.pdf"),
    ("77", "https://www.ietf.org/media/documents/77-Anaheim-2010.pdf"),
    ("78", "https://www.ietf.org/media/documents/78-Maastricht-2010.pdf"),
    ("79", "https://www.ietf.org/media/documents/79-Beijing-2010.pdf"),
    ("81", "https://www.ietf.org/media/documents/81-Quebec-2011.pdf"),
    ("82", "https://www.ietf.org/media/documents/82-Taipei-2011.pdf"),
    ("83", "https://www.ietf.org/media/documents/83-Paris-2012.pdf"),
    ("84", "https://www.ietf.org/media/documents/84-Vancouver-2012.pdf"),
    ("85", "https://www.ietf.org/media/documents/85-Atlanta-2013.pdf"),
    ("86", "https://www.ietf.org/media/documents/86-Orlando-2013.pdf"),
    ("87", "https://www.ietf.org/media/documents/IETF87-Berlin-Survey.pdf"),
    ("88", "https://www.ietf.org/media/documents/Vancouver88-Meeting-Survey.pdf"),
    ("89", "https://www.ietf.org/media/documents/IETF89-London-Survey-Results.pdf"),
    ("97", "https://www.ietf.org/media/documents/ietf97-survey-results.pdf"),
    ("99", "https://www.ietf.org/media/documents/99_survey_results.pdf"),
    ("100", "https://www.ietf.org/media/documents/100-Survey-Results.pdf"),
    ("101", "https://www.ietf.org/media/documents/101_LondonSurvey.pdf"),
    ("102", "https://www.ietf.org/media/documents/102_MontrealSurvey.pdf"),
    ("103", "https://www.ietf.org/media/documents/103_survey_results.pdf"),
    ("104", "https://www.ietf.org/media/documents/104_survey_results.pdf"),
    ("105", "https://www.ietf.org/media/documents/ietf-105-survey-results.pdf"),
    ("106", "https://www.ietf.org/media/documents/ietf-106-survey-results.pdf"),
    ("107", "https://www.ietf.org/media/documents/ietf-107-survey-results.pdf"),
    ("108", "https://www.ietf.org/media/documents/IETF_108_Meeting_Survey.pdf"),
    ("109", "https://www.ietf.org/media/documents/IETF_109_Post-Meeting_Survey-2.pdf"),
    ("110", "https://www.ietf.org/media/documents/IETF_110_Meeting_Survey.pdf"),
    ("111", "https://www.ietf.org/media/documents/IETF_111_Meeting_Survey.pdf"),
    ("112", "https://www.ietf.org/media/documents/IETF_112_Meeting_Survey.pdf"),
    ("113", "https://www.ietf.org/media/documents/IETF_113_Meeting_Survey.pdf"),
    ("114", "https://www.ietf.org/media/documents/IETF_114_Meeting_Survey-2.pdf"),
    ("115", "https://www.ietf.org/media/documents/IETF_115_Meeting_Survey.pdf"),
    ("116", "https://www.ietf.org/media/documents/IETF_116_Meeting_Survey.pdf"),
    ("117", "https://www.ietf.org/media/documents/IETF_117_Meeting_Survey.pdf"),
    ("118", "https://www.ietf.org/media/documents/IETF_118_Meeting_Survey.pdf"),
    ("119", "https://www.ietf.org/media/documents/IETF_119_Meeting_Survey.pdf"),
    ("120", "https://ietf.co1.qualtrics.com/results/public/aWV0Zi1VUl8zT3laRG9JQWxidUkxZ0otNjZjMzQwNWI4ZjhlYTQwMDA4Nzg5MjNi#/pages/Page_1fe9399e-cacb-4063-af49-ee1340c57993"),
    ("121", "https://www.ietf.org/media/documents/IETF_121_Meeting_Survey_37YLJfu.pdf"),
    ("122", "https://www.ietf.org/media/documents/IETF_122_Meeting_Survey.pdf"),
    ("123", "https://www.ietf.org/media/documents/IETF_123_Madrid_Post-Meeting_Survey.pdf"),
    ("124", "https://www.ietf.org/media/documents/IETF_124_Montreal_Post-Meeting_Survey.pdf"),
    ("125", "https://www.ietf.org/media/documents/IETF_125_Shenzhen_Post-Meeting_Survey.pdf"),
    ("126", "https://www.ietf.org/media/documents/IETF_126_Vienna_Post-Meeting_Survey___Qualtrics_Experience_Management.pdf"),
]


def forward(apps, schema_editor):
    Meeting = apps.get_model("meeting", "Meeting")
    MeetingExtResource = apps.get_model("meeting", "MeetingExtResource")
    meetings = {
        m.number: m
        for m in Meeting.objects.filter(
            type_id="ietf", number__in=[number for number, _ in SURVEY_RESULTS]
        )
    }
    MeetingExtResource.objects.bulk_create(
        MeetingExtResource(meeting=meetings[number], name_id="meeting_survey", value=url)
        for number, url in SURVEY_RESULTS
        if number in meetings
    )


def reverse(apps, schema_editor):
    MeetingExtResource = apps.get_model("meeting", "MeetingExtResource")
    MeetingExtResource.objects.filter(
        name_id="meeting_survey",
        value__in=[url for _, url in SURVEY_RESULTS],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("meeting", "0021_meetingextresource"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
