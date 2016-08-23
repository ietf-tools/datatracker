# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os, datetime

from django.db import migrations
from django.conf import settings

def rename_x3s3dot3_forwards(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    Group.objects.filter(acronym="x3s3.3").update(acronym="x3s3dot3")

def rename_x3s3dot3_backwards(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    Group.objects.filter(acronym="x3s3dot3").update(acronym="x3s3.3")

def get_rid_of_empty_charters(apps, schema_editor):
    Group = apps.get_model("group", "Group")

    for acronym in ["fun", "multrans", "cicm", "woes", "dcon", "sdn", "i2aex", "rpsreqs", "antitrust", "iprbis", "dsii"]:
        group = Group.objects.get(acronym=acronym)
        if group.charter:
            charter = group.charter

            # clean up any empty files left behind
            revisions = set()
            revisions.add(charter.rev)
            for h in charter.history_set.all():
                revisions.add(h.rev)

            for rev in revisions:
                path = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (charter.name, rev))
                try:
                    if os.path.exists(path):
                        with open(path, 'r') as f:
                            if f.read() == "":
                                os.remove(path)
                except IOError:
                    pass

            group.charter = None
            group.save()

            charter.delete()


def fix_empty_rrg_charter(apps, schema_editor):
    Document = apps.get_model("doc", "Document")
    DocEvent = apps.get_model("doc", "DocEvent")
    NewRevisionDocEvent = apps.get_model("doc", "NewRevisionDocEvent")
    Person = apps.get_model("person", "Person")
    State = apps.get_model("doc", "State")

    charter = Document.objects.get(name="charter-irtf-rrg")
    system = Person.objects.get(name="(System)")

    if charter.rev == "00-00":
        charter.rev = "01"
        charter.time = datetime.datetime.now()
        charter.save()

        NewRevisionDocEvent.objects.create(
            rev=charter.rev,
            doc=charter,
            type="new_revision",
            by=system,
            desc="New version available: <b>%s-%s.txt</b>" % (charter.name, charter.rev),
            time=charter.time,
        )

        DocEvent.objects.create(
            doc=charter,
            type="added_comment",
            by=system,
            desc="Added existing charter",
            time=charter.time,
        )

        approved = State.objects.get(type="charter", slug="approved")
        already_set = list(charter.states.filter(type="charter"))
        if already_set:
            charter.states.remove(*already_set)
        charter.states.add(approved)

        path = os.path.join(settings.CHARTER_PATH, '%s-%s.txt' % (charter.name, charter.rev))
        with open(path, "w") as f:
            f.write("""The Routing Research Group (RRG) is chartered to explore routing and addressing problems that are important to the development of the Internet but are not yet mature enough for engineering work within the IETF. As the Internet continues to evolve, the challenges in providing a scalable and robust global routing system will also change over time. At the moment, the Internet routing and addressing architecture is facing challenges in scalability, mobility, multi-homing, and inter-domain traffic engineering. Thus the RRG proposes to focus its effort on designing an alternate architecture to meet these challenges. Although Internet routing is a broad and active research area, a focused effort at this time is necessary to assure rapid progress towards reaching the goal.

More specifically, we propose to explore architectural alternatives, including, but not limited to, separating host location and identification information. Research and experimentation in addressing and routing algorithms will be encouraged to understand whether this new direction can provide effective solutions, to work out candidate designs as necessary for a complete solution, and to fully understand both the gains and the tradeoffs that the new solutions may bring. The group will produce a list of prioritized design goals and a recommendation for a routing and addressing architecture.

The RRG will have an open general discussion mailing list where any topic of interest to the routing research community can be discussed, and topics related to scalable routing architectures are particularly encouraged. For specific topics with widespread discussion, interested parties will be encouraged to form ad-hoc mailing lists, with summaries sent to the general mailing list quarterly. Summaries will contain the recent conclusions reached as well as the near-term agenda for future progress.

It is commonly recognized that productive design efforts can be carried out by small and focused design teams. The RRG encourages the formation of focused design teams to explore specific design choices. As with ad-hoc mailing lists, individual design teams are required to report back quarterly to the RRG with their progress and remaining open issues. Each design team is expected to produce a set of Internet Drafts that documents their current thinking.

The RRG, as a whole, will hold open meetings from time to time to solicit input from, and supply information to, the broader community. In particular, at least once per year there will be a review of the group's activities held at an IETF meeting. More frequent meetings will be held if it will speed group progress. Ad-hoc and design team meetings are strongly encouraged.

The output of the group will consist of Informational and Experimental RFCs as well as Journal Articles on the topics covered by the subgroups.""")



def fix_cicm_state(apps, schema_editor):
    Group = apps.get_model("group", "Group")
    Group.objects.filter(acronym="cicm").update(state="bof-conc")

def noop(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('doc', '0010_auto_20150930_0251'),
        ('group', '0006_auto_20150718_0509'),
    ]

    operations = [
        migrations.RunPython(rename_x3s3dot3_forwards, rename_x3s3dot3_backwards),
        migrations.RunPython(fix_empty_rrg_charter, noop),
        migrations.RunPython(get_rid_of_empty_charters, noop),
        migrations.RunPython(fix_cicm_state, noop),
    ]
