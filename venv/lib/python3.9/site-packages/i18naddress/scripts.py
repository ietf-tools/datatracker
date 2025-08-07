import logging
from argparse import ArgumentParser

logging.basicConfig()
logger = logging.getLogger("i18naddress")


def download_json_files():
    from i18naddress.downloader import download  # deferred because of multiprocessing

    logger.setLevel(logging.DEBUG)

    parser = ArgumentParser(
        description="Download all addresses data from Google i18n API"
    )
    parser.add_argument(
        "--country", default=None, help="Alpha-2 code of the country to download"
    )
    args = parser.parse_args()

    download(country=args.country)
