import sys, re

with open("aliases") as afile:
    try:
        aliases = dict([line.strip().split(None, 1) for line in afile.read().splitlines() if line.strip()])
    except ValueError:
        sys.stderr.write([line.strip().split(None, 1) for line in afile.read().splitlines() if line.strip()])
        raise

for line in sys.stdin:
    try:
        blank, name, email, rest = line.strip().split("||", 3)
        email = email.strip()
    except ValueError:
        sys.stderr.write(line + "\n")
        raise

    login, dummy = re.split("[@.]", email, 1)
    if email in aliases:
        login = aliases[email]
    print("\t".join((login.strip().lower(), email.strip().lower(), name.strip())))
