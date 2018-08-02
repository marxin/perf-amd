#!/usr/bin/env python3

import json
import re
import os
import shutil

from itertools import *

section_mapping = {'Floating Point (FP)': 'floating-point.json',
        'LS': 'memory.json',
        'IC and BP': 'cache.json',
        'DE': 'other.json',
        'EX (SC)': 'core.json',
        'L2 Cache': 'cache.json'}

def convert(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def canonicalize_name(name):
    r = convert(name).upper()
    r = r.replace('-', '_').replace('__', '_')
    for c in r:
        assert c.isdigit() or c.isupper() or c == '_'
    return r.upper()

class GroupValue:
    def __init__(self, bits, value):
        self.bits = bits

        if 'Reserved.' in value:
            self.name = 'reserved'
            self.description = '' 
            return

        i = value.find(' ')
        self.name = value[:i].strip('.').strip(':')
        self.description = value[i + 1:].replace('Read-write. ', '').replace('Reset: 0.', '').replace('Read-only.', '').strip()

    def get_name(self):
        return canonicalize_name(self.name)

    def get_mask(self):
        return hex(1 << int(self.bits))

class Group:
    def __init__(self, name, lines):
        assert name.startswith('PMCx')
        self.pmc = ('0x' + name.split(' ')[0].lstrip('PMCx').lower()).replace('0x0', '0x')
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
        values = zip(bits, values)
        self.values = [GroupValue(x[0], x[1]) for x in values]

    def get_event_name(self):
        name = self.identifier.split(':')[-1]
        return canonicalize_name(name)

    def get_description(self):
        if self.description != '':
            return self.description
        else:
            return self.name + '.'

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
        print(g.pmc + ': ' + g.name + ': ' + g.get_event_name())
        print('  ' + g.description)
        for v in g.values:
            print('   XXX ' + v.get_name() + ':' + v.description)

result = 'output'
shutil.rmtree(result, ignore_errors = True)
os.mkdir(result)

result_json = {}
all_results = []

for s in sections:
    results = []
    for g in s.groups:
        if len(g.values) == 1:
            assert g.values[0].get_name() == 'RESERVED'
            d = {'EventName': g.get_event_name(), 'EventCode': g.pmc, 'BriefDescription': g.get_description()}
            results.append(d)
        else:
            for v in g.values:
                if v.get_name() != 'RESERVED':
                    description = v.description
                    full_description = g.get_description() + ' ' + description
                    if description == '':
                        description = g.get_description() + ' Event name: ' + v.get_name()
                        full_description = description
                    d = {'EventName': g.get_event_name() + '.' + v.get_name(), 'EventCode': g.pmc, 'BriefDescription': description,
                            'PublicDescription': full_description, 'UMask': v.get_mask()}
                    results.append(d)
    f = section_mapping[s.name]
    if not f in result_json:
        result_json[f] = []
    result_json[f] += results
    all_results += results

for f in result_json.keys():
    with open(os.path.join(result, f), 'a') as outfile:
        json.dump(result_json[f], outfile, indent = 2)

with open('all-events.json', 'w') as outfile:
    json.dump(all_results, outfile, indent = 2)
