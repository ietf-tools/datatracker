#!/usr/bin/env python
import argparse
import copy
import json
import os
import shelve  # nosec
import sys
from builtins import input
from typing import Any
from typing import List
from urllib.parse import parse_qs
from urllib.parse import urlparse

from oic import rndstr
from oic.oic.provider import secret
from oic.utils.clientdb import BaseClientDatabase

__author__ = "rolandh"


def unpack_redirect_uri(redirect_uris):
    res = []
    for item in redirect_uris:
        (base, query) = item
        if query:
            res.append("%s?%s" % (base, query))
        else:
            res.append(base)
    return res


def pack_redirect_uri(redirect_uris):
    ruri = []
    for uri in redirect_uris:
        parts = urlparse(uri)
        if parts.fragment:
            print("Faulty redirect uri, contains fragment", file=sys.stderr)
        query = parts.query
        base = parts._replace(query="").geturl()
        if query:
            ruri.append([base, parse_qs(query)])
        else:
            ruri.append([base, None])

    return ruri


class CDB(BaseClientDatabase):
    """Implementation of ClientDatabase with shelve."""

    def __init__(self, filename):
        self.cdb = shelve.open(filename, writeback=True)  # nosec
        self.seed = rndstr(32).encode("utf-8")

    def __getitem__(self, item):
        return self.cdb[item]

    def keys(self):
        return self.cdb.keys()

    def items(self):
        return self.cdb.items()

    def create(self, redirect_uris=None, policy_uri="", logo_uri="", jwks_uri=""):
        if redirect_uris is None:
            print("Enter redirect_uris one at the time, end with a blank line: ")
            redirect_uris = []
            while True:
                redirect_uri = input("?: ")
                if redirect_uri:
                    redirect_uris.append(redirect_uri)
                else:
                    break
        if not policy_uri:
            policy_uri = input("Enter policy_uri or just return: ")
        if not logo_uri:
            logo_uri = input("Enter logo_uri or just return: ")

        client_id = rndstr(12)
        while client_id in self.cdb.keys():
            client_id = rndstr(12)

        client_secret = secret(self.seed, client_id)

        info = {
            "client_secret": client_secret,
            "client_id": client_id,
            "client_salt": rndstr(8),
            "redirect_uris": pack_redirect_uri(redirect_uris),
        }

        if policy_uri:
            info["policy_uri"] = policy_uri
        if logo_uri:
            info["logo_uri"] = logo_uri
        if jwks_uri:
            info["jwks_uri"] = jwks_uri

        self.cdb[client_id] = info

        return self.cdb[client_id]

    def __delitem__(self, key):
        del self.cdb[key]

    def __setitem__(self, key, value):
        self.cdb[key] = value

    def load(self, filename):
        with open(filename) as f:
            info = json.loads(f.read())
        for item in info:
            if isinstance(item, list):
                self.cdb[str(item[0])] = item[1]
            else:
                _tmp = copy.copy(item)
                try:
                    for uris in ["redirect_uris", "post_logout_redirect_uris"]:
                        try:
                            _tmp[uris] = unpack_redirect_uri(_tmp[uris])
                        except KeyError:
                            pass
                except Exception:
                    print("Faulty specification: {}".format(item))
                else:
                    self.cdb[str(item["client_id"])] = item

    def dump(self, filename):
        res: List[Any] = []
        for key, val in self.cdb.items():
            if isinstance(val, dict):
                res.append(val)
            else:
                res.append([key, val])

        with open(filename, "w") as fp:
            json.dump(res, fp)


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l", "--list", dest="list", action="store_true", help="List all client_ids"
    )
    parser.add_argument(
        "-d",
        "--delete",
        dest="delete",
        action="store_true",
        help="Delete the entity with the given client_id",
    )
    parser.add_argument(
        "-c",
        "--create",
        dest="create",
        action="store_true",
        help=("Create a new client, returns the stored information"),
    )
    parser.add_argument(
        "-s",
        "--show",
        dest="show",
        action="store_true",
        help=("Show information connected to a specific client_id"),
    )
    parser.add_argument(
        "-i",
        "--client-id",
        dest="client_id",
        help="A client_id on which to do an action",
    )
    parser.add_argument(
        "-r",
        "--replace",
        dest="replace",
        help=(
            "Information that should replace what's there about a specific client_id"
        ),
    )
    parser.add_argument(
        "-I",
        "--input-file",
        dest="input_file",
        help="Import client information from a file",
    )
    parser.add_argument(
        "-D",
        "--output-file",
        dest="output_file",
        help="Dump client information to a file",
    )
    parser.add_argument(
        "-R",
        "--reset",
        dest="reset",
        action="store_true",
        help="Reset the database == removing all registrations",
    )
    parser.add_argument(dest="filename")
    args = parser.parse_args()

    if args.reset:
        os.unlink(args.filename)

    cdb = CDB(args.filename)

    if args.list:
        for client_id in list(cdb.keys()):
            print(client_id)
    elif args.client_id:
        if args.delete:
            del cdb[args.client_id]
        elif args.show:
            print(cdb[args.client_id])
        elif args.replace:
            cdb[args.client_id] = args.replace
    elif args.create:
        print(cdb.create())
    elif args.delete or args.show or args.replace:
        print("You have to specify a client_id !")
    elif args.input_file:
        cdb.load(args.input_file)
    elif args.output_file:
        cdb.dump(args.output_file)


if __name__ == "__main__":
    run()
