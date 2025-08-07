import sys
import traceback

__author__ = "rohe0002"


def tobytes(value) -> bytes:
    """Convert value to bytes."""
    if isinstance(value, bytes):
        return value
    else:
        if isinstance(value, str):
            return value.encode()
        else:
            return bytes(value)


def exception_trace(tag, exc, log=None):
    message = traceback.format_exception(*sys.exc_info())
    if log:
        log.error("[%s] ExcList: %s", tag, "".join(message))
        log.error("[%s] Exception: %s", tag, exc)
    else:
        print("[{0}] ExcList: {1}".format(tag, "".join(message)), file=sys.stderr)
        print("[{0}] Exception: {1}".format(tag, exc), file=sys.stderr)


SORT_ORDER = {"RS": 0, "ES": 1, "HS": 2, "PS": 3, "no": 4}


def sort_sign_alg(alg1, alg2):
    if SORT_ORDER[alg1[0:2]] < SORT_ORDER[alg2[0:2]]:
        return -1
    elif SORT_ORDER[alg1[0:2]] > SORT_ORDER[alg2[0:2]]:
        return 1
    else:
        if alg1 < alg2:
            return -1
        elif alg1 > alg2:
            return 1
        else:
            return 0
