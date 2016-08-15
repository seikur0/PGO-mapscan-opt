import requests
import re
import json
import argparse

import POGOProtos
import POGOProtos.Enums_pb2
import POGOProtos.Networking
import POGOProtos.Networking.Envelopes_pb2
import POGOProtos.Networking.Responses_pb2
import POGOProtos.Networking.Requests
import POGOProtos.Networking.Requests.Messages_pb2
import POGOProtos.Map
import POGOProtos.Map.Pokemon_pb2
import POGOProtos.Data_pb2

import time
from datetime import datetime
import sys
import math
import os
import random

from pushbullet import Pushbullet
from geopy.geocoders import Nominatim
from s2sphere import CellId, LatLng
from gpsoauth import perform_master_login, perform_oauth
from shutil import move
from operator import itemgetter

from res.uk6 import generateLocation1, generateLocation2, generateRequestHash, generate_signature
import ctypes

import threading
import Queue

import pokesite


def get_time():
    return int(round(time.time() * 1000))

def get_time_wrap():
    return int(round(time.time() * 1000)) % 3600000


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
            # origin.from_face_ij_same(face, i, j - 2*size, j - 2*size >= 0).parent(level).id(),
            # origin.from_face_ij_same(face, i - size, j - 2*size, j - 2*size >= 0 and i - size >=0).parent(level).id(),
            # origin.from_face_ij_same(face, i + size, j - 2*size, j - 2*size >= 0 and i + size < max_size).parent(level).id(),
            # origin.from_face_ij_same(face, i, j + 2*size, j + 2*size < max_size).parent(level).id(),
            # origin.from_face_ij_same(face, i - size, j + 2*size, j + 2*size < max_size and i - size >=0).parent(level).id(),
            # origin.from_face_ij_same(face, i + size, j + 2*size, j + 2*size < max_size and i + size < max_size).parent(level).id(),
            # origin.from_face_ij_same(face, i + 2*size, j, i + 2*size < max_size).parent(level).id(),
            # origin.from_face_ij_same(face, i + 2*size, j - size, j - size >= 0 and i + 2*size < max_size).parent(level).id(),
            # origin.from_face_ij_same(face, i + 2*size, j + size, j + size < max_size and i + 2*size < max_size).parent(level).id(),
            # origin.from_face_ij_same(face, i - 2*size, j, i - 2*size >= 0).parent(level).id(),
            # origin.from_face_ij_same(face, i - 2*size, j - size, j - size >= 0 and i - 2*size >=0).parent(level).id(),
            # origin.from_face_ij_same(face, i - 2*size, j + size, j + size < max_size and i - 2*size >=0).parent(level).id()]
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
exclude_ids = None
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
port = None

time_hb = 8
time_small = time_hb
tries = 1
percinterval = 2
curR = None
maxR = None
starttime = None
runs = 0
location_str = ''
spawnlyzetime = 0
countmax = 0
countall = 0
empty_thisrun = 0
all_loc = None
empty_loc = None
addlocation = None
synch_li = None

scannum = None
login_simu = False
acc_tos = False

signature_lib = None
locktime = None
lock_network = None
lock_banfile = None
smartscan = False
emptyremoved = False
silent = False
spawns = []

def do_settings():
    global LANGUAGE, LAT_C, LNG_C, ALT_C, HEX_NUM, interval, F_LIMIT, pb, PUSHPOKS, scannum, login_simu, port, wID, acc_tos, exclude_ids

    parser = argparse.ArgumentParser()
    parser.add_argument('-id', '--id', help='group id')
    parser.add_argument('-r', '--range', help='scan range')
    parser.add_argument('-t', '--timeinterval', help='time interval')
    parser.add_argument('-lat', '--latitude', help='latitude')
    parser.add_argument('-lng', '--longitude', help='longitude')
    parser.add_argument('-alt', '--altitude', help='altitude')
    parser.add_argument('-loc', '--location', help='location')
    parser.add_argument('-s', "--scannum", help="number of scans to run")
    parser.add_argument('-tos', "--tosaccept", help="let accounts accept tos at start", action="store_true")
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
            lprint('[-] Error: The coordinates for the specified location couldn\'t be retrieved, http code: {}'.format(r.status_code))
            lprint('[-] The location parameter will be ignored.')

    if args.tosaccept:
        acc_tos = True

    if wID is None:
        wID = 0
    else:
        wID = int(wID)

    try:
        f = open(SETTINGS_FILE, 'r')
        try:
            allsettings = json.load(f)
        except ValueError as e:
            lprint('[-] Error: The settings file is not in a valid format, {}'.format(e))
            f.close()
            sys.exit()
        f.close()
    finally:
        if 'f' in vars() and not f.closed:
            f.close()

    login_simu = allsettings['login_simu']

    F_LIMIT = int(allsettings['backup_size'] * 1024 * 1024)
    if F_LIMIT == 0:
        F_LIMIT = 9223372036854775807

    if args.scannum is None:
        scannum = 0
    else:
        scannum = int(args.scans)

    if allsettings['pushbullet']['enabled'] is True:
        pb = []
        keys = allsettings['pushbullet']['api_key']
        for a in range(len(keys)):
            try:
                this_pb = Pushbullet(keys[a])
                if allsettings['pushbullet']['use_channels'] is True:
                    for channel in this_pb.channels:
                        if channel.channel_tag in allsettings['pushbullet']['channel_tags']:
                            pb.append(channel)
                else:
                    pb.append(this_pb)
            except Exception as e:
                lprint('[-] Pushbullet error, key {} is invalid, {}'.format(a + 1, e))
                lprint('[-] This pushbullet will be disabled.')

        if len(pb) > 0:
            PUSHPOKS = set(allsettings['pushbullet']['push_ids'])
        else:
            pb = None

    LANGUAGE = allsettings['language']

    port = allsettings['port']

    exclude_ids = set(allsettings['exclude_ids'])

    if HEX_NUM is None:
        HEX_NUM = allsettings['range']
    else:
        HEX_NUM = int(HEX_NUM)
    if interval is None:
        interval = allsettings['scaninterval']
    else:
        interval = int(interval)

    # ////////////////////////
    idlist = []
    for i in range(0, len(allsettings['profiles'])):
        if allsettings['profiles'][i]['id'] == wID:
            idlist.append(i)

    accounts = []
    if len(idlist) > 0:
        for i in range(0, len(idlist)):
            account = {'num': i, 'type': allsettings['profiles'][idlist[i]]['type'], 'user': allsettings['profiles'][idlist[i]]['username'], 'pw': allsettings['profiles'][idlist[i]]['password']}
            accounts.append(account)
    else:
        lprint('[-] Error: No profile exists for the set id.')
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

    copykeys = 'language','api_key','icon_scalefactor','mobile_scalefactor','load_ids'
    websettings = dict()
    for key in copykeys:
        websettings[key] = allsettings[key]

    websettings['html_coords'] = allsettings['profiles'][idlist[0]]['coordinates']
    try:
        f = open('{}/webres/websettings.json'.format(workdir), 'w')
        json.dump(websettings, f, separators=(',', ':'))
        f.close()
    finally:
        if 'f' in vars() and not f.closed:
            f.close()

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
                lprint('[-] Google Login error, retrying in {} seconds (step 1)'.format(retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                login1 = perform_master_login(account['user'], account['pw'], ANDROID_ID)

            retry_after = 1
            login2 = perform_oauth(account['user'], login1.get('Token'), ANDROID_ID, SERVICE, APP, APP_SIG)
            while login2.get('Auth') is None:
                lprint('[-] Google Login error, retrying in {} seconds (step 2)'.format(retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                login2 = perform_oauth(account['user'], login1.get('Token', ''), ANDROID_ID, SERVICE, APP, APP_SIG)

            access_token = login2['Auth']
            account['access_expire_timestamp'] = int(login2['Expiry'])*1000
            account['access_token'] = access_token
            session = requests.session()
            session.verify = True
            session.headers.update({'User-Agent': 'Niantic App'}) #session.headers.update({'User-Agent': 'niantic'})
            account['session'] = session
            return
        except Exception as e:
            lprint('[-] Unexpected google login error: {}'.format(e))
            lprint('[-] Retrying...')
            time.sleep(1)


def login_ptc(account):
    LOGIN_URL = 'https://sso.pokemon.com/sso/login?service=https%3A%2F%2Fsso.pokemon.com%2Fsso%2Foauth2.0%2FcallbackAuthorize'
    LOGIN_OAUTH = 'https://sso.pokemon.com/sso/oauth2.0/accessToken'
    pattern = re.compile("access_token=(?P<access_token>.+?)&expires=(?P<expire_in>[0-9]+)")
    r = None
    step = 0
    while True:
        try:
            session = requests.session()
            session.verify = True
            session.headers.update({'User-Agent': 'Niantic App'})  # session.headers.update({'User-Agent': 'niantic'})

            step = 0
            r = session.get(LOGIN_URL)
            step = 1
            jdata = json.loads(r.content)
            step = 2
            data = {
                'lt': jdata['lt'],
                'execution': jdata['execution'],
                '_eventId': 'submit',
                'username': account['user'],
                'password': account['pw'],
            }
            step = 3
            r = session.post(LOGIN_URL, data=data)
            step = 4

            ticket = re.sub('.*ticket=', '', r.history[0].headers['Location'])
            step = 5
            data1 = {
                'client_id': 'mobile-app_pokemon-go',
                'redirect_uri': 'https://www.nianticlabs.com/pokemongo/error',
                'client_secret': 'w8ScCUXJQc6kXKw8FiOhd8Fixzht18Dq3PEVkUCP5ZPxtgyWsbTvWHFLm2wNY0JR',
                'grant_type': 'refresh_token',
                'code': ticket,
            }
            r = session.post(LOGIN_OAUTH, data=data1)
            step = 6
            result = pattern.search(r.content)
            step = 7
            account['access_expire_timestamp'] = 7200000 + get_time() #account['access_expire_timestamp'] = int(result.groupdict()["expire_in"])*1000 + get_time()
            account['access_token'] = result.groupdict()["access_token"]
            account['session'] = session
            return

        except Exception as e:
            lprint('[-] Ptc login error in step {}: {}'.format(step, e))
            if r is not None:
                lprint('[-] Connection error, http code: {}'.format(r.status_code))
            else:
                lprint('[-] Error happened before network request.')
            lprint('[-] Retrying...')
            time.sleep(1)


def do_login(account):
    account['api_url'] = API_URL
    account['auth_ticket'] = None
    account['login_time'] = int(round(time.time() * 1000))
    account['session_hash'] = os.urandom(32)

    lock_network.acquire()
    time.sleep(locktime)
    lock_network.release()
    if account['type'] == 'ptc':
        login_ptc(account)
    elif account['type'] == 'google':
        login_google(account)
    else:
        lprint('[{}] Error: Login type should be either ptc or google.'.format(account['num']))
        sys.exit()


def api_req(location, account, api_endpoint, access_token, *reqs, **auth):
    session = account['session']
    r = None

    p_req = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope()
    p_req.request_id = get_time() * 1000000 + random.randint(1, 999999)

    p_req.status_code = POGOProtos.Networking.Envelopes_pb2.GET_PLAYER

    p_req.latitude, p_req.longitude, p_req.altitude = location

    for s_req in reqs:
        p_req.MergeFrom(s_req)

    p_req.unknown12 = 989  # transaction id, anything works

    if auth['useauth'] is None:
        p_req.auth_info.provider = account['type']
        p_req.auth_info.token.contents = access_token
        p_req.auth_info.token.unknown2 = 59
        ticket_serialized = p_req.auth_info.SerializeToString()
    else:
        p_req.auth_ticket.start = auth['useauth'].start
        p_req.auth_ticket.expire_timestamp_ms = auth['useauth'].expire_timestamp_ms
        p_req.auth_ticket.end = auth['useauth'].end
        ticket_serialized = p_req.auth_ticket.SerializeToString()

    sig = POGOProtos.Networking.Envelopes_pb2.Signature()
    sig.location_hash1 = generateLocation1(ticket_serialized, location[0], location[1], location[2])
    sig.location_hash2 = generateLocation2(location[0], location[1], location[2])

    for req in p_req.requests:
        req_hash = generateRequestHash(ticket_serialized, req.SerializeToString())
        sig.request_hash.append(req_hash)

    sig.session_hash = account['session_hash'] #os.urandom(32)
    sig.timestamp = get_time()
    sig.timestamp_since_start = get_time() - account['login_time']
    sig.unknown25 = -8537042734809897855

    signature_proto = sig.SerializeToString()
    u6 = p_req.unknown6
    u6.request_type = 6
    u6.unknown2.encrypted_signature = generate_signature(signature_proto, signature_lib)

    request_str = p_req.SerializeToString()

    loopcount = 0
    while True:
        try:
            lock_network.acquire()
            time.sleep(locktime)
            lock_network.release()

            r = session.post(api_endpoint, data=request_str)

            if r.status_code == 200:
                p_ret = POGOProtos.Networking.Envelopes_pb2.ResponseEnvelope()
                p_ret.ParseFromString(r.content)
                return p_ret
            elif r.status_code == 403:
                lprint('[-] Access denied, your IP is blocked by the N-company.')
                sys.exit()
            elif r.status_code == 502:
                lprint('[-] Servers busy, retrying...')
                time.sleep(2)
                loopcount += 1
                if loopcount > 4:
                    return None
            else:
                lprint('[-] Unexpected network error, http code: {}'.format(r.status_code))
                return None


        except requests.ConnectionError as e:
            if re.search('Connection aborted', str(e)) is None:
                lprint('[-] Unexpected connection error, error: {}'.format(e))
                if r is not None:
                    lprint('[-] Unexpected connection error, http code: {}'.format(r.status_code))
                else:
                    lprint('[-] Error happened before network request.')
                lprint('[-] Retrying...')
            time.sleep(1)
        except Exception as e:
            lprint('[-] Unexpected connection error, error: {}'.format(e))
            if r is not None:
                lprint('[-] Unexpected connection error, http code: {}'.format(r.status_code))
            else:
                lprint('[-] Error happened before network request.')
            lprint('[-] Retrying...')
            time.sleep(1)


def get_profile(rtype, location, account, *reqq):
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

    while True:  # 1 for hearbeat, 2 for profile authorization, 53 for api endpoint, 52 for error, 102 session token invalid
        time.sleep(time_hb)
        response = api_req(location, account, account['api_url'], account['access_token'], req, useauth=account['auth_ticket'])
        if response is None:
            time.sleep(1)
            lprint('[-] Response error, retrying...')
            do_login(account)
            set_api_endpoint(location, account)
        elif rtype == 1 and response.status_code in [1,2]:
            return response
        elif rtype == 53 or response.status_code == 53:
            if response.auth_ticket is not None and response.auth_ticket.expire_timestamp_ms > 0:
                account['auth_ticket'] = response.auth_ticket
            if response.api_url is not None and response.api_url:
                account['api_url'] = 'https://{}/rpc'.format(response.api_url)
            if account['auth_ticket'] is not None and account['api_url'] != API_URL:
                if rtype == 53:
                    return
                else:
                    lprint('[+] API endpoint changed.')
            else:
                time.sleep(1)
                lprint('[-] auth/token error, refreshing login...')
                do_login(account)
                set_api_endpoint(location, account)
        elif rtype == 0 and response.status_code in [1,2]:
            return
        elif response.status_code == 102:
            timenow = get_time()
            if timenow > account['access_expire_timestamp'] or timenow < account['auth_ticket'].expire_timestamp_ms:
                lprint('[+] Login refresh.')
                do_login(account)
            else:
                lprint('[+] Authorization refresh.')
            set_api_endpoint(location, account)
        elif response.status_code == 52:
            lprint('[-] Servers busy, retrying...')
        elif response.status_code == 3:
            if synch_li.empty():
                addlocation.put([location[0],location[1]])
                addlocation.task_done()
            else:
                synch_li.get()
                synch_li.task_done()
            lprint('Account {}: {} was banned. It\'ll be logged out.'.format(account['num']+1,account['user']))
            lock_banfile.acquire()
            try:
                f = open('{}/res/banned{}.txt'.format(workdir, wID), 'a')
                f.write('{}\n'.format(account['user']))
                f.close()
            finally:
                if 'f' in vars() and not f.closed:
                    f.close()
            lock_banfile.release()
            exit()
        else:
            lprint('[-] Response error, unexpected status code: {}, retrying...'.format(response.status_code))
        time.sleep(1)


def set_api_endpoint(location, account):
    account['auth_ticket'] = None
    get_profile(53, location, account)


def heartbeat(location, account):
    m1 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
    m1.request_type = POGOProtos.Networking.Envelopes_pb2.GET_MAP_OBJECTS
    m11 = POGOProtos.Networking.Requests.Messages_pb2.GetMapObjectsMessage()

    walk = getNeighbors(location)
    m11.cell_id.extend(walk)

    m11.since_timestamp_ms.extend([0] * len(walk))
    m11.latitude = location[0]
    m11.longitude = location[1]
    m1.request_message = m11.SerializeToString()

    response = get_profile(1, location, account, m1)
    heartbeat = POGOProtos.Networking.Responses_pb2.GetMapObjectsResponse()
    heartbeat.ParseFromString(response.returns[0])

    for cell in heartbeat.map_cells:  # tests if an empty heartbeat was returned
        if len(cell.ListFields()) > 2:
            return heartbeat
    return None


def accept_tos(location, account):
    m1 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
    m1.request_type = POGOProtos.Networking.Envelopes_pb2.MARK_TUTORIAL_COMPLETE
    m11 = POGOProtos.Networking.Requests.Messages_pb2.MarkTutorialCompleteMessage()

    m11.tutorials_completed.append(POGOProtos.Enums_pb2.LEGAL_SCREEN)
    m11.send_marketing_emails = False
    m11.send_push_notifications = False

    m1.request_message = m11.SerializeToString()
    get_profile(0, location, account, m1)


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
    except ValueError as e:
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


def lprint(message):
    sys.stdout.write(str(message) + '\n')


##################################################################################################################################################
##################################################################################################################################################
def main():
    SPAWN_UNDEF = -1
    SPAWN_DEF = 1
    SPAWN_1x0 = 100
    SPAWN_1x15 = 101
    SPAWN_1x30 = 102
    SPAWN_1x45 = 103
    SPAWN_1x60 = 104
    SPAWN_2x0 = 200
    SPAWN_2x15 = 201
    VSPAWN_2x15 = 2011

    class spawnpoint:
        def __init__(self, lat, lng, spawnid):
            self.type = SPAWN_UNDEF
            self.spawntime = -1
            self.phasetime = -1
            self.lat = lat
            self.lng = lng
            self.spawnid = spawnid
            self.prev_encid = -1
            self.prev_time = starttime
            self.phase = 0
            self.pauses = 0
            self.pausetime = 0

#########################################################################
#########################################################################
    class spawnjoiner(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            thistime = -1

            while thistime < spawnlyzetime:
                wild = addspawns.get()

                spawnIDint = int(wild.spawn_point_id, 16)
                if spawnIDint not in list_spawns:
                    list_spawns.append(spawnIDint)
                    spawns.append(spawnpoint(wild.latitude, wild.longitude, spawnIDint))
                    position = len(spawns) - 1
                else:
                    position = list_spawns.index(spawnIDint)
                thisspawn = spawns[position]

                if thisspawn.phasetime == -1:
                    thisspawn.phasetime = wild.last_modified_timestamp_ms

                if thisspawn.phase < 2 and wild.time_till_hidden_ms > 0:
                    thisspawn.spawntime = (((wild.last_modified_timestamp_ms + wild.time_till_hidden_ms) / 1000.0) / 60) % 15

                if thisspawn.phase == 0:
                    if thisspawn.prev_encid != -1 and thisspawn.prev_encid != wild.encounter_id:
                        thisspawn.phase = 1
                        thisspawn.phasetime = wild.last_modified_timestamp_ms
                        if wild.time_till_hidden_ms > 0:
                            thisspawn.prev_time = wild.last_modified_timestamp_ms + wild.time_till_hidden_ms - 1
                        else:
                            thisspawn.prev_time = wild.last_modified_timestamp_ms
                    thisspawn.prev_encid = wild.encounter_id

                elif thisspawn.phase == 1:
                    thisspawn.pausetime = int(math.floor((wild.last_modified_timestamp_ms - thisspawn.prev_time - 1) / 900000.0)) * 15
                    if thisspawn.pausetime > 0:
                        thisspawn.pauses += 1
                    if thisspawn.prev_encid != wild.encounter_id:
                        thisspawn.phase = 2
                        thisspawn.phasetime = int(round((wild.last_modified_timestamp_ms - thisspawn.phasetime) / 900000.0))*15
                        if thisspawn.spawntime != -1:
                            quarter = (((wild.last_modified_timestamp_ms / 1000.0 / 60) % 60) / 15) + 4
                            thisspawn.spawntime += math.floor(quarter)  * 15
                            if thisspawn.spawntime > 15 * quarter:
                                thisspawn.spawntime -= 15
                            thisspawn.spawntime %= 60
                        else:
                            thisspawn.spawntime = ((wild.last_modified_timestamp_ms / 1000.0 / 60) % 60)
                        if thisspawn.pauses == 0:
                            thisspawn.pausetime = wild.last_modified_timestamp_ms - thisspawn.prev_time
                        thisspawn.type = SPAWN_DEF
                    if wild.time_till_hidden_ms > 0:
                        thisspawn.prev_time = wild.last_modified_timestamp_ms + wild.time_till_hidden_ms - 1
                    else:
                        thisspawn.prev_time = wild.last_modified_timestamp_ms
                thistime = time.time()
                addspawns.task_done()
#########################################################################
#########################################################################
    class smartlocgiver(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            global smartscan, curR, countmax, countall, empty_thisrun, tries, silent
            curR = 0
            smartscan = True
            all_sort = []

            types = [SPAWN_1x15, SPAWN_1x30, SPAWN_1x45, SPAWN_1x60, SPAWN_2x15, SPAWN_UNDEF]
            typestrs = ['1x15', '1x30', '1x45', '1x60', '2x15', 'UNDEF']
            typecount = [0,0,0,0,0,0]
            tallcount = len(scandata['spawns'])

            pointnum = tallcount
            vleft = 0
            for s in range(0, tallcount):
                spawn = scandata['spawns'][s]
                list_spawns.append(spawn['id'])
                all_sort.append([int(spawn['spawntime']*60000), s])
                for t in range(0, len(types)):
                    if spawn['type'] == types[t]:
                        typecount[t] += 1
                if spawn['type'] == SPAWN_2x15:
                    vspawn = spawn.copy()
                    vspawn['spawntime'] = (vspawn['spawntime'] + 30) % 60
                    vspawn['type'] = VSPAWN_2x15
                    scandata['spawns'].append(vspawn)
                    all_sort.append([int(vspawn['spawntime'] * 60000), pointnum])
                    pointnum += 1
                    vleft += 1

            vtotal = vleft
            infostring = 'ID: {}, {}, Range: {}, Start: {}'.format(wID, location_str, HEX_NUM, datetime.fromtimestamp(starttime / 1000.0).strftime('%H:%M:%S'))

            lprint('\n[+] Starting intelligent scan mode.\n')
            lprint('[+] Spawn point count: {}'.format(tallcount))
            for t in range(0, len(types)):
                lprint('[+] Type: {}, Count: {}, Percentage: {}%'.format(typestrs[t], typecount[t], round(100.0 * typecount[t] / tallcount, 2)))

            lprint('\n\n')
            all_sort = sorted(all_sort, key=itemgetter(0))

            indx_sort = 0
            curT = get_time() % 3600000
            if curT <= all_sort[pointnum-1][0]:
                while curT > all_sort[indx_sort][0]:
                    indx_sort += 1

            wrapindx = indx_sort
            if indx_sort == 0:
                indx_sort = pointnum -1
            else:
                indx_sort -= 1

            lprint('[+] Catch up phase, 0/2 complete.')
            lprint('[+] Time: {}, {}\n'.format(datetime.now().strftime('%H:%M:%S'), infostring))
            catchup = -1.5 * threadnum
            caughtup = False
            nextperc = percinterval
            curT = get_time()
            while indx_sort != wrapindx:
                spawn = scandata['spawns'][all_sort[indx_sort][1]]
                actT = get_time()
                if (actT-curT) < (actT - all_sort[indx_sort][0]) % 3600000 < (spawn['phasetime'] - spawn['pausetime'] - 5) * 60000:
                    addlocation.put([spawn['lat'], spawn['lng']])
                    if spawn['type'] == VSPAWN_2x15:
                        vleft -= 1
                indx_sort -= 1
                if indx_sort == -1:
                    indx_sort = pointnum -1
                catchup += 1
                if (100.0 * catchup / pointnum * 5) >= nextperc:
                    perc = math.floor((100.0 * catchup / pointnum * 5) / percinterval) * percinterval
                    if perc < 100:
                        lprint('[+] Phase complete: {} %'.format(perc))
                    nextperc = perc + percinterval

            lprint('[+] Phase complete: 100 %')

            lprint('\n[+] Catch up phase, 1/2 complete.')
            lprint('[+] Time: {}, {}\n'.format(datetime.now().strftime('%H:%M:%S'), infostring))

            while not caughtup or vleft > 0:
                timediff = (all_sort[indx_sort][0] - get_time() - time_hb * 1000.0) % 3600000
                if timediff < 1800000:
                    if not caughtup:
                        lprint('\n[+] Catch up phase 2/2 complete. Map is now live.')
                        lprint('[+] Time: {}, {}\n'.format(datetime.now().strftime('%H:%M:%S'), infostring))
                        caughtup = True
                        tries = 3
                    time.sleep(((all_sort[indx_sort][0] - get_time()) % 3600000) / 1000.0)
                elif timediff < (3600000 - (time_hb + 1) * 1000.0):
                    lprint('{} s behind.'.format(round((3600000-timediff) / 1000.0, 2)))

                spawn = scandata['spawns'][all_sort[indx_sort][1]]
                addlocation.put([spawn['lat'],spawn['lng']])
                if spawn['type'] == VSPAWN_2x15:
                    vleft -= 1
                indx_sort += 1
                if indx_sort == pointnum:
                    indx_sort = 0

            addlocation.join()
            addforts.join()
            addpokemon.join()
            del scandata['spawns'][pointnum-vtotal:]
            del all_sort[:]
            pointnum = len(scandata['spawns'])

            for s in range(0, pointnum):
                spawn = scandata['spawns'][s]
                all_sort.append([int(spawn['spawntime']*60000), s])
            all_sort = sorted(all_sort, key=itemgetter(0))
            indx_sort = 0
            curT = get_time() % 3600000
            if curT <= all_sort[pointnum-1][0]:
                while curT > all_sort[indx_sort][0]:
                    indx_sort += 1

            lprint('\n[+] Catch up phase, cleanup finished.')
            lprint('[+] Time: {}, {}\n'.format(datetime.now().strftime('%H:%M:%S'), infostring))

            lprint('[+] Switching to silent mode.\n')
            silent = True

            while True:
                timediff = (all_sort[indx_sort][0] - get_time() - time_hb * 1000.0) % 3600000
                if timediff < 1800000:
                    time.sleep(((all_sort[indx_sort][0] - get_time()) % 3600000) / 1000.0)
                elif timediff < (3600000 - (time_hb + 1) * 1000.0):
                    lprint('{} s behind.'.format(round((3600000-timediff) / 1000.0, 2)))

                spawn = scandata['spawns'][all_sort[indx_sort][1]]
                addlocation.put([spawn['lat'], spawn['lng']])

                indx_sort += 1
                if indx_sort == pointnum:
                    indx_sort = 0

                    countmax = 0
                    countall = 0
                    empty_thisrun = 0

                    list_unique.intersection_update(list_seen)
                    list_seen.clear()
                    lprint('\n[+] Time: {}, {}\n'.format(datetime.now().strftime('%H:%M:%S'), infostring))

#########################################################################
#########################################################################
    class locgiver(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            global curR, maxR, scannum, countmax, countall, empty_thisrun, starttime, spawnlyzetime, emptyremoved, runs, location_str, empty_loc, spawns, smartscan
            starttime = get_time()
            runs = 0
            try:
                location_str = 'Location: ({})'.format(geolocator.reverse('{},{}'.format(LAT_C, LNG_C)).address)
            except:
                location_str = 'Lat: {}, Lng: {}'.format(LAT_C, LNG_C)

            if smartscan:
                emptyremoved = True
                exit()

            maxR = len(all_loc)

            infostring = 'ID: {}, {}, Interval: {} s, Range: {}, Start: {}'.format(wID, location_str, interval, HEX_NUM, datetime.fromtimestamp(starttime / 1000.0).strftime('%H:%M:%S'))
            lprint('')
            lprint('[+] Distributing {} locations to {} threads.'.format(len(all_loc), threadnum))

            emptymaxtime = 7200
            spawnmaxtime = 10800
            emptytime = int(time.time()) + emptymaxtime - interval
            spawnlyzetime = int(time.time()) + spawnmaxtime

            ##################################################################################################################################################
            while True:
                runs += 1
                curR = 0
                nextperc = percinterval
                curT = int(time.time())

                lprint('\n\n')
                lprint('[+] Run #{}, Time: {}, {}'.format(runs, datetime.now().strftime('%H:%M:%S'), infostring))
                for this_loc in all_loc:
                    addlocation.put(this_loc)
                    if (100.0 * curR / maxR) >= nextperc:
                        perc = math.floor((100.0 * curR / maxR) / percinterval) * percinterval
                        lprint('[+] Finished: {} %'.format(perc))
                        nextperc = perc + percinterval

                addlocation.join()
                addforts.join()
                addpokemon.join()
                lprint('[+] Finished: 100 %')
                lprint('')

                lprint('[+] {} of {} cells detected as empty during last run.'.format(empty_thisrun, maxR))
                lprint('[+] Non-empty heartbeats reached a maximum of {} retries, allowed: {}.'.format(countmax, tries))
                ave_retries = float(countall) / maxR
                lprint('[+] Average number of retries was {}, total number {}.'.format(round(ave_retries, 2), countall))

                #########################################################################
                if not emptyremoved and curT > emptytime:
                    emptyremoved = True
                    l = 0
                    while l < len(all_loc):
                        if empty_loc[l] == runs:  # within whole time came up as empty, standard setting 2 hours
                            this_loc = all_loc.pop(l)
                            scandata['emptylocs'].append({'lat': this_loc[0], 'lng': this_loc[1]})
                            empty_loc.pop(l)
                        else:
                            l += 1

                    lprint('[+] {} locations were permanently removed as empty. They\'ve been empty during {} consecutive scans covering a time of {} seconds.'.format(maxR - len(all_loc), runs, emptymaxtime))
                    maxR = len(all_loc)

                #########################################################################
                countmax = 0
                countall = 0
                empty_thisrun = 0

                list_unique.intersection_update(list_seen)
                list_seen.clear()

                #########################################################################
                if curT > spawnlyzetime:
                    addspawns.join()
                    for s in spawns:
                        if s.type == SPAWN_DEF:
                            if s.phasetime == 60:
                                if s.pauses == 0:
                                    s.type = SPAWN_1x60
                                elif s.pauses == 1:
                                    if s.pausetime == 45:
                                        s.type = SPAWN_1x15
                                    elif s.pausetime == 30:
                                        s.type = SPAWN_1x30
                                    elif s.pausetime == 15:
                                        s.type = SPAWN_1x45
                                elif s.pauses == 2:
                                    if s.pausetime == 15:
                                        s.type = SPAWN_2x15
                        else:
                            if s.spawntime == -1:
                                s.spawntime = ((s.phasetime / 1000.0) / 60) % 60
                            s.phasetime = -1
                            s.pauses = -1
                            s.pausetime = -1
                        scandata['spawns'].append({'type': s.type, 'id': s.spawnid, 'lat': s.lat, 'lng': s.lng, 'spawntime': s.spawntime, 'phasetime': s.phasetime, 'pauses': s.pauses, 'pausetime': s.pausetime})
                    del spawns
                    try:
                        f = open(scan_file, 'w', 0)
                        json.dump(scandata, f, indent=1, separators=(',', ': '))
                        lprint('Scandata was written to file.')
                        f.close()
                    finally:
                        if 'f' in vars() and not f.closed:
                            f.close()
                    del all_loc[:]
                    del list_spawns[:]
                    del empty_loc
                    smartscan = True
                    exit()

                #########################################################################
                curT = int(time.time()) - curT
                lprint('[+] Scan Time: {} s'.format(curT))

                if scannum > 0:
                    scannum -= 1
                    if scannum == 0:
                        sys.exit()

                curT = max(interval - curT, 0)
                lprint('[+] Sleeping for {} seconds...'.format(curT))
                time.sleep(curT)
                prune_data()

#########################################################################
#########################################################################
    class collector(threading.Thread):
        def __init__(self, name, account):
            threading.Thread.__init__(self)
            self.account = account

        def run(self):
            global curR, countmax, countall, empty_loc, empty_thisrun

            do_login(self.account)
            lprint('[{}] Login for {} account: {}'.format(self.account['num'], self.account['type'], self.account['user']))
            lprint('[{}] RPC Session Token: {}'.format(self.account['num'], self.account['access_token']))
            location = LAT_C, LNG_C , ALT_C
            set_api_endpoint(location, self.account)
            lprint('[{}] API endpoint: {}'.format(self.account['num'], self.account['api_url']))
            if acc_tos:
                accept_tos(location, self.account)
            # /////////////////
            synch_li.get()
            synch_li.task_done()

            # ////////////////////
            while True:
                this_loc = addlocation.get()
                location = this_loc[0], this_loc[1], ALT_C
                h = heartbeat(location, self.account)
                count = 0
                while h is None and count < tries:
                    count += 1
                    time.sleep(time_small)
                    h = heartbeat(location, self.account)
                if h is None:
                    if not smartscan:
                        empty_loc[all_loc.index(this_loc)] += 1
                        empty_thisrun += 1
                    else:
                        lprint('[-] Non-empty cell returned as empty.')
                else:
                    if not smartscan:
                        empty_loc[all_loc.index(this_loc)] = 0
                        countmax = max(countmax, count)
                        countall += count
                    for cell in h.map_cells:
                        for p in range(0,len(cell.wild_pokemons)):
                            if cell.catchable_pokemons[p].expiration_timestamp_ms == -1:
                                cell.wild_pokemons[p].time_till_hidden_ms = -1
                            addpokemon.put(cell.wild_pokemons[p])
                        if not emptyremoved:
                            for fort in cell.forts:
                                addforts.put(fort)
                curR += 1
                addlocation.task_done()

#########################################################################
#########################################################################
    class fortjoiner(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
        def run(self):
            while not emptyremoved:
                fort = addforts.get()
                id_str = fort.id[:-3]

                fortIDint = int(id_str, 16)
                if fortIDint not in list_forts:
                    list_forts.add(fortIDint)
                    thisfort = {'id': fortIDint, 'lat': fort.latitude, 'lng': fort.longitude}
                    if fort.type == 1:
                        scandata['stops'].append(thisfort)
                    else:
                        scandata['gyms'].append(thisfort)
                addforts.task_done()

#########################################################################
#########################################################################
    class pokejoiner(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            data_file = '{}/webres/data{}.json'.format(workdir, wID)
            stat_file = '{}/res/spawns{}.txt'.format(workdir, wID)
            POKEMONS = json.load(open('{}/webres/{}.json'.format(workdir, LANGUAGE)))
            statheader = 'Name\tid\tSpawnID\tlat\tlng\tspawnTime\tTime\tTime2Hidden\tencounterID\n'

            interval_datwrite = 5
            nextdatwrite = time.time() + interval_datwrite
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
                            if time.time() < spawnlyzetime:
                                addspawns.put(wild)

                            mod_tth = wild.time_till_hidden_ms
                            addinfo = 0
                            if smartscan:
                                list_unique.add(wild.encounter_id)
                                if spawnIDint in list_spawns:
                                    spawn = scandata['spawns'][list_spawns.index(spawnIDint)]
                                    if spawn['type'] != SPAWN_UNDEF:
                                        finished_ms = (wild.last_modified_timestamp_ms - spawn['spawntime'] * 60000) % 3600000
                                        if spawn['type'] == SPAWN_2x15 and finished_ms < 1800000:
                                            addinfo = 1
                                            finished_ms += 1800000
                                        mod_tth = int((spawn['phasetime'] - spawn['pausetime']) * 60000 - finished_ms)
                            if mod_tth > 0:
                                list_unique.add(wild.encounter_id)
                            else:
                                mod_tth = 901000
                            f.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(POKEMONS[wild.pokemon_data.pokemon_id], wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, (wild.last_modified_timestamp_ms + mod_tth) / 1000.0 - 900.0,
                                                                                  wild.last_modified_timestamp_ms / 1000.0, wild.time_till_hidden_ms / 1000.0, wild.encounter_id))
                            if addinfo: #accomodates for the 2x15 spawn's second time
                                f.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(POKEMONS[wild.pokemon_data.pokemon_id], wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, (wild.last_modified_timestamp_ms + 1800000 + mod_tth) / 1000.0 - 900.0,
                                                                                      (wild.last_modified_timestamp_ms + 1800000) / 1000.0, wild.time_till_hidden_ms / 1000.0, wild.encounter_id))
                            if wild.pokemon_data.pokemon_id not in exclude_ids:
                                if addinfo:
                                    DATA.append([wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, int((wild.last_modified_timestamp_ms + mod_tth + 180000) / 1000.0),addinfo])
                                else:
                                    DATA.append([wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, int((wild.last_modified_timestamp_ms + mod_tth) / 1000.0)])
                            if not silent:
                                other_ll = LatLng.from_degrees(wild.latitude, wild.longitude)
                                origin_ll = LatLng.from_degrees(LAT_C, LNG_C)
                                diff = other_ll - origin_ll
                                difflat = diff.lat().degrees
                                difflng = diff.lng().degrees
                                distance = int(origin_ll.get_distance(other_ll).radians * 6366468.241830914)
                                direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '') + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')
                                lprint('[+] ({}) {} visible for {} seconds ({}m {} from you)'.format(wild.pokemon_data.pokemon_id, POKEMONS[wild.pokemon_data.pokemon_id], int(mod_tth / 1000.0), distance, direction))

                            if pb is not None and wild.pokemon_data.pokemon_id in PUSHPOKS:
                                try:
                                    location = geolocator.reverse('{},{}'.format(wild.latitude, wild.longitude))
                                    notification_text = "{} @ {}".format(POKEMONS[wild.pokemon_data.pokemon_id], location.address)
                                except:
                                    notification_text = '{} found!'.format(POKEMONS[wild.pokemon_data.pokemon_id])
                                disappear_time = datetime.fromtimestamp(int((wild.last_modified_timestamp_ms + mod_tth) / 1000.0)).strftime("%H:%M:%S")
                                time_text = 'disappears at: {}'.format(disappear_time)
                                if addinfo:
                                    time_text += '\nwill then reappear after 15 m for 15 m.'
                                for pushacc in pb:
                                    pushacc.push_link(notification_text, 'http://www.google.com/maps/place/{},{}'.format(wild.latitude, wild.longitude), body=time_text)

                            if addpokemon.empty() and time.time() < nextdatwrite:
                                time.sleep(1)
                            if addpokemon.empty() or time.time() >= nextdatwrite:
                                prune_data()
                                write_data(data_file)
                                if f.tell() > F_LIMIT:
                                    lprint('[+] File size is over the set limit, doing backup.')
                                    f.close()
                                    move(stat_file, stat_file[:-4] + '.' + time.strftime('%Y%m%d_%H%M') + '.txt')
                                    f = open(stat_file, 'a', 0)
                                    f.write(statheader)

                                nextdatwrite = time.time() + interval_datwrite
                    addpokemon.task_done()
            finally:
                if 'f' in vars() and not f.closed:
                    f.close()

#########################################################################
#########################################################################
    class webserver(threading.Thread):
        def __init__(self, port, workdir):
            threading.Thread.__init__(self)
            self.port = port
            self.workdir = workdir

        def run(self):
            pokesite.server_start(port, workdir)

#########################################################################
#########################################################################

    global all_loc, empty_loc, signature_lib, lock_network, lock_banfile, locktime, addlocation, synch_li, smartscan

    random.seed()

    signature_lib = ctypes.cdll.LoadLibrary('{}/res/encrypt.so'.format(workdir))
    signature_lib.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_size_t)]
    signature_lib.restype = ctypes.c_int

    accounts = do_settings()

    list_spawns = []
    list_forts = set([])

    list_seen = set([])
    list_unique = set([])
    threadnum = len(accounts)
    threadList = []
    locktime = min(0.8* time_hb / threadnum, 0.1)

    addpokemon = Queue.Queue(threadnum)
    synch_li = Queue.Queue(threadnum)
    addlocation = Queue.Queue(threadnum)
    addspawns = Queue.Queue(threadnum)
    addforts = Queue.Queue(threadnum)

    lock_network = threading.Lock()
    lock_banfile = threading.Lock()

    scan_file = '{}/res/{}_{}_{}_{}.json'.format(workdir, LAT_C, LNG_C, HEX_NUM, HEX_R)
    try:
        f = open(scan_file, 'r')
        scandata = json.load(f)
        f.close()
        smartscan = True
    except Exception as e:
        smartscan = False
        lprint('Can\'t load location database file: {}'.format(e))
        lprint('After a learning phase of 3 hours this file will be created and it\'ll make subsequent scans with the same parameters very efficient.\n')
        scandata = {'parameters': {'lat': LAT_C, 'lng': LNG_C, 'range': HEX_NUM, 'sight': HEX_R}, 'emptylocs': [], 'spawns': [], 'stops': [], 'gyms': []}
    finally:
        if 'f' in vars() and not f.closed:
            f.close()

    if not smartscan:
        all_loc = [[LAT_C, LNG_C]]
        empty_loc = []

        latrad = LAT_C * math.pi / 180
        HEX_M = 3.0 ** 0.5 / 2.0 * HEX_R

        x_un = 1.5 * HEX_R / getEarthRadius(latrad) / math.cos(latrad) * safety * 180 / math.pi
        y_un = 1.0 * HEX_M / getEarthRadius(latrad) * safety * 180 / math.pi

        for a in range(1, HEX_NUM + 1):
            for s in range(0, 6):
                for i in range(0, a):
                    if s == 0:
                        lat = LAT_C + y_un * (-2 * a + i)
                        lng = LNG_C + x_un * i
                    elif s == 1:
                        lat = LAT_C + y_un * (-a + 2 * i)
                        lng = LNG_C + x_un * a
                    elif s == 2:
                        lat = LAT_C + y_un * (a + i)
                        lng = LNG_C + x_un * (a - i)
                    elif s == 3:
                        lat = LAT_C - y_un * (-2 * a + i)
                        lng = LNG_C - x_un * i
                    elif s == 4:
                        lat = LAT_C - y_un * (-a + 2 * i)
                        lng = LNG_C - x_un * a
                    else:  # if s==5:
                        lat = LAT_C - y_un * (a + i)
                        lng = LNG_C - x_un * (a - i)

                    all_loc.append([lat, lng])

        empty_loc = [0] * len(all_loc)

        newthread = spawnjoiner()
        newthread.deaemon = True
        newthread.start()

    newthread = pokejoiner()
    newthread.daemon = True
    newthread.start()

    newthread = fortjoiner()
    newthread.daemon = True
    newthread.start()

    if login_simu:
        for i in range(0, threadnum):
            synch_li.put(True)

    if port > 0:
        newthread = webserver(port, workdir)
        newthread.daemon = True
        newthread.start()

    for i in range(0, threadnum):
        newthread = collector(i, accounts[i])
        newthread.daemon = True
        newthread.start()
        threadList.append(newthread)
        if not login_simu:
            synch_li.put(True)
            while not synch_li.empty():
                time.sleep(1)

    if login_simu:
        while not synch_li.empty():
            time.sleep(2)

    newthread = locgiver()
    newthread.daemon = True
    newthread.start()

    while newthread.isAlive():
        newthread.join(5)

    if smartscan:
        newthread = smartlocgiver()
        newthread.daemon = True
        newthread.start()

        while newthread.isAlive():
            newthread.join(5)

if __name__ == '__main__':
    main()
