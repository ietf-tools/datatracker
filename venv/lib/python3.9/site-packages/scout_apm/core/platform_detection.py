# coding=utf-8

import platform


def is_valid_triple(triple):
    values = triple.split("-", 1)
    return (
        len(values) == 2
        and values[0] in ("i686", "x86_64", "aarch64", "unknown")
        and values[1]
        in ("unknown-linux-gnu", "unknown-linux-musl", "apple-darwin", "unknown")
        # Validate _apple_darwin_aarch64_override was applied.
        and triple != "aarch64-apple-darwin"
    )


def _apple_darwin_aarch64_override(triple):
    """
    If using M1 ARM64 machine, still use x86_64.
    See https://github.com/scoutapp/scout_apm_python/issues/683
    """
    if triple == "aarch64-apple-darwin":
        return "x86_64-apple-darwin"
    return triple


def get_triple():
    return _apple_darwin_aarch64_override(
        "{arch}-{platform}".format(arch=get_arch(), platform=get_platform())
    )


def get_arch():
    """
    What CPU are we on?
    """
    arch = platform.machine()
    if arch == "i686":
        return "i686"
    elif arch == "x86_64":
        return "x86_64"
    elif arch == "aarch64":
        return "aarch64"
    elif arch == "arm64":
        # We treat these as synonymous and name them "aarch64" for consistency
        # Mac OS, for example, uses "arm64"
        return "aarch64"
    else:
        return "unknown"


def get_platform():
    """
    What Operating System (and sub-system like glibc / musl)
    """
    system_name = platform.system()
    if system_name == "Linux":
        # Previously we'd use either "-gnu" or "-musl" indicate which version
        # of libc we were built against. We now default to musl since it
        # reliably works on all platforms.
        return "unknown-linux-musl"
    elif system_name == "Darwin":
        return "apple-darwin"
    else:
        return "unknown"
