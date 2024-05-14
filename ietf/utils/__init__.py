# Copyright The IETF Trust 2007-2024, All Rights Reserved
import subprocess


class _ToolVersionManager:
    _known = [
        "pyang",
        "xml2rfc",
        "xym",
        "yanglint",
    ]
    _versions: dict[str, str] = dict()

    def __getitem__(self, item):
        if item not in self._known:
            return "Unknown"
        elif item not in self._versions:
            try:
                self._versions[item] = subprocess.run(
                    [item, "--version"],
                    capture_output=True,
                    check=True,
                ).stdout.decode().strip()
            except subprocess.CalledProcessError:
                return "Unknown"
        return self._versions[item]


tool_version = _ToolVersionManager()
