# Copyright The IETF Trust 2025, All Rights Reserved
# -*- coding: utf-8 -*-
import os
import re


class FileAccessError(Exception):
    """File access error"""

    pass


def can_access(options, source, path, access_templates=False):
    # templates can be always accessed
    template_path = os.path.abspath(os.path.join(options.template_dir, path))
    if (
        access_templates
        and template_path.startswith(options.template_dir)
        and os.path.exists(template_path)
    ):
        return True

    # user allowed access?
    if not options.allow_local_file_access:
        raise FileAccessError(
            f"Can not access local file: {path}. Use --allow-local-file-access enable access."
        )

    # does it have shell meta-chars?
    shellmeta = re.compile("[><*[`$|;&(#]")
    if shellmeta.search(path):
        raise FileAccessError(f"Found disallowed shell meta-characters in {path}")

    # file is within the source dir?
    dir = os.path.abspath(os.path.dirname(source))
    path = os.path.abspath(os.path.join(dir, path))
    if not path.startswith(dir):
        raise FileAccessError(
            f"Expected a file located beside or below the .xml source (in {dir}), but found a reference to {path}"
        )

    # does it exists?
    if not os.path.exists(path):
        raise FileAccessError(f"Expected a file at '{path}', but no such file exists")

    return True
