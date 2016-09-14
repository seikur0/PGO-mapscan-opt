import os
import json

workdir = os.path.dirname(os.path.realpath(__file__))

SPAWN_UNDEF = -1
SPAWN_DEF = 1
SPAWN_1x15 = 101
SPAWN_1x30 = 102
SPAWN_1x45 = 103
SPAWN_1x60 = 104
SPAWN_2x15 = 201
SPAWN_1x60h2 = 202
SPAWN_1x60h3 = 203
SPAWN_1x60h23 = 204

scandata = None

alldata= {'spawns': [],'emptylocs': [],'gyms': [],'stops': [],'parameters': []}

alldata_path = 'mapdata_rename_this.json'
alldata_readable_path = 'mapdata_readable_can delete.json'

types = [SPAWN_1x15, SPAWN_1x30, SPAWN_1x45, SPAWN_1x60, SPAWN_2x15, SPAWN_1x60h2, SPAWN_1x60h3, SPAWN_1x60h23, SPAWN_UNDEF]
typestrs = ['1x15', '1x30', '1x45', '1x60', '2x15', '1x60h2', '1x60h3', '1x60h23', 'UNDEF']

def spawnstats(scandata):
    typecount = [0, 0, 0, 0, 0, 0, 0, 0, 0]
    tallcount = len(scandata['spawns'])

    for spawn in scandata['spawns']:
        for t in range(0, len(types)):
            if spawn['type'] == types[t]:
                typecount[t] += 1
    print('[+] Spawn point count: {}'.format(tallcount))
    for t in range(0, len(types)):
        print('[+] Type: {}, Count: {}, Percentage: {}%'.format(typestrs[t], typecount[t], round(100.0 * typecount[t] / tallcount, 2)))
    print('\n')


list_spawns = []
list_emptylocs = set([])
list_gyms = set([])
list_stops = set([])

def fix1():
    global scandata
    for s in scandata['spawns']:
        if s.get('phasetime',None) is not None:
            if s['phasetime'] == 45 or s['phasetime'] == 75:
                s['phasetime'] = 60  # fixes entries caused by wrong rounding
            if s['pauses'] == 0 and s['pausetime'] > 1000:
                s['pausetime'] /= 60000.0  # fixes entry for 1x60 spawns in one of the first iscan versions
            if s['type'] == SPAWN_1x60h2:
                s['pausetime'] = 15

def fix2():
    global scandata
    for s in scandata['spawns']:  # reclassifies spawnpoints after fixes and in consideration of the new type
        if s.get('phasetime',None) is not None and s['type'] == SPAWN_DEF:
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
                        s['type'] = SPAWN_1x60h2
                        s['pausetime'] = 15
                elif s['pauses'] == 2:
                    if s['pausetime'] == 15:
                        s['type'] = SPAWN_2x15

def fix3():
    global scandata
    for s in scandata['spawns']:
        if s.get('phasetime',None) is not None and s['phasetime'] == 60:
            s['pausetime'] *= 60000
            s['spawntime'] = int(round(s['spawntime'] * 60000))
            s.pop('phasetime',None)
            s.pop('pauses',None)

def main():
    global scandata
    foundfile = False
    for file in os.listdir(workdir):
        if file.endswith(".json") and not file == alldata_readable_path and not file == alldata_path:
            foundfile = True
            path = workdir + '/' + file

            f = open(path, 'r')
            scandata = json.load(f)
            f.close()

            if 'spawns' in scandata and 'parameters' in scandata:
                fix1()
                fix2()
                fix3()

                f = open(path, 'w')
                json.dump(scandata,f, indent=1, separators=(',', ': '))
                f.close()

                for entry in scandata['spawns']:
                    if entry['id'] in list_spawns:
                        ind = list_spawns.index(entry['id'])
                        if alldata['spawns'][ind]['type'] in (SPAWN_UNDEF,SPAWN_DEF):
                            alldata['spawns'][ind] = entry
                    else:
                        alldata['spawns'].append(entry)
                        list_spawns.append(entry['id'])

                for entry in scandata['emptylocs']:
                    if (entry['lat'], entry['lng']) not in list_emptylocs:
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
    if foundfile:
        f = open(workdir + '/' + alldata_path, 'w')
        json.dump(alldata,f, indent=1, separators=(',', ': '))
        f.close()
        spawnstats(alldata)

        for entry in alldata['spawns']:
            entry['spawn_minute'] = round(entry['spawntime'] / 60000.0,2)
            entry['location'] = '{},{}'.format(round(entry['lat'],5),round(entry['lng'],5))
            entry['type'] = typestrs[types.index(entry['type'])]

            entry.pop('spawntime')
            entry.pop('pausetime')
            entry.pop('lat')
            entry.pop('lng')
        alldata.pop('emptylocs')
        alldata.pop('gyms')
        alldata.pop('parameters')
        alldata.pop('stops')

        f = open(workdir + '/' + alldata_readable_path, 'w')
        json.dump(alldata, f, indent=1, separators=(',', ': '), sort_keys=True)
        f.close()
    else:
        print('Spawnfix couldn\'t find any learning files. Put the files that you wish to fix and join into the same folder as "spawnfix.py".')


if __name__=="__main__":
    main()