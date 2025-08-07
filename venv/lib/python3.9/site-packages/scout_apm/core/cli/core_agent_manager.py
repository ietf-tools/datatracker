# coding=utf-8

import argparse
import logging

from scout_apm.core import CoreAgentManager

logger = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="count"
    )

    subparsers = parser.add_subparsers(
        title="subcommands", description="valid subcommands", dest="subparser"
    )
    subparsers.add_parser("download")
    subparsers.add_parser("launch")

    args = parser.parse_args(argv)

    if args.verbose is not None:
        if args.verbose >= 2:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

    core_agent_manager = CoreAgentManager()
    getattr(core_agent_manager, args.subparser)()
