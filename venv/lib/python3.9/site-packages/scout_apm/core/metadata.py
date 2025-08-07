# coding=utf-8

import datetime as dt
import sys
from os import getpid

from scout_apm.core.agent.commands import ApplicationEvent, format_dt_for_core_agent
from scout_apm.core.agent.socket import CoreAgentSocketThread
from scout_apm.core.config import scout_config


def report_app_metadata():
    CoreAgentSocketThread.send(
        ApplicationEvent(
            event_type="scout.metadata",
            event_value=get_metadata(),
            source="Pid: " + str(getpid()),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )
    )


def get_metadata():
    data = {
        "language": "python",
        "language_version": "{}.{}.{}".format(*sys.version_info[:3]),
        "server_time": format_dt_for_core_agent(dt.datetime.now(dt.timezone.utc)),
        "framework": scout_config.value("framework"),
        "framework_version": scout_config.value("framework_version"),
        "environment": "",
        "app_server": scout_config.value("app_server"),
        "hostname": scout_config.value("hostname"),
        "database_engine": "",
        "database_adapter": "",
        "application_name": "",
        "libraries": get_python_packages_versions(),
        "paas": "",
        "application_root": scout_config.value("application_root"),
        "scm_subdirectory": scout_config.value("scm_subdirectory"),
        "git_sha": scout_config.value("revision_sha"),
    }
    # Deprecated - see #327:
    data["version"] = data["language_version"]
    return data


def get_python_packages_versions():
    try:
        from importlib.metadata import distributions
    except ImportError:
        # For some reason it is unavailable
        return []

    return sorted(
        (
            distribution.metadata["Name"],
            (distribution.metadata["Version"] or "Unknown"),
        )
        for distribution in distributions()
        # Filter out distributions wtih None for name or value. This can be the
        # case for packages without a METADATA or PKG-INFO file in their relevant
        # distribution directory. According to comments in importlib.metadata
        # internals this is possible for certain old packages, but I could only
        # recreate it by deliberately deleting said files.
        if distribution.metadata["Name"]
    )
