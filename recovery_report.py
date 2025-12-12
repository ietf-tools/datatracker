import sys

from hashlib import sha384

def main(source_file):
    source_lines = open(source_file, "r").readlines()
    table_in_progress = None
    for line in source_lines:
        if any([
            line[0] not in ["<",">"],
            line[2:].startswith("\\restrict"),
            line[2:].startswith("\\unrestrict"),
            line[2:].startswith("SELECT"),
        ]):
            continue
        if table_in_progress is None:
            assert(line.startswith("< COPY"))
            table_in_progress = line.split()[2]
            left_side = []
            right_side = []
        elif line.startswith("< COPY"):
            if set(left_side)!=set(right_side):
                print(f"Unexpected difference at {table_in_progress}")
                print("Left side")
                print("".join(left_side))
                print("Right side")
                print("".join(right_side))
            table_in_progress = line.split()[2]
            left_side = []
            right_side = []
        else:
            if line.startswith("< "):
                left_side.append(line[2:])
            elif line.startswith("> "):
                right_side.append(line[2:])
            else:
                raise Exception(f"Unexpeced line encountered: {line}")
    # In case the last line was a data line
    assert(set(left_side)==set(right_side))
    digest = sha384()
    with open("recovery.sql","rb") as f:
        digest.update(f.read())
    assert digest.hexdigest() == "6944d0dc7d0b8b2bb582072f6dd9ca806700ac79ee3a3b3b00c07a6a08e73515312bcff0d9dbbdafd1f332721d96276a"
    print("Recovery is as expected")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python recovery_report.py <diff_recovered.txt>")
        sys.exit(1)
    
    source_file = sys.argv[1]
    main(source_file)
