# coding=utf-8

import importlib
import logging

from scout_apm.core.config import scout_config

logger = logging.getLogger(__name__)

instrument_names = ["elasticsearch", "jinja2", "pymongo", "redis", "urllib3"]


def ensure_all_installed():
    disabled_instruments = scout_config.value("disabled_instruments")
    for instrument_name in instrument_names:
        if instrument_name in disabled_instruments:
            logger.info("%s instrument is disabled. Skipping.", instrument_name)
            continue

        module = importlib.import_module("{}.{}".format(__name__, instrument_name))
        module.ensure_installed()
