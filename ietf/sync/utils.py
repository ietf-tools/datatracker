# Copyright The IETF Trust 2026, All Rights Reserved

import subprocess


def rsync_helper(subprocess_arg_array: list[str]):
    subprocess.run(subprocess_arg_array)
