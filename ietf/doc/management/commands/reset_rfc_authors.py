# Copyright The IETF Trust 2024, All Rights Reserved

# Reset an RFC's authors to those of the draft it came from
from django.core.management.base import BaseCommand, CommandError

from ietf.doc.models import Document, DocEvent
from ietf.person.models import Person


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("rfcnum", type=int, help="RFC number to modify")
        parser.add_argument(
            "--force",
            action="store_true",
            help="reset even if RFC already has authors",
        )

    def handle(self, *args, **options):
        try:
            rfc = Document.objects.get(type="rfc", rfc_number=options["rfcnum"])
        except Document.DoesNotExist:
            raise CommandError(
                f"rfc{options['rfcnum']} does not exist in the Datatracker."
            )

        draft = rfc.came_from_draft()
        if draft is None:
            raise CommandError(f"{rfc.name} did not come from a draft. Can't reset.")

        orig_authors = rfc.documentauthor_set.all()
        if orig_authors.exists():
            # Potentially dangerous, so refuse unless "--force" is specified
            if not options["force"]:
                raise CommandError(
                    f"{rfc.name} already has authors. Not resetting. Use '--force' to reset anyway."
                )
            removed_auth_names = list(orig_authors.values_list("person__name", flat=True))
            rfc.documentauthor_set.all().delete()
            DocEvent.objects.create(
                doc=rfc,
                by=Person.objects.get(name="(System)"),
                type="edited_authors",
                desc=f"Removed all authors: {', '.join(removed_auth_names)}",
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Removed author(s): {', '.join(removed_auth_names)}"
                )
            )

        for author in draft.documentauthor_set.all():
            # Copy the author but point at the new doc.
            # See https://docs.djangoproject.com/en/4.2/topics/db/queries/#copying-model-instances
            author.pk = None
            author.id = None
            author._state.adding = True
            author.document = rfc
            author.save()
            self.stdout.write(
                self.style.SUCCESS(f"Added author {author.person.name} <{author.email}>")
            )
        auth_names = draft.documentauthor_set.values_list("person__name", flat=True)
        DocEvent.objects.create(
            doc=rfc,
            by=Person.objects.get(name="(System)"),
            type="edited_authors",
            desc=f"Set authors from rev {draft.rev} of {draft.name}: {', '.join(auth_names)}",
        )
