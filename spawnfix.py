import os
import json

workdir = os.path.dirname(os.path.realpath(__file__))

SPAWN_UNDEF = -1
SPAWN_DEF = 1
SPAWN_1x15 = 101
SPAWN_1x30 = 102
SPAWN_1x45 = 103
SPAWN_1x60 = 104
SPAWN_1x45h2 = 201 # 2x15
SPAWN_1x60h3 = 202

alldata= {'spawns': [],'emptylocs': [],'gyms': [],'stops': []}

alldata_path = workdir + '/mapdata.json'


def spawnstats(scandata):
    types = [SPAWN_1x15, SPAWN_1x30, SPAWN_1x45, SPAWN_1x60, SPAWN_1x45h2, SPAWN_1x60h3, SPAWN_UNDEF]
    typestrs = ['1x15', '1x30', '1x45', '1x60', '2x15', '1x60h3', 'UNDEF']
    typecount = [0, 0, 0, 0, 0, 0, 0]
    tallcount = len(scandata['spawns'])

    for spawn in scandata['spawns']:
        for t in range(0, len(types)):
            if spawn['type'] == types[t]:
                typecount[t] += 1

    print('[+] Spawn point count: {}'.format(tallcount))
    for t in range(0, len(types)):
        print('[+] Type: {}, Count: {}, Percentage: {}%'.format(typestrs[t], typecount[t], round(100.0 * typecount[t] / tallcount, 2)))
    print('\n')


list_spawns = set([])
list_emptylocs = set([])
list_gyms = set([])
list_stops = set([])

for file in os.listdir(workdir):
    if file.endswith(".json"):
        path = workdir + '/' + file

        f = open(path, 'r')
        scandata = json.load(f)
        f.close()

        if 'spawns' in scandata and 'parameters' in scandata:
            for s in scandata['spawns']:
                if s['phasetime'] == 45 or s['phasetime'] == 75:
                    s['phasetime'] = 60 # fixes entries caused by wrong rounding
                if s['pauses'] == 0 and s['pausetime'] > 1000:
                    s['pausetime'] /= 60000.0 # fixes entry for 1x60 spawns in one of the first iscan versions

            for s in scandata['spawns']: # reclassifies spawnpoints after fixes and in consideration of the new type
                if s['type'] == SPAWN_DEF:
                    if s['phasetime'] == 60:
                        if s['pauses'] == 0:
                            s['type'] = SPAWN_1x60
                        elif s['pauses'] == 1:
                            if s['pausetime'] == 45:
                                s['type'] = SPAWN_1x15
                            elif s['pausetime'] == 30:
                                s['type'] = SPAWN_1x30
                            elif s['pausetime'] == 15:
                                s['type'] = SPAWN_1x45
                            elif s['pausetime'] == 0:
                                s['type'] = SPAWN_1x60h3
                        elif s['pauses'] == 2:
                            if s['pausetime'] == 15:
                                s['type'] = SPAWN_1x45h2
            f = open(path, 'w')
            json.dump(scandata,f, indent=1, separators=(',', ': '))
            f.close()

            for entry in scandata['spawns']:
                if entry['id'] not in list_spawns:
                    alldata['spawns'].append(entry)
                    list_spawns.add(entry['id'])
            for entry in scandata['emptylocs']:
                if (entry['lat'] * 10, entry['lng']) not in list_emptylocs:
                    alldata['emptylocs'].append(entry)
                    list_emptylocs.add((entry['lat'], entry['lng']))
            for entry in scandata['gyms']:
                if entry['id'] not in list_gyms:
                    alldata['gyms'].append(entry)
                    list_gyms.add(entry['id'])
            for entry in scandata['stops']:
                if entry['id'] not in list_stops:
                    alldata['stops'].append(entry)
                    list_stops.add(entry['id'])

f = open(alldata_path, 'w')
json.dump(alldata,f, indent=1, separators=(',', ': '))
f.close()
spawnstats(alldata)