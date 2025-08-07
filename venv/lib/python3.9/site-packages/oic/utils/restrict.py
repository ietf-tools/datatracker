import inspect
import json
import sys

__author__ = "roland"


def single(restriction, cinfo):
    for s in restriction:
        try:
            if len(cinfo[s]) != 1:
                return "Too Many {}".format(s)
        except KeyError:
            pass
    return ""


def map_grant_type2response_type(restriction, cinfo):
    if "grant_types" in cinfo and "response_types" in cinfo:
        for g, r in restriction.items():
            if g in cinfo["grant_types"] and r in cinfo["response_types"]:
                pass
            elif g in cinfo["grant_types"] or r in cinfo["response_types"]:
                return "grant_type didn't match response_type"
    return ""


def map(restriction, cinfo):
    for fname, spec in restriction.items():
        func = factory("map_" + fname)
        resp = func(spec, cinfo)
        if resp:
            return resp
    return ""


def allow(restriction, cinfo):
    for param, args in restriction.items():
        try:
            _cparam = cinfo[param]
        except KeyError:
            continue

        if isinstance(_cparam, str):
            if _cparam not in args:
                return "Not allowed to register with {}={}".format(param, _cparam)
        else:
            if not set(_cparam).issubset(args):
                return "Not allowed to register with {}={}".format(
                    param, json.dumps(_cparam)
                )

    return ""


def assign(restriction, cinfo):
    cinfo.update(restriction)


def factory(name):
    for fname, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isfunction(obj):
            if fname == name:
                return obj

    return None
