# Copyright The IETF Trust 2026, All Rights Reserved

import subprocess
from typing import List

def rsync_helper(subprocess_arg_array:List[str]):
    subprocess.run(subprocess_arg_array)
