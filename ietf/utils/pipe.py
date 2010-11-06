# Simplified interface to os.popen3()

def pipe(cmd, str=None):
    from popen2 import Popen3 as Popen
    bufsize = 4096
    MAX = 65536*16

    if str and len(str) > 4096:                 # XXX: Hardcoded Linux 2.4, 2.6 pipe buffer size
        bufsize = len(str)

    pipe = Popen(cmd, True, bufsize)
    if str:
        pipe.tochild.write(str)
        pipe.tochild.close()

    out = ""
    err = ""
    while True:
        str = pipe.fromchild.read()
        if str:
            out += str
        code = pipe.poll()
        if code > -1:
            err = pipe.childerr.read()
            break
        if len(out) >= MAX:
            err = "Output exceeds %s bytes and has been truncated"
            break

    return (code, out, err)
