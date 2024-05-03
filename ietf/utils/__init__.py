# Copyright The IETF Trust 2007-2024, All Rights Reserved
import subprocess


class _ToolVersionManager:
    _known = [
        "pyang",
        "xml2rfc",
        "xym",
        "yanglint",
    ]
    _versions = dict()

    def __getitem__(self, item):
        if item not in self._known:
            return "Unknown"
        if item not in self._versions:
            result = subprocess.run(
                [item, "--version"],
                capture_output=True,
                check=True,
            )
            if result.returncode != 0:
                version = "Unknown"
            else:
                version = "\n".join(
                    [
                        result.stdout.decode().strip(),
                        result.stderr.decode().strip(),
                    ]
                ).strip()
            self._versions[item] = version
        return self._versions[item]


tool_version = _ToolVersionManager()
