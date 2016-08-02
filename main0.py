import requests
import re
import json
import argparse

import POGOProtos
import POGOProtos.Networking
import POGOProtos.Networking.Envelopes_pb2
import POGOProtos.Networking.Responses_pb2
import POGOProtos.Networking.Requests
import POGOProtos.Networking.Requests.Messages_pb2

import time
from datetime import datetime
import sys
import math
import os

from pushbullet import Pushbullet
from geopy.geocoders import Nominatim
from s2sphere import CellId, LatLng
from gpsoauth import perform_master_login, perform_oauth
from shutil import move

import threading
import Queue


def getNeighbors(location):
    level = 15
    origin = CellId.from_lat_lng(LatLng.from_degrees(location[0], location[1])).parent(level)

    max_size = 1 << 30
    size = origin.get_size_ij(level)

    face, i, j = origin.to_face_ij_orientation()[0:3]

    walk = [origin.id(),
            origin.from_face_ij_same(face, i, j - size, j - size >= 0).parent(level).id(),
            origin.from_face_ij_same(face, i, j + size, j + size < max_size).parent(level).id(),
            origin.from_face_ij_same(face, i - size, j, i - size >= 0).parent(level).id(),
            origin.from_face_ij_same(face, i + size, j, i + size < max_size).parent(level).id(),
            origin.from_face_ij_same(face, i - size, j - size, j - size >= 0 and i - size >= 0).parent(level).id(),
            origin.from_face_ij_same(face, i + size, j - size, j - size >= 0 and i + size < max_size).parent(level).id(),
            origin.from_face_ij_same(face, i - size, j + size, j + size < max_size and i - size >= 0).parent(level).id(),
            origin.from_face_ij_same(face, i + size, j + size, j + size < max_size and i + size < max_size).parent(level).id()]
            #origin.from_face_ij_same(face, i, j - 2*size, j - 2*size >= 0).parent(level).id(),
            #origin.from_face_ij_same(face, i - size, j - 2*size, j - 2*size >= 0 and i - size >=0).parent(level).id(),
            #origin.from_face_ij_same(face, i + size, j - 2*size, j - 2*size >= 0 and i + size < max_size).parent(level).id(),
            #origin.from_face_ij_same(face, i, j + 2*size, j + 2*size < max_size).parent(level).id(),
            #origin.from_face_ij_same(face, i - size, j + 2*size, j + 2*size < max_size and i - size >=0).parent(level).id(),
            #origin.from_face_ij_same(face, i + size, j + 2*size, j + 2*size < max_size and i + size < max_size).parent(level).id(),
            #origin.from_face_ij_same(face, i + 2*size, j, i + 2*size < max_size).parent(level).id(),
            #origin.from_face_ij_same(face, i + 2*size, j - size, j - size >= 0 and i + 2*size < max_size).parent(level).id(),
            #origin.from_face_ij_same(face, i + 2*size, j + size, j + size < max_size and i + 2*size < max_size).parent(level).id(),
            #origin.from_face_ij_same(face, i - 2*size, j, i - 2*size >= 0).parent(level).id(),
            #origin.from_face_ij_same(face, i - 2*size, j - size, j - size >= 0 and i - 2*size >=0).parent(level).id(),
            #origin.from_face_ij_same(face, i - 2*size, j + size, j + size < max_size and i - 2*size >=0).parent(level).id()]
    return walk


API_URL = 'https://pgorelease.nianticlabs.com/plfe/rpc'

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

NET_MAXWAIT = 30
LOGIN_MAXWAIT = 30
MAXWAIT = LOGIN_MAXWAIT

EARTH_Rmax = 6378137.0
EARTH_Rmin = 6356752.3
HEX_R = 70.0

safety = 0.999

LOGGING = False
DATA = []
pb = None
PUSHPOKS = None
geolocator = Nominatim()

F_LIMIT = None
LANGUAGE = None
HEX_NUM = None
wID = None
interval = None
workdir = os.path.dirname(os.path.realpath(__file__))

LAT_C, LNG_C, ALT_C = [None, None, None]

SETTINGS_FILE = '{}/res/usersettings.json'.format(workdir)

time_hb = 3.8
time_small = 1
tries = 5
percinterval = 2
curR = None
maxR = None
firstrun = True
all_ll = None

def do_settings():
    global LANGUAGE
    global LAT_C, LNG_C, ALT_C
    global HEX_NUM
    global interval
    global F_LIMIT
    global pb
    global PUSHPOKS

    global wID

    parser = argparse.ArgumentParser()
    parser.add_argument('-id', '--id', help='group id')
    parser.add_argument('-r', '--range', help='scan range')
    parser.add_argument('-t', '--timeinterval', help='time interval')
    parser.add_argument('-lat', '--latitude', help='latitude')
    parser.add_argument('-lng', '--longitude', help='longitude')
    parser.add_argument('-alt', '--altitude', help='altitude')
    parser.add_argument('-loc', '--location', help='location')
    args = parser.parse_args()
    wID = args.id
    HEX_NUM = args.range
    interval = args.timeinterval

    ALT_C = args.altitude
    LAT_C = args.latitude
    LNG_C = args.longitude
    if args.location is not None:
        url = 'https://maps.googleapis.com/maps/api/geocode/json'
        params = {'sensor': 'false', 'address': args.location}
        r = requests.get(url, params=params)
        if r.status_code == 200:
            spot = r.json()['results'][0]['geometry']['location']
            LAT_C, LNG_C = [spot['lat'], spot['lng']]
        else:
            print('[-] Error: The coordinates for the specified location couldn\'t be retrieved, http code: {}'.format(r.status_code))
            print('[-] The location parameter will be ignored.')

    if wID is None:
        wID = 0
    else:
        wID = int(wID)

    try:
        f = open(SETTINGS_FILE, 'r')
        try:
            allsettings = json.load(f)
        except ValueError as e:
            print('[-] Error: The settings file is not in a valid format, {}'.format(e))
            f.close()
            sys.exit()
        f.close()
    finally:
        if f is not None and not f.closed:
            f.close()

    F_LIMIT = int(allsettings['backup_size'] * 1024 * 1024)
    if F_LIMIT == 0:
        F_LIMIT = 9223372036854775807

    if allsettings['pushbullet']['enabled'] is True:
        pb = []
        keys = allsettings['pushbullet']['api_key']
        for a in range (len(keys)):
            try:
                this_pb = Pushbullet(keys[a])
                pb.append(this_pb)
            except Exception as e:
                print('[-] Pushbullet error, key {} is invalid, {}'.format(a+1, e))
                print('[-] This pushbullet will be disabled.')

        if len(pb) > 0:
            PUSHPOKS = set(allsettings['pushbullet']['push_ids'])
        else:
            pb = None

    LANGUAGE = allsettings['language']

    if HEX_NUM is None:
        HEX_NUM = allsettings['range']
    else:
        HEX_NUM = int(HEX_NUM)
    if interval is None:
        interval = allsettings['scaninterval']
    else:
        interval = int(interval)

    #////////////////////////
    idlist = []
    for i in range(0, len(allsettings['profiles'])):
        if allsettings['profiles'][i]['id']==wID:
            idlist.append(i)

    accounts = []
    if len(idlist) > 0:
        for i in range(0,len(idlist)):
            account = {'num': i, 'type': allsettings['profiles'][idlist[i]]['type'], 'user': allsettings['profiles'][idlist[i]]['username'], 'pw': allsettings['profiles'][idlist[i]]['password']}
            accounts.append(account)
    else:
        print('[-] Error: No profile exists for the set id.')
        sys.exit()

    if LAT_C is None:
        LAT_C = allsettings['profiles'][idlist[0]]['coordinates']['lat']
    else:
        LAT_C = float(LAT_C)
    if LNG_C is None:
        LNG_C = allsettings['profiles'][idlist[0]]['coordinates']['lng']
    else:
        LNG_C = float(LNG_C)
    if ALT_C is None:
        ALT_C = allsettings['profiles'][idlist[0]]['coordinates']['alt']
    else:
        ALT_C = float(ALT_C)

    return accounts


def getEarthRadius(latrad):
    return (1.0 / (((math.cos(latrad)) / EARTH_Rmax) ** 2 + ((math.sin(latrad)) / EARTH_Rmin) ** 2)) ** (1.0 / 2)


def login_google(account):

    ANDROID_ID = '9774d56d682e549c'
    SERVICE = 'audience:server:client_id:848232511240-7so421jotr2609rmqakceuu1luuq0ptb.apps.googleusercontent.com'
    APP = 'com.nianticlabs.pokemongo'
    APP_SIG = '321187995bc7cdc2b5fc91b11a96e2baa8602c62'

    while True:
        try:
            retry_after = 1
            login1 = perform_master_login(account['user'], account['pw'], ANDROID_ID)
            while login1.get('Token') is None:
                print('[-] Google Login error, retrying in {} seconds (step 1)'.format(retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                login1 = perform_master_login(account['user'], account['pw'], ANDROID_ID)

            retry_after = 1
            login2 = perform_oauth(account['user'], login1.get('Token'), ANDROID_ID, SERVICE, APP, APP_SIG)
            while login2.get('Auth') is None:
                print('[-] Google Login error, retrying in {} seconds (step 2)'.format(retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                login2 = perform_oauth(account['user'], login1.get('Token', ''), ANDROID_ID, SERVICE, APP, APP_SIG)

            access_token = login2['Auth']
            account['access_token'] = access_token
            return
        except Exception as e:
            print('[-] Unexpected google login error: {}'.format(e))
            print('[-] Retrying...')
            time.sleep(2)


def login_ptc(account):
    session = account['session']

    LOGIN_URL = 'https://sso.pokemon.com/sso/login?service=https%3A%2F%2Fsso.pokemon.com%2Fsso%2Foauth2.0%2FcallbackAuthorize'
    LOGIN_OAUTH = 'https://sso.pokemon.com/sso/oauth2.0/accessToken'

    while True:
        try:
            # session.headers.update({'User-Agent': 'Niantic App'})
            session.headers.update({'User-Agent': 'niantic'})
            r = session.get(LOGIN_URL)
            retry_after = 1
            while r.status_code != 200:
                print('[-] Connection error {}, retrying in {} seconds (step 1)'.format(r.status_code, retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                r = session.get(LOGIN_URL)

            jdata = json.loads(r.content)
            data = {
                'lt': jdata['lt'],
                'execution': jdata['execution'],
                '_eventId': 'submit',
                'username': account['user'],
                'password': account['pw'],
            }
            r = session.post(LOGIN_URL, data=data)
            retry_after = 1

            while r.status_code != 500 and r.status_code != 200:
                print('[-] Connection error {}, retrying in {} seconds (step 2)'.format(r.status_code, retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                r = session.post(LOGIN_URL, data=data)

            ticket = re.sub('.*ticket=', '', r.history[0].headers['Location'])
            data1 = {
                'client_id': 'mobile-app_pokemon-go',
                'redirect_uri': 'https://www.nianticlabs.com/pokemongo/error',
                'client_secret': 'w8ScCUXJQc6kXKw8FiOhd8Fixzht18Dq3PEVkUCP5ZPxtgyWsbTvWHFLm2wNY0JR',
                'grant_type': 'refresh_token',
                'code': ticket,
            }
            r = session.post(LOGIN_OAUTH, data=data1)
            while r.status_code != 200:
                print('[-] Connection error {}, retrying in {} seconds (step 3)'.format(r.status_code, retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                r = session.post(LOGIN_OAUTH, data=data1)

            access_token = re.sub('&expires.*', '', r.content)
            access_token = re.sub('.*access_token=', '', access_token)
            account['access_token'] = access_token
            account['session'] = session
            return

        except Exception as e:
            print('[-] Unexpected ptc login error: {}'.format(e))
            if r is not None:
                print('[-] Connection error, http code: {}'.format(r.status_code))
            else:
                print('[-] Error happened before network request.')
            print('[-] Retrying...')
            time.sleep(2)

def do_login(account):
    if account.get('session') is None:
        session = requests.session()
        session.verify = False
        account['session'] = session

    if account['type'] == 'ptc':
        print('[{}] Login for ptc account: {}'.format(account['num'], account['user']))
        login_ptc(account)
    elif account['type'] == 'google':
        print('[{}] Login for google account: {}'.format(account['num'], account['user']))
        login_google(account)
    else:
        print('[{}] Error: Login type should be either ptc or google.'.format(account['num']))
        sys.exit()


def api_req(location, account, api_endpoint, access_token, *mehs, **kw):
    session = account['session']
    r = None
    while True:
        try:
            p_req = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope()
            p_req.request_id = 1469378659230941192# anything works here as well 1469378659230941192

            p_req.status_code = POGOProtos.Networking.Envelopes_pb2.GET_PLAYER

            p_req.latitude, p_req.longitude, p_req.altitude = (location[0], location[1], location[2])

            p_req.unknown12 = 989  # transaction id, anything works
            if 'useauth' not in kw or not kw['useauth']:
                p_req.auth_info.provider = account['type']
                p_req.auth_info.token.contents = access_token
                p_req.auth_info.token.unknown2 = 14
            else:
                p_req.auth_ticket.start = kw['useauth'].start
                p_req.auth_ticket.expire_timestamp_ms = kw['useauth'].expire_timestamp_ms
                p_req.auth_ticket.end = kw['useauth'].end

            for meh in mehs:
                p_req.MergeFrom(meh)
            protobuf = p_req.SerializeToString()

            r = session.post(api_endpoint, data=protobuf, verify=False)
            retry_after = 1
            while r.status_code != 200:
                if r.status_code == 403:
                    print('[-] Access denied, your IP is blocked by the N-company.')
                    sys.exit()
                print('[-] Connection error {}, retrying in {} seconds'.format(r.status_code, retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                r = session.post(api_endpoint, data=protobuf, verify=False)

            p_ret = POGOProtos.Networking.Envelopes_pb2.ResponseEnvelope()
            p_ret.ParseFromString(r.content)
            return p_ret

        except Exception, e:
            print('[-] Uncaught connection error, error: {}'.format(e))
            if r is not None:
                print('[-] Uncaught connection error, http code: {}'.format(r.status_code))
            else:
                print('[-] Error happened before network request.')
            print('[-] Retrying...')
            time.sleep(2)


def get_profile(location, account, api, useauth, *reqq):
    req = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope()

    req1 = req.requests.add()
    req1.request_type = POGOProtos.Networking.Envelopes_pb2.GET_PLAYER
    if len(reqq) >= 1:
        req1.MergeFrom(reqq[0])

    req2 = req.requests.add()
    req2.request_type = POGOProtos.Networking.Envelopes_pb2.GET_HATCHED_EGGS
    if len(reqq) >= 2:
        req2.MergeFrom(reqq[1])

    req3 = req.requests.add()
    req3.request_type = POGOProtos.Networking.Envelopes_pb2.GET_INVENTORY
    if len(reqq) >= 3:
        req3.MergeFrom(reqq[2])

    req4 = req.requests.add()
    req4.request_type = POGOProtos.Networking.Envelopes_pb2.CHECK_AWARDED_BADGES
    if len(reqq) >= 4:
        req4.MergeFrom(reqq[3])

    req5 = req.requests.add()
    req5.request_type = POGOProtos.Networking.Envelopes_pb2.DOWNLOAD_SETTINGS
    if len(reqq) >= 5:
        req5.MergeFrom(reqq[4])

    newResponse = api_req(location, account, api, account['access_token'], req, useauth=useauth)

    retry_after = 1
    while newResponse.status_code not in [1, 2, 53, 102]:  # 1 for hearbeat, 2 for profile authorization, 53 for api endpoint, 52 for error, 102 session token invalid
        print('[-] Response error, status code: {}, retrying in {} seconds'.format(newResponse.status_code,retry_after))
        time.sleep(retry_after)
        retry_after = min(retry_after * 2, MAXWAIT)
        newResponse = api_req(location, account, api, account['access_token'], req, useauth=useauth)
    return newResponse


def set_api_endpoint(location, account):
    p_ret = get_profile(location, account, API_URL, None)
    while p_ret.status_code == 102:
        print('[-] Error, invalid session, retrying...')
        time.sleep(2)
        p_ret = get_profile(location, account, API_URL, None)

    account['api_endpoint'] = ('https://%s/rpc' % p_ret.api_url)


def authorize_profile(location, account):
    while True:
        response = get_profile(location, account, account['api_endpoint'], None)
        if response.status_code == 1 or response.status_code == 2:
            account['response'] = response
            return
        elif response.status_code == 102:
            print('[-] Session token isn\'t valid yet, retrying...')
            time.sleep(5)
            #set_api_endpoint(location, account)
        else:
            print('[-] Authorization eror, status code: {}'.format( response.status_code))  # should not happen, probably unused
            print('[-] Retrying...')
            time.sleep(2)


def heartbeat(location, account):
    while True:
        m1 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
        m1.request_type = POGOProtos.Networking.Envelopes_pb2.GET_MAP_OBJECTS
        m11 = POGOProtos.Networking.Requests.Messages_pb2.GetMapObjectsMessage()

        walk = getNeighbors(location)
        m11.cell_id.extend(walk)

        m11.since_timestamp_ms.extend([0] * len(walk))
        m11.latitude = location[0]
        m11.longitude = location[1]
        m1.request_message = m11.SerializeToString()
        newResponse = get_profile(location, account, account['api_endpoint'], account['response'].auth_ticket, m1)
        if newResponse.status_code == 1:
            heartbeat = POGOProtos.Networking.Responses_pb2.GetMapObjectsResponse()
            heartbeat.ParseFromString(newResponse.returns[0])
            for cell in heartbeat.map_cells: # tests if an empty heartbeat was returned
                for testit in cell.spawn_points:
                    return heartbeat
            return None
        elif newResponse.status_code == 2:
            authorize_profile(location, account)
        elif newResponse.status_code == 102:
            print('[-] Error, refreshing login')
            do_login(account)
            set_api_endpoint(location, account)
            authorize_profile(location, account)
        else:
            print('[-] Heartbeat error, status code: {}'.format( newResponse.status_code))  # should not happen, probably unused
            print('[-] Retrying...')
            time.sleep(2)


def prune_data():
    # prune despawned pokemon
    cur_time = int(time.time())
    for i, poke in reversed(list(enumerate(DATA))):
        if cur_time > poke[4]:
            DATA.pop(i)

def load_data(data_file):
    try:
        f = open(data_file, 'r')
        DATA.extend(json.load(f))
        prune_data()
        f.close()
    except IOError as e:
        pass
    finally:
        if 'f' in vars() and not f.closed:
            f.close()

def write_data(data_file):
    try:
        f = open(data_file, 'w')
        json.dump(DATA, f, separators=(',', ':'))
        f.close()
    finally:
        if 'f' in vars() and not f.closed:
            f.close()

##################################################################################################################################################
##################################################################################################################################################
def main():
    class locgiver(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
        def run(self):
            global curR
            global maxR
            global firstrun
            firstrun = True
            maxR=len(all_ll)

            print('')
            print('[+] Distributing {} locations to {} threads.'.format(len(all_ll), threadnum))

            while True:
                print('')
                print('[+] Time: {}'.format(datetime.now().strftime('%H:%M:%S')))
                curR = 0
                nextperc = percinterval
                curT = int(time.time())

                for this_ll in all_ll:
                    addlocation.put(this_ll)
                    if (100.0 * curR / maxR) >= nextperc:
                        perc = math.floor((100.0 * curR / maxR) / percinterval) * percinterval
                        print('[+] Finished: {} %'.format(perc))
                        nextperc = perc + percinterval

                addlocation.join()
                if firstrun:
                    a = 0
                    while a < len(all_ll):
                        if all_ll[a] is None:
                            all_ll.remove(all_ll[a])
                        else:
                            a +=1
                    print('[+] {}/{} non-empty locations in scan range remaining.'.format(len(all_ll), maxR))
                    maxR = len(all_ll)
                    firstrun = False

                addpokemon.join()
                print('[+] Finished: 100 %')

                list_unique.intersection_update(list_seen)
                list_seen.clear()

                curT = int(time.time()) - curT
                print('[+] Scan Time: {} s'.format(curT))
                curT = max(interval - curT, 0)
                print('[+] Sleeping for {} seconds...'.format(curT))
                time.sleep(curT)
                prune_data()

#########################################################################
#########################################################################
    class collector(threading.Thread):
        def __init__(self, name, account):
            threading.Thread.__init__(self)
            self.account = account

        def run(self):
            global curR
            do_login(self.account)
            print('[{}] RPC Session Token: {}'.format(self.account['num'], self.account['access_token']))
            location = origin.lat().degrees, origin.lng().degrees, ALT_C
            set_api_endpoint(location, self.account)
            print('[{}] API endpoint: {}'.format(self.account['num'], self.account['api_endpoint']))
            authorize_profile(location, self.account)
            print('[{}] Login successful'.format(self.account['num']))

            settings = POGOProtos.Networking.Responses_pb2.DownloadSettingsResponse()
            settings.ParseFromString(self.account['response'].returns[4])

            profile = POGOProtos.Networking.Responses_pb2.GetPlayerResponse()
            profile.ParseFromString(self.account['response'].returns[0])

            print('[{}] Username: {}'.format(self.account['num'], profile.player_data.username))
            # /////////////////
            synch_li.get()
            synch_li.task_done()

            # ////////////////////
            while True:
                this_ll = addlocation.get()
                location = this_ll.lat().degrees, this_ll.lng().degrees, ALT_C
                h = heartbeat(location, self.account)
                count = 1
                while h is None and count <= tries:
                    if firstrun:
                        # print('[-] Empty heartbeat, retrying... (try {}/{})'.format(count,tries))
                        count += 1
                    time.sleep(time_small)
                    h = heartbeat(location, self.account)
                time.sleep(time_hb)
                if h is None:
                    print('[+] Empty location removed. lat/lng: {}, {}'.format(this_ll.lat().degrees, this_ll.lng().degrees))
                    all_ll[all_ll.index(this_ll)] = None
                else:
                    for cell in h.map_cells:
                        for wild in cell.wild_pokemons:
                            addpokemon.put(wild)
                curR += 1
                addlocation.task_done()

#########################################################################
#########################################################################
    class joiner(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
        def run(self):
            data_file = '{}/res/data{}.json'.format(workdir, wID)
            stat_file = '{}/res/spawns{}.txt'.format(workdir, wID)
            POKEMONS = json.load(open('{}/res/{}.json'.format(workdir, LANGUAGE)))
            statheader = 'Name\tid\tSpawnID\tlat\tlng\tspawnTime\tTime\tTime2Hidden\tencounterID\n'

            interval_datwrite=5
            nextdatwrite=time.time() + interval_datwrite
            load_data(data_file)
            try:
                f = open(stat_file, 'a', 0)
                f.seek(0, 2)
                if f.tell() == 0:
                    f.write(statheader)
                while True:
                    wild = addpokemon.get()

                    if wild.encounter_id not in list_seen:
                        list_seen.add(wild.encounter_id)
                        if wild.encounter_id not in list_unique:

                            spawnIDint = int(wild.spawn_point_id, 16)
                            org_tth = wild.time_till_hidden_ms
                            if wild.time_till_hidden_ms < 0:
                                wild.time_till_hidden_ms = 900001
                            else:
                                list_unique.add(wild.encounter_id)
                            f.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(POKEMONS[wild.pokemon_data.pokemon_id], wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, (wild.last_modified_timestamp_ms + wild.time_till_hidden_ms) / 1000.0 - 900.0, wild.last_modified_timestamp_ms / 1000.0, org_tth / 1000.0, wild.encounter_id))
                            DATA.append([wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, int((wild.last_modified_timestamp_ms + wild.time_till_hidden_ms) / 1000.0)])
                            other = LatLng.from_degrees(wild.latitude, wild.longitude)
                            diff = other - origin
                            difflat = diff.lat().degrees
                            difflng = diff.lng().degrees
                            direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '') + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')
                            print('[+] ({}) {} visible for {} seconds ({}m {} from you)'.format(wild.pokemon_data.pokemon_id, POKEMONS[wild.pokemon_data.pokemon_id], int(wild.time_till_hidden_ms / 1000.0), int(origin.get_distance(other).radians * 6366468.241830914), direction))

                            if pb is not None:
                                if wild.pokemon_data.pokemon_id in PUSHPOKS:
                                    try:
                                        location = geolocator.reverse('{},{}'.format(wild.latitude, wild.longitude))
                                        notification_text = POKEMONS[wild.pokemon_data.pokemon_id] + " @ " + location.address
                                    except:
                                        notification_text = POKEMONS[wild.pokemon_data.pokemon_id] + " found!"
                                    disappear_time = str(datetime.fromtimestamp(int((wild.last_modified_timestamp_ms + wild.time_till_hidden_ms) / 1000.0)).strftime("%H:%M"))
                                    location_text = "disappears at: " + disappear_time
                                    for pushacc in pb:
                                        pushacc.push_link(notification_text, 'http://www.google.com/maps/place/{},{}'.format(wild.latitude, wild.longitude), body=location_text)

                            if addpokemon.empty() and time.time() < nextdatwrite:
                                time.sleep(1)
                            if addpokemon.empty() or time.time() >= nextdatwrite:
                                prune_data()
                                write_data(data_file)
                                if f.tell() > F_LIMIT:
                                    print('[+] File size is over the set limit, doing backup.')
                                    f.close()
                                    move(stat_file, stat_file[:-4] + '.' + time.strftime('%Y%m%d_%H%M') + '.txt')
                                    f = open(stat_file, 'a', 0)
                                    f.write(statheader)

                                nextdatwrite=time.time() + interval_datwrite
                    addpokemon.task_done()
            finally:
                if 'f' in vars() and not f.closed:
                    f.close()
#########################################################################
#########################################################################
    global all_ll
    accounts = do_settings()

    origin = LatLng.from_degrees(LAT_C, LNG_C)
    all_ll = [origin]

    latrad = origin.lat().radians
    HEX_M = 3.0 ** 0.5 / 2.0 * HEX_R

    x_un = 1.5 * HEX_R / getEarthRadius(latrad) / math.cos(latrad) * safety * 180 / math.pi
    y_un = 1.0 * HEX_M / getEarthRadius(latrad) * safety * 180 / math.pi

    for a in range(1, HEX_NUM + 1):
        for s in range(0,6):
            for i in range(0, a):
                if s==0:
                    lat = LAT_C + y_un * (-2 * a + i)
                    lng = LNG_C + x_un * i
                elif s==1:
                    lat = LAT_C + y_un * (-a + 2 * i)
                    lng = LNG_C + x_un * a
                elif s==2:
                    lat = LAT_C + y_un * (a + i)
                    lng = LNG_C + x_un * (a - i)
                elif s==3:
                    lat = LAT_C - y_un * (-2 * a + i)
                    lng = LNG_C - x_un * i
                elif s==4:
                    lat = LAT_C - y_un * (-a + 2 * i)
                    lng = LNG_C - x_un * a
                else:  # if s==5:
                    lat = LAT_C - y_un * (a + i)
                    lng = LNG_C - x_un * (a - i)

                all_ll.append(LatLng.from_degrees(lat, lng))

    list_seen = set([])
    list_unique = set([])

    threadnum = len(accounts)

    threadList = []
    addpokemon = Queue.Queue(threadnum * 3)
    synch_li = Queue.Queue(threadnum)
    addlocation = Queue.Queue(threadnum * 2)

    newthread = joiner()
    newthread.daemon = True
    newthread.start()

    for i in range(0,threadnum):
        newthread = collector(i, accounts[i])
        newthread.daemon = True
        newthread.start()
        synch_li.put(True)
        threadList.append(newthread)
        synch_li.join()

    newthread = locgiver()
    newthread.daemon = True
    newthread.start()

    for t in threadList:
        t.join()

if __name__ == '__main__':
    main()
