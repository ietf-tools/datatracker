# Copyright The IETF Trust 2024, All Rights Reserved
import django

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from pathlib import Path

from ietf.utils import patch


class Command(BaseCommand):
    """Apply IETF patches to libraries"""
    requires_system_checks = tuple()

    def handle(self, *args, **options):
        library_path = Path(django.__file__).parent.parent
        top_dir = Path(settings.BASE_DIR).parent 

        # All patches in settings.CHECKS_LIBRARY_PATCHES_TO_APPLY must have a
        # relative file path starting from the site-packages dir, e.g.
        # 'django/db/models/fields/__init__.py'
        for patch_file in settings.CHECKS_LIBRARY_PATCHES_TO_APPLY:
            patch_set = patch.fromfile(top_dir / Path(patch_file))
            if not patch_set:
                raise CommandError(f"Could not parse patch file '{patch_file}'")
            if not patch_set.apply(root=bytes(library_path)):
                raise CommandError(f"Could not apply the patch from '{patch_file}'")
            if patch_set.already_patched:
                self.stdout.write(f"Patch from '{patch_file}' was already applied")
            else:
                self.stdout.write(f"Applied the patch from '{patch_file}'")
