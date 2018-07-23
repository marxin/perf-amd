#!/usr/bin/env python3

from itertools import *

class Group:
    def __init__(self, name, lines):
        name = name[name.find(' ') + 1:name.rfind(' ')]
        assert name[0] == '['
        assert name[-1] == ']'
        self.name = name[1:-1]
        self.lines = lines

        if lines[0].startswith('Read-write'):
            lines = lines[1:]

        # parse description
        description_lines = list(takewhile(lambda x: not x.startswith('Core::'), lines))
        self.description = ' '.join(description_lines).strip()
        lines = lines[len(description_lines):]

        # parse identifier
        self.identifier = lines[0].split(';')[0]
        lines = lines[1:]
        assert lines[0] == 'Bits'
        lines = lines[1:]

        # parse bits
        bits = list(takewhile(lambda x: x.startswith('Description') or x[0].isdigit(), lines))
        lines = lines[len(bits):]
        bits = list(filter(lambda x: not '.' in x and not 'Description' in x, bits))
        values = []
        while len(lines) > 0:
            parts = [lines[0]]
            parts += list(takewhile(lambda x: not 'Reserved' in x and not 'Read-write' in x and not 'Read-only' in x, lines[1:]))
            values.append(' '.join(parts))
            lines = lines[len(parts):]

        assert len(bits) == len(values)
        self.values = zip(bits, values)

class Section:
    def __init__(self, name, lines):
        self.name = name[:-len(' Events')]

        self.groups = []

        # parse groups
        group_fn = lambda x: not x.startswith('PMCx') and not x.startswith('L3PMCx')
        lines = list(dropwhile(group_fn, lines))

        while len(lines) > 0:
            group_name = lines[0]
            assert not group_fn(group_name)
            lines = lines[1:]

            # trim first line
            if 'Read-write' in lines[0]:
                lines = lines[1:]

            group_lines = list(takewhile(group_fn, lines))
            self.groups.append(Group(group_name, group_lines))
            lines = lines[len(group_lines):]

lines = [x.strip() for x in open('amd_fam17_counters.txt').readlines()]

# strip page headers
lines = [x for x in lines if not 'Rev 1.14' in x and not 'PPR for AMD Family' in x]

# parse sections
section_fn = lambda x: not x.endswith(' Events')

lines = list(dropwhile(section_fn, lines))

sections = []

while len(lines) > 0:
    section_name = lines[0]
    lines = lines[1:]
    section_lines = list(takewhile(section_fn, lines))
    sections.append(Section(section_name, section_lines))
    lines = lines[len(section_lines):]

for s in sections:
    print('=== SECTION: ' + s.name + ' ===')
    for g in s.groups:
        print('  ' + g.name + ': ' + g.identifier)
        for v in g.values:
            print('   ' + str(v))
