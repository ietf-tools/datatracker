# Copyright The IETF Trust 2026, All Rights Reserved

from django.db import migrations


def forward(apps, schema_editor):
    State = apps.get_model("doc", "State")
    for name, desc in [
        (
            "Adopted by a WG",
            "The individual submission document has been adopted by the Working Group (WG), but some administrative matter still needs to be completed (e.g., a WG document replacing this document with the typical naming convention of 'draft-ietf-wgname-topic-nn' has not yet been submitted).",
        ),
        (
            "WG Document",
            "The document has been identified as a Working Group (WG) document and is under development per Section 7.2 of RFC2418.",
        ),
        (
            "Waiting for WG Chair Go-Ahead",
            "The Working Group (WG) document has completed Working Group Last Call (WGLC), but the WG chairs are not yet ready to call consensus on the document. The reasons for this may include comments from the WGLC need to be responded to, or a revision to the document is needed.",
        ),
        (
            "Submitted to IESG for Publication",
            "The Working Group (WG) document has been submitted to the Internet Engineering Steering Group (IESG) for evaluation and publication per Section 7.4 of RFC2418.  See the “IESG State” or “RFC Editor State” for further details on the state of the document.",
        ),
    ]:
        State.objects.filter(name=name).update(desc=desc, type="draft-stream-ietf")


def reverse(apps, schema_editor):
    State = apps.get_model("doc", "State")
    for name, desc in [
        (
            "Adopted by a WG",
            "The individual submission document has been adopted by the Working Group (WG), but a WG document replacing this document with the typical naming convention of 'draft- ietf-wgname-topic-nn' has not yet been submitted.",
        ),
        (
            "WG Document",
            "The document has been adopted by the Working Group (WG) and is under development.  A document can only be adopted by one WG at a time.  However, a document may be transferred between WGs.",
        ),
        (
            "Waiting for WG Chair Go-Ahead",
            "The Working Group (WG) document has completed Working Group Last Call (WGLC), but the WG chair(s) are not yet ready to call consensus on the document. The reasons for this may include comments from the WGLC need to be responded to, or a revision to the document is needed",
        ),
        (
            "Submitted to IESG for Publication",
            "The Working Group (WG) document has left the WG and been submitted to the Internet Engineering Steering Group (IESG) for evaluation and publication.  See the “IESG State” or “RFC Editor State” for further details on the state of the document.",
        ),
    ]:
        State.objects.filter(name=name).update(desc=desc, type="draft-stream-ietf")


class Migration(migrations.Migration):
    dependencies = [
        ("doc", "0030_alter_dochistory_title_alter_document_title"),
    ]

    operations = [migrations.RunPython(forward, reverse)]
