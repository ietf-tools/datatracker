#!/usr/bin/env python

Scripts='Scripts.txt'
ScriptExtensions='ScriptExtensions.txt'
PropertyValueAliases='PropertyValueAliases.txt'

SCRIPT_ABBREVS = {}

with open(PropertyValueAliases, 'r') as f:
    for line in f:
        line = line.strip()
        if len(line) == 0 or line[0] == '#':
            continue

        if line[0:2] != 'sc':
            continue

        if '#' in line:
            line = line[0 : line.index('#')]

        fields = line.split(';')
        fields = [field.strip() for field in fields]

        if fields[0] != 'sc':
            continue

        SCRIPT_ABBREVS[fields[1]] = fields[2]


RANGES={}
def parse_uni_range(range_str):
    '''Convert Unicode range notation to Python ranges.

Single codepoints are converted to single-number ranges.  That is:

'0001..0003' -> range(1, 4)
'0001' -> range(1, 2)
   '''
    start_stop_strs = range_str.split('..')
    start = int(start_stop_strs[0], 16)

    if len(start_stop_strs) > 1:
        end = int(start_stop_strs[1], 16)
    else:
        end = start + 1

    char_range = range(start, end+1)
    return(char_range)


with open(Scripts, 'r') as f:
    for line in f:
        line = line.strip()

        if len(line) == 0 or line[0] == '#':
            continue

        if '#' in line:
            line = line[0 : line.index('#')]

        fields = line.split(';')
        fields = [field.strip() for field in fields]

        if fields[1] not in RANGES.keys():
            RANGES[fields[1]] = []

        RANGES[fields[1]].append(parse_uni_range(fields[0]))

with open(ScriptExtensions, 'r') as f:
    for line in f:
        line = line.strip()

        if len(line) == 0 or line[0] == '#':
            continue

        if '#' in line:
            line = line[0 : line.index('#')]

        fields = line.split(';')
        fields = [field.strip() for field in fields]

        char_range = parse_uni_range(fields[0])
        scripts = fields[1].split()

        for script_shortname in scripts:
            longname = SCRIPT_ABBREVS[script_shortname]
            RANGES[longname].append(char_range)

# this facilitates tests later on
if 'Unknown' not in RANGES.keys():
    RANGES['Unknown'] = []

print('RANGES = ' + repr(RANGES))
print('SCRIPT_ABBREVS = ' + repr(SCRIPT_ABBREVS))
