# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-


# Simplified interface to os.popen3()

def pipe(cmd, str=None):
    from subprocess import Popen, PIPE
    bufsize = 4096
    MAX = 65536*16

    if str and len(str) > 4096:                 # XXX: Hardcoded Linux 2.4, 2.6 pipe buffer size
        bufsize = len(str)

    pipe = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, bufsize=bufsize, shell=True)
    if not str is None:
        pipe.stdin.write(str)
        pipe.stdin.close()

    out = b""
    err = b""
    while True:
        str = pipe.stdout.read()
        if str:
            out += str
        code = pipe.poll()
        if code != None:
            err = pipe.stderr.read()
            break
        if len(out) >= MAX:
            err = "Output exceeds %s bytes and has been truncated" % MAX
            break

    return (code, out, err)
