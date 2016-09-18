# -*- coding: UTF-8 -*-
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
import POGOProtos.Networking.Platform_pb2
import POGOProtos.Networking.Platform
import POGOProtos.Networking.Platform.Requests_pb2

import time
from datetime import datetime
import sys
import math
import os
import random
import platform

import sqlite3

import pushbullet
from pushbullet import Pushbullet
import telepot
from geopy.geocoders import Nominatim
from unidecode import unidecode
from s2sphere import CellId, LatLng
from gpsoauth import perform_master_login, perform_oauth
from shutil import move
from operator import itemgetter

from res.uk6 import generateLocation1, generateLocation2, generateRequestHash, generate_signature
import ctypes

import threading
import Queue

import pokesite

import signal

def format_address(input, fieldnum):
    fields = input.split(', ')
    output = fields[0]
    for f in range(1,min(fieldnum,len(fields))):
        output += ', ' + fields[f]
    output = unidecode(output.encode('utf-8').replace('�','ae').replace('�','oe').replace('�','ue').replace('�','ss').decode('utf-8'))
    return output

def get_time():
    return int(round(time.time() * 1000))

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
random.seed()

NET_MAXWAIT = 30
LOGIN_MAXWAIT = 30
MAXWAIT = LOGIN_MAXWAIT
time_socks5_retry = 30

EARTH_Rmax = 6378137.0
EARTH_Rmin = 6356752.3
HEX_R = 70.0
num_cells = 9

safety = 0.999

LOGGING = False
DATA = []
exclude_ids = None
pb = []
telegrams = []
telebot = None
PUSHPOKS = []
geolocator = Nominatim()
add_location_name = False

F_LIMIT = None
LANGUAGE = None
HEX_NUM = None
wID = None
interval = None
workdir = os.path.dirname(os.path.realpath(__file__))
data_file = '{}/webres/data.db'.format(workdir)
data_buffer = []

LAT_C, LNG_C= [None, None]
accuracy = random.random()*7+3

SETTINGS_FILE = '{}/res/usersettings.json'.format(workdir)

time_hb = 10
tries = 1
percinterval = 2
curR = None
maxR = None
starttime = None
runs = 0
location_str = ''
countmax = 0
countall = 0
empty_thisrun = 0
scan_compromised = False
all_loc = None
empty_loc = None
addlocation = None
synch_li = None

scannum = None
login_simu = False
acc_tos = False

signature_lib = None
lock_network = threading.Lock()
lock_banfile = threading.Lock()
locktime = None
plan = False
smartscan = False
silent = False
verbose = False
dumb = False
safetysecs = 3

def get_encryption_lib_path():
    # win32 doesn't mean necessarily 32 bits
    if sys.platform == "win32" or sys.platform == "cygwin":
        if platform.architecture()[0] == '64bit':
            lib_name = "encrypt64bit.dll"
        else:
            lib_name = "encrypt32bit.dll"

    elif sys.platform == "darwin":
        lib_name = "libencrypt-osx-64.so"

    elif os.uname()[4].startswith("arm") and platform.architecture()[0] == '32bit':
        lib_name = "libencrypt-linux-arm-32.so"

    elif os.uname()[4].startswith("aarch64") and platform.architecture()[0] == '64bit':
        lib_name = "libencrypt-linux-arm-64.so"

    elif sys.platform.startswith('linux'):
        if "centos" in platform.platform():
            if platform.architecture()[0] == '64bit':
                lib_name = "libencrypt-centos-x86-64.so"
            else:
                lib_name = "libencrypt-linux-x86-32.so"
        else:
            if platform.architecture()[0] == '64bit':
                lib_name = "libencrypt-linux-x86-64.so"
            else:
                lib_name = "libencrypt-linux-x86-32.so"

    elif sys.platform.startswith('freebsd'):
        lib_name = "libencrypt-freebsd-64.so"

    elif sys.platform.startswith('sunos5'):
        lib_name = "libencrypt-sunos5-x86-64.so"

    else:
        err = "Unexpected/unsupported platform '{}'.".format(sys.platform)
        lprint(err)
        raise Exception(err)

    lib_path = os.path.join(os.path.dirname(__file__), "res", "libencrypt", lib_name)

    if not os.path.isfile(lib_path):
        err = "Could not find {} encryption library {}".format(sys.platform, lib_path)
        lprint(err)
        raise Exception(err)

    return lib_path

def do_settings():
    global LANGUAGE, LAT_C, LNG_C, HEX_NUM, interval, F_LIMIT, pb, PUSHPOKS, scannum, login_simu, wID, acc_tos, exclude_ids, telebot,add_location_name,verbose,dumb

    parser = argparse.ArgumentParser()
    parser.add_argument('-id', '--id', help='group id')
    parser.add_argument('-r', '--range', help='scan range')
    parser.add_argument('-t', '--timeinterval', help='time interval')
    parser.add_argument('-lat', '--latitude', help='latitude')
    parser.add_argument('-lng', '--longitude', help='longitude')
    parser.add_argument('-loc', '--location', help='location')
    parser.add_argument('-s', "--scannum", help="number of scans to run")
    parser.add_argument('-tos', "--tosaccept", help="let accounts accept tos at start", action="store_true")
    parser.add_argument('-v', '--verbose', help='makes it put out all found pokemon all the time', action='store_true')
    parser.add_argument('-d','--dumb', help='disables smartscan', action='store_true')
    parser.add_argument('-p', '--plan', help='loads scan plans from planning folder')
    args = parser.parse_args()
    wID = args.id
    HEX_NUM = args.range
    interval = args.timeinterval

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
    if args.verbose:
        verbose = True
    if args.dumb:
        dumb = True

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

    if allsettings['notifications']['enabled']:
        PUSHPOKS = set(allsettings['notifications']['push_ids'])
        if allsettings['notifications']['add_location_name']:
            add_location_name = True
        if allsettings['notifications']['pushbullet']['enabled']:
            for key in allsettings['notifications']['pushbullet']['api_key']:
                try:
                    this_pb = Pushbullet(key)
                    if allsettings['notifications']['pushbullet']['use_channels']:
                        for channel in this_pb.channels:
                            if channel.channel_tag in allsettings['notifications']['pushbullet']['channel_tags']:
                                pb.append(channel)
                    else:
                        pb.append(this_pb)
                except Exception as e:
                    lprint('[-] Pushbullet error, key {} is invalid, {}'.format(key, e))
                    lprint('[-] This pushbullet will be disabled.')
        if allsettings['notifications']['telegram']['enabled']:
            telebot = telepot.Bot(allsettings['notifications']['telegram']['bot_token'])
            for chat_id in allsettings['notifications']['telegram']['chat_ids']:
                telegrams.append(chat_id)
        if (len(telegrams) + len(pb)) == 0:
            PUSHPOKS = []

    LANGUAGE = allsettings['language']

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
        proxies = None
        if 'proxy' in allsettings['profiles'][idlist[0]] and allsettings['profiles'][idlist[0]]['proxy']:
            proxies = {'http': allsettings['profiles'][idlist[0]]['proxy'], 'https': allsettings['profiles'][idlist[0]]['proxy']}
            lprint('[+] Using group proxy: {}'.format(allsettings['profiles'][idlist[0]]['proxy']))
        for i in range(0, len(idlist)):
            account = {'num': i, 'type': allsettings['profiles'][idlist[i]]['type'], 'user': allsettings['profiles'][idlist[i]]['username'], 'pw': allsettings['profiles'][idlist[i]]['password']}
            if i > 0 and 'proxy' in allsettings['profiles'][idlist[i]] and allsettings['profiles'][idlist[i]]['proxy']:
                account['proxy']={'http': allsettings['profiles'][idlist[i]]['proxy'], 'https': allsettings['profiles'][idlist[i]]['proxy']}
                lprint('[{}] Using individual proxy: {}'.format(i,allsettings['profiles'][idlist[i]]['proxy']))
            elif not proxies is None:
                account['proxy'] = proxies
            else:
                account['proxy'] = None

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

    lprint('')
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
                lprint('[{}] Google Login error, retrying in {} seconds (step 1)'.format(account['num'], retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                login1 = perform_master_login(account['user'], account['pw'], ANDROID_ID)

            retry_after = 1
            login2 = perform_oauth(account['user'], login1.get('Token'), ANDROID_ID, SERVICE, APP, APP_SIG)
            while login2.get('Auth') is None:
                lprint('[{}] Google Login error, retrying in {} seconds (step 2)'.format(account['num'], retry_after))
                time.sleep(retry_after)
                retry_after = min(retry_after * 2, MAXWAIT)
                login2 = perform_oauth(account['user'], login1.get('Token', ''), ANDROID_ID, SERVICE, APP, APP_SIG)

            access_token = login2['Auth']
            account['access_expire_timestamp'] = int(login2['Expiry'])*1000
            account['access_token'] = access_token
            session = requests.session()
            session.verify = True
            session.headers.update({'User-Agent': 'Niantic App'}) #session.headers.update({'User-Agent': 'niantic'})
            if not account['proxy'] is None:
                session.proxies.update(account['proxy'])
            account['session'] = session
            return
        except Exception as e:
            lprint('[{}] Unexpected google login error: {}'.format(account['num'], e))
            lprint('[{}] Retrying...'.format(account['num']))
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
            if not account['proxy'] is None:
                session.proxies.update(account['proxy'])

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
            if r is not None:
                try:
                    answer = json.loads(r.content)
                    if answer.get('error_code',None) == 'users.login.activation_required':
                        lprint('[{}] Login error for {}, needs email verification.'.format(account['num'],account['user']))
                        exit()
                    elif answer.get('errors',None)[0].startswith('Your username or password is incorrect.'):
                        lprint('[{}] Login error for {}, incorrect username/password/account does not exist.'.format(account['num'], account['user']))
                        exit()
                    elif answer.get('errors',None)[0].startswith('As a security measure, your account has been disabled for 15 minutes'):
                        lprint('[{}] Login error for {}, incorrect username/password was entered 5 times, login for that account is disabled for 15 minutes.'.format(account['num'], account['user']))
                        exit()
                    lprint('[{}] Connection error, http code: {}, content: {}'.format(account['num'], r.status_code, answer))
                except ValueError:
                    lprint('[{}] Ptc login error in step {}: {}'.format(account['num'], step, e))
            else:
                lprint('[{}] Ptc login error in step {}: {}'.format(account['num'], step, e))
                lprint('[{}] Error happened before network request.'.format(account['num']))
            lprint('[{}] Retrying...'.format(account['num']))
            time.sleep(2)


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

    p_req.latitude, p_req.longitude, p_req.accuracy = location[0],location[1],accuracy

    for s_req in reqs:
        p_req.MergeFrom(s_req)

    p_req.ms_since_last_locationfix = 989

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
    sig.location_hash1 = generateLocation1(ticket_serialized, location[0], location[1], accuracy)
    sig.location_hash2 = generateLocation2(location[0], location[1], accuracy)

    for req in p_req.requests:
        req_hash = generateRequestHash(ticket_serialized, req.SerializeToString())
        sig.request_hash.append(req_hash)

    sig.session_hash = account['session_hash']
    sig.timestamp = get_time()
    sig.timestamp_since_start = get_time() - account['login_time']
    sig.unknown25 = -8537042734809897855

    signature_proto = sig.SerializeToString()

    request_sig = p_req.platform_requests.add()
    request_sig.type = POGOProtos.Networking.Platform_pb2.SEND_ENCRYPTED_SIGNATURE
    sig_env = POGOProtos.Networking.Platform.Requests_pb2.SendEncryptedSignatureRequest()

    sig_env.encrypted_signature = generate_signature(signature_proto, signature_lib)
    request_sig.request_message = sig_env.SerializeToString()

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
                if account['proxy'] is not None:
                    if account['proxy']['http'].startswith('socks5'):
                        lprint('[+] Socks5 Proxy detected. Sleeping and retrying after 30 s.')
                        time.sleep(time_socks5_retry)
                    else:
                        lprint('[-] Access denied, your IP is blocked by the N-company. ({})'.format(account['user']))
                        sys.exit()
                else:
                    lprint('[-] Access denied, your IP is blocked by the N-company.')
                    sys.exit()
            elif r.status_code == 502:
                lprint('[{}] Servers busy (502), retrying...'.format(account['num']))
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
            loopcount += 1
            if loopcount > 4:
                return None
        except Exception as e:
            lprint('[-] Unexpected connection error, error: {}'.format(e))
            if r is not None:
                lprint('[-] Unexpected connection error, http code: {}'.format(r.status_code))
            else:
                lprint('[-] Error happened before network request.')
            lprint('[-] Retrying...')
            time.sleep(1)
            loopcount += 1
            if loopcount > 4:
                return None


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
    req3.request_type = POGOProtos.Networking.Envelopes_pb2.CHECK_CHALLENGE
    if len(reqq) >= 3:
        req3.MergeFrom(reqq[2])

    req4 = req.requests.add()
    req4.request_type = POGOProtos.Networking.Envelopes_pb2.GET_INVENTORY
    if len(reqq) >= 4:
        req4.MergeFrom(reqq[3])

    req5 = req.requests.add()
    req5.request_type = POGOProtos.Networking.Envelopes_pb2.CHECK_AWARDED_BADGES
    if len(reqq) >= 5:
        req5.MergeFrom(reqq[4])

    req6 = req.requests.add()
    req6.request_type = POGOProtos.Networking.Envelopes_pb2.DOWNLOAD_SETTINGS
    if len(reqq) >= 6:
        req6.MergeFrom(reqq[5])

    while True:  # 1 for heartbeat, 2 for profile authorization, 53 for api endpoint, 52 for error, 102 session token invalid
        time.sleep(time_hb)
        response = api_req(location, account, account['api_url'], account['access_token'], req, useauth=account['auth_ticket'])
        if response is None:
            time.sleep(1)
            lprint('[{}] Response error, retrying...'.format(account['num']))
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
            lprint('[{}] Servers busy (52), retrying...'.format(account['num']))
        elif response.status_code == 3:
            if synch_li.empty():
                #addlocation.put([location[0],location[1]])
                addlocation.task_done()
            else:
                synch_li.get()
                synch_li.task_done()
            lprint('Account {}: {} was banned. It\'ll be logged out.'.format(account['num']+1,account['user']))
            lock_banfile.acquire()
            try:
                f = open('{}/res/banned{}.txt'.format(workdir, wID), 'a')
                f.write('{}\n'.format(account['user']))
            finally:
                if 'f' in vars() and not f.closed:
                    f.close()
            lock_banfile.release()
            exit()
        else:
            lprint('[-] Response error, unexpected status code: {}, retrying...'.format(response.status_code))
            print(response)
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

    timenow = get_time()
    if timenow > account['access_expire_timestamp'] - 30000:
        lprint('[+] Login refresh.')
        do_login(account)
        set_api_endpoint(location, account)
    elif timenow > account['auth_ticket'].expire_timestamp_ms:
        lprint('[+] Authorization refresh.')
        set_api_endpoint(location,account)

    response = get_profile(1, location, account, m1)
    heartbeat = POGOProtos.Networking.Responses_pb2.GetMapObjectsResponse()
    heartbeat.ParseFromString(response.returns[0])
    return heartbeat


def accept_tos(location, account):
    m1 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
    m1.request_type = POGOProtos.Networking.Envelopes_pb2.MARK_TUTORIAL_COMPLETE
    m11 = POGOProtos.Networking.Requests.Messages_pb2.MarkTutorialCompleteMessage()

    m11.tutorials_completed.append(POGOProtos.Enums_pb2.LEGAL_SCREEN)
    m11.send_marketing_emails = False
    m11.send_push_notifications = False

    m1.request_message = m11.SerializeToString()
    get_profile(0, location, account, m1)

def init_data():
    con = sqlite3.connect(data_file)
    with con:
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS spawns(spawnid INTEGER PRIMARY KEY, latitude REAL, longitude REAL, spawntype INTEGER, pokeid INTEGER, expiretime INTEGER, fromtime INTEGER, profile INTEGER)")
        cur.execute("PRAGMA journal_mode = OFF")

def update_data():
    timenow = int(round(time.time(),0))
    con = sqlite3.connect(data_file)
    with con:
        cur = con.cursor()
        for l in range(0,len(data_buffer)):
            [pokeid, spawnid, latitude, longitude, expiretime, addinfo] = data_buffer.pop()
            cur.execute("INSERT OR REPLACE INTO spawns VALUES(?,?,?,?,?,?,?,?)",[spawnid,round(latitude,5),round(longitude,5),addinfo,pokeid,expiretime,timenow,wID])


def lprint(message):
    sys.stdout.write(str(message) + '\n')


##################################################################################################################################################
##################################################################################################################################################
def main():
    SPAWN_UNDEF = -1
    SPAWN_DEF = 1
    SPAWN_1x15 = 101
    SPAWN_1x30 = 102
    SPAWN_1x45 = 103
    SPAWN_1x60 = 104
    SPAWN_2x15 = 201  # 2x15
    SPAWN_1x60h2 = 202
    SPAWN_1x60h3 = 203
    SPAWN_1x60h23 = 204
    VSPAWN_2x15 = 2201
    VSPAWN_1x60h2 = 2202
    VSPAWN_1x60h3 = 2203
    VSPAWN_1x60h23 = 2204

    class spawnpoint:
        def __init__(self, lat, lng, spawnid):
            self.type = SPAWN_UNDEF
            self.lat = lat
            self.lng = lng
            self.spawnid = spawnid

            self.spawntime = -1
            self.pausetime = -1

            self.encounters = []

    class scan:
        def __init__(self,location):
            self.location = location
            self.spawns = []
            self.times = []
            for c in range(0,num_cells):
                self.spawns.append(set([]))
                self.times.append([])

#########################################################################
#########################################################################
    class spawnjoiner(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            global scan_compromised
            scan_compromised = False

            list_spawns = []
            all_spawns = []
            list_encounters = []

            list_free_eids = []
            list_free_times = []

            location, h = addspawns.get()
            while not smartscan:
                scan = all_scans[all_loc.index(location)]

                for n in range(0,num_cells):
                    cell = h.map_cells[n]
                    cell_time = cell.current_timestamp_ms
                    scan.times[n].append(cell_time)
                    if len(scan.times[n]) > 1 and scan.times[n][-1] - scan.times[n][-2] > time_1q - 1:
                        scan_compromised = True

                    for wild in cell.wild_pokemons:
                        spawnIDint = int(wild.spawn_point_id, 16)
                        scan.spawns[n].add(spawnIDint)

                        if spawnIDint not in list_spawns:
                            list_spawns.append(spawnIDint)
                            list_encounters.append(wild.encounter_id)
                            spawn = spawnpoint(wild.latitude,wild.longitude,spawnIDint)
                            all_spawns.append(spawn)
                            spawn.encounters.append((wild.encounter_id,[wild.last_modified_timestamp_ms]))
                        else:
                            ind = list_spawns.index(spawnIDint)
                            spawn = all_spawns[ind]
                            if spawn.encounters[-1][0] == wild.encounter_id:
                                spawn.encounters[-1][1].append(wild.last_modified_timestamp_ms)
                            else:
                                spawn.encounters.append((wild.encounter_id, [wild.last_modified_timestamp_ms]))
                                list_encounters[ind] = wild.encounter_id

                        if wild.time_till_hidden_ms > 0:
                            spawn.spawntime = (wild.last_modified_timestamp_ms + wild.time_till_hidden_ms - time_1q) % time_4q
                            spawn.encounters[-1][1].append(wild.last_modified_timestamp_ms + wild.time_till_hidden_ms - time_1q)
                            spawn.encounters[-1][1].append(wild.last_modified_timestamp_ms + wild.time_till_hidden_ms - 1)

                    for nearby in cell.nearby_pokemons:
                        if nearby.encounter_id in list_encounters:
                            ind = list_encounters.index(nearby.encounter_id)
                            spawn = all_spawns[ind]
                            if not spawn.encounters[-1][1][-1] == cell_time:
                                spawn.encounters[-1][1].append(cell_time)
                        else:
                            list_free_eids.append(nearby.encounter_id)
                            list_free_times.append(cell_time)

                addspawns.task_done()
                location, h = addspawns.get()

            #######
            for spawn in all_spawns:
                scanned_times = []
                occupied_times = []

                for encounter in spawn.encounters:
                    while encounter[0] in list_free_eids:
                        ind = list_free_eids.index(encounter[0])
                        encounter[1].append(list_free_times[ind])
                        list_free_eids.pop(ind)
                        list_free_times.pop(ind)
                    occupied_times.extend(encounter[1])

                for t in range(0,len(occupied_times)):
                    occupied_times[t] %= time_4q
                occupied_times.sort()

                for scan in all_scans:
                    for c in range(0,num_cells):
                        if spawn.spawnid in scan.spawns[c]:
                            scanned_times.extend(scan.times[c])
                for t in range(0,len(scanned_times)):
                    scanned_times[t] %= time_4q

                scanned_times.extend(occupied_times)
                scanned_times.sort()

                spawn_compromised = False
                for t in range(1,len(scanned_times)):
                    if scanned_times[t]-scanned_times[t-1] > time_1q-1:
                        spawn_compromised = True
                        break
                if spawn_compromised or scanned_times[0]+time_4q - scanned_times[-1] > time_1q-1:
                    continue

                pausetime = 0
                for t in range(1,len(occupied_times)):
                    pausetime = max(occupied_times[t]-occupied_times[t-1],pausetime)
                pausetime = max(occupied_times[0] + time_4q -occupied_times[-1],pausetime)

                if pausetime > time_4q - 1:
                    continue

                first_time = min(spawn.encounters[0][1])
                last_time = max(spawn.encounters[0][1])
                for en in range(1,len(spawn.encounters)):
                    first_time = min(min(spawn.encounters[en][1]) - time_4q*en, first_time)
                    last_time = max(max(spawn.encounters[en][1]) - time_4q*en, last_time)

                if pausetime < time_1q + 1:
                    spawn.type = SPAWN_1x60
                    spawn.spawntime = first_time % time_4q
                    spawn.pausetime = time_4q - (last_time - first_time)
                    continue

                spawn.pausetime = int(math.floor(float(pausetime)/time_1q))*time_1q

                qdiff = int(math.ceil(float((spawn.spawntime - first_time) % time_4q)/time_1q)) % 4
                spawn.spawntime = (spawn.spawntime - qdiff * time_1q) % time_4q

                occupied = [True,False,False,False]
                occupied[qdiff] = True
                for occ in range(1,4):
                    if not occupied[occ]:
                        for time in occupied_times:
                            if (time - (spawn.spawntime + time_1q*occ)) % time_4q < time_1q:
                                occupied[occ] = True
                                break

                if pausetime < 2*time_1q + 1:
                    if occupied == [True,True,True,False]:
                        spawn.type = SPAWN_1x45
                    elif occupied == [True, False, True, False]:
                        spawn.type = SPAWN_2x15
                    elif occupied == [True,False,True,True]:
                        spawn.type = SPAWN_1x60h2
                    elif occupied == [True,True,False,True]:
                        spawn.type = SPAWN_1x60h3
                elif pausetime < 3*time_1q + 1:
                    if occupied == [True,True,False,False]:
                        spawn.type = SPAWN_1x30
                    elif occupied == [True,False,False,True]:
                        spawn.type = SPAWN_1x60h23
                else:
                    if occupied == [True,False,False,False]:
                        spawn.type = SPAWN_1x15

            #######
            for s in all_spawns:
                scandata['spawns'].append({'type': s.type, 'id': s.spawnid, 'lat': s.lat, 'lng': s.lng, 'spawntime': s.spawntime, 'pausetime': s.pausetime})

            for l in range(0,len(all_loc)):
                if empty_loc[l] == runs:
                    scandata['emptylocs'].append({'lat':  all_loc[l][0], 'lng':  all_loc[l][1]})

            addspawns.task_done()

#########################################################################
#########################################################################
    class smartlocgiver(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            global countmax, countall, empty_thisrun, tries, silent
            all_sort = []

            types = (SPAWN_1x15, SPAWN_1x30, SPAWN_1x45, SPAWN_1x60, SPAWN_2x15, SPAWN_1x60h2, SPAWN_1x60h3, SPAWN_1x60h23, SPAWN_UNDEF, SPAWN_DEF,VSPAWN_2x15,VSPAWN_1x60h2,VSPAWN_1x60h3,VSPAWN_1x60h23)
            type_first_time = (15,30,45,60,15,15,30,15,-1,-1,15,30,15,15)
            typestrs = ('1x15', '1x30', '1x45', '1x60', '2x15', '1x60h2', '1x60h3', '1x60h23', 'UNDEF/DEF')
            typecount = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            tallcount = len(scandata['spawns'])

            pointnum = tallcount
            vleft = 0
            for s in range(0, tallcount):
                spawn = scandata['spawns'][s]
                list_spawns.append(spawn['id'])
                if not spawn['type'] in [SPAWN_UNDEF, SPAWN_DEF]:
                    all_sort.append((spawn['spawntime'], s))
                for t in range(0, len(typecount)):
                    if spawn['type'] == types[t]:
                        typecount[t] += 1
                        break
                if spawn['type'] > 200:
                    vspawn = spawn.copy()
                    vspawn['type'] += 2000
                    if spawn['type'] == SPAWN_2x15 or spawn['type'] == SPAWN_1x60h2:
                        vspawn['spawntime'] = (vspawn['spawntime'] + 2*time_1q) % time_4q
                    elif spawn['type'] == SPAWN_1x60h23 or spawn['type'] == SPAWN_1x60h3:
                        vspawn['spawntime'] = (vspawn['spawntime'] + 3*time_1q) % time_4q

                    scandata['spawns'].append(vspawn)
                    all_sort.append([vspawn['spawntime'], pointnum])
                    pointnum += 1
                    vleft += 1
            typecount[8] += typecount[9]
            pointnum -= typecount[8]

            if not pointnum:
                lprint('[-] Learning file contains no valid spawn points.')
                sys.exit()
            elif typecount[8]:
                lprint('[-] Learning file contains {} undefined spawn points. It is advised to recreate it. This can happen, if you either run into softban issues during the scan (very high range/very high amount of workers/other reasons) or if you\'re not using enough workers for your range.'.format(typecount[8]))

            infostring = 'ID: {}, {}, Range: {}, Start: {}'.format(wID, location_str, HEX_NUM, datetime.fromtimestamp(starttime / 1000.0).strftime('%H:%M:%S'))

            lprint('\n[+] Starting intelligent scan mode.\n')
            lprint('[+] Spawn point count: {}'.format(tallcount))
            for t in range(0, len(typestrs)):
                lprint('[+] Type: {}, Count: {}, Percentage: {}%'.format(typestrs[t], typecount[t], round(100.0 * typecount[t] / tallcount, 2)))

            lprint('\n\n')
            all_sort = sorted(all_sort, key=itemgetter(0))

            indx_sort = 0
            curT = get_time() % time_4q
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
            ignoretime = 5
            while indx_sort != wrapindx:
                spawn = scandata['spawns'][all_sort[indx_sort][1]]
                actT = get_time()
                if (actT-curT) < (actT - all_sort[indx_sort][0]) % 3600000 < (type_first_time[types.index(spawn['type'])]-ignoretime)*60000:
                    addlocation.put((spawn['lat'], spawn['lng']))
                    if spawn['type'] > 2000:
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
                timediff = (all_sort[indx_sort][0] - get_time() - time_hb * 1000) % 3600000
                if timediff < 2*time_1q:
                    if not caughtup:
                        lprint('\n[+] Catch up phase 2/2 complete. Map is now live.')
                        lprint('[+] Time: {}, {}\n'.format(datetime.now().strftime('%H:%M:%S'), infostring))
                        caughtup = True
                        tries = 3
                        actT = get_time()
                    time.sleep(timediff / 1000.0 + safetysecs)
                elif timediff > (time_4q - safetysecs * 1000):
                    time.sleep(timediff/ 1000.0 - 3600 + safetysecs)
                elif timediff < (time_4q - (time_hb + 1) * 1000):
                    lprint('{} s behind.'.format(3600 - safetysecs - round(timediff / 1000.0, 2)))

                spawn = scandata['spawns'][all_sort[indx_sort][1]]
                addlocation.put((spawn['lat'],spawn['lng']))
                if spawn['type'] > 2000:
                    vleft -= 1
                indx_sort += 1
                if indx_sort == pointnum:
                    indx_sort = 0

                if not silent and caughtup and get_time()-actT > time_1q/3 and not verbose:
                    lprint('[+] Switching to silent mode.\n')
                    silent = True


            addlocation.join()
            addforts.join()
            addpokemon.join()
            del scandata['spawns'][tallcount:]
            del all_sort[:]

            for s in range(0, tallcount):
                spawn = scandata['spawns'][s]
                if not spawn['type'] in [SPAWN_UNDEF, SPAWN_DEF]:
                    all_sort.append((spawn['spawntime'], s))
            all_sort = sorted(all_sort, key=itemgetter(0))
            pointnum = tallcount - typecount[8]
            indx_sort = 0
            curT = get_time() % time_4q
            if curT <= all_sort[pointnum-1][0]:
                while curT > all_sort[indx_sort][0]:
                    indx_sort += 1

            lprint('\n[+] Catch up phase, cleanup finished.')
            lprint('[+] Time: {}, {}\n'.format(datetime.now().strftime('%H:%M:%S'), infostring))

            if not silent and not verbose:
                lprint('[+] Switching to silent mode.\n')
                silent = True

            while True:
                timediff = (all_sort[indx_sort][0] - get_time() - time_hb * 1000) % time_4q
                if timediff < 2*time_1q:
                    time.sleep(timediff / 1000.0 + safetysecs)
                elif timediff > (time_4q - safetysecs * 1000):
                    time.sleep(timediff/ 1000.0 - 3600 + safetysecs)
                elif timediff < (time_4q - (time_hb + 1) * 1000):
                    lprint('{} s behind.'.format(3600 - safetysecs - round(timediff / 1000.0, 2)))

                spawn = scandata['spawns'][all_sort[indx_sort][1]]
                addlocation.put((spawn['lat'], spawn['lng']))

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
            global curR, maxR, scannum, countmax, countall, empty_thisrun, starttime, runs, location_str, empty_loc, smartscan, all_scans
            starttime = get_time()
            runs = 0
            try:
                location_str = 'Location: ({})'.format(geolocator.reverse('{},{}'.format(LAT_C, LNG_C)).address)
            except:
                location_str = 'Lat: {}, Lng: {}'.format(LAT_C, LNG_C)

            if smartscan:
                exit()

            maxR = len(all_loc)

            infostring = 'ID: {}, {}, Interval: {} s, Range: {}, Start: {}'.format(wID, location_str, interval, HEX_NUM, datetime.fromtimestamp(starttime / 1000.0).strftime('%H:%M:%S'))

            ##################################################################################################################################################
            while True:
                runs += 1
                curR = 0
                nextperc = percinterval
                nowtime = get_time()

                lprint('\n\n')
                lprint('[+] Run #{}, Time: {}, {}'.format(runs, datetime.fromtimestamp(nowtime / 1000.0).strftime('%H:%M:%S'), infostring))
                for this_loc in all_loc:
                    addlocation.put(this_loc)
                    if (100.0 * curR / maxR) >= nextperc:
                        perc = math.floor((100.0 * curR / maxR) / percinterval) * percinterval
                        lprint('[+] Finished: {} %'.format(perc))
                        nextperc = perc + percinterval

                addlocation.join()
                addforts.join()
                addpokemon.join()
                lprint('[+] Finished: 100 %\n')

                if scan_compromised:
                    lprint('[-] Warning, maximum interval of 15 m was exceeded. It is advised to restart the scan with a smaller range or more workers.\n')

                lprint('[+] {} of {} cells detected as empty during last run.'.format(empty_thisrun, maxR))
                lprint('[+] Non-empty heartbeats reached a maximum of {} retries, allowed: {}.'.format(countmax, tries))
                ave_retries = float(countall) / maxR
                lprint('[+] Average number of retries was {}, total number {}.'.format(round(ave_retries, 2), countall))

                #########################################################################
                countmax = 0
                countall = 0
                empty_thisrun = 0

                list_unique.intersection_update(list_seen)
                list_seen.clear()

                curT = (get_time() - nowtime) / 1000.0
                lprint('[+] Scan Time: {} s'.format(int(round(curT))))

                if scannum > 0:
                    scannum -= 1
                    if scannum == 0:
                        sys.exit()

                #########################################################################
                if nowtime - starttime >= 2700000 and not smartscan:
                    smartscan = True
                    addforts.put(True)
                    addspawns.put((True,True))
                    addspawns.join()
                    try:
                        f = open(scan_file, 'w', 0)
                        json.dump(scandata, f, indent=1, separators=(',', ': '))
                        lprint('[+] Learning file was written.')
                    except Exception as e:
                        lprint('[+] Error while writing learning file, error : {}'.format(e))
                    finally:
                        if 'f' in vars() and not f.closed:
                            f.close()
                    del all_scans
                    if not dumb:
                        del empty_loc
                        del all_loc[:]
                        exit()
                    else:
                        scandata.clear()
                #########################################################################

                curT = max(interval - curT, 0)
                lprint('[+] Sleeping for {} seconds...'.format(int(round(curT))))
                time.sleep(curT)

#########################################################################
#########################################################################
    class collector(threading.Thread):
        def __init__(self, name, account):
            threading.Thread.__init__(self)
            self.account = account

        def run(self):
            global curR, countmax, countall, empty_loc, empty_thisrun, safetysecs

            def emptyheartbeat(heartbeat):
                for cell in heartbeat.map_cells:  # tests if an empty heartbeat was returned
                    if len(cell.ListFields()) > 2:
                        return False
                return True

            do_login(self.account)
            lprint('[{}] Login for {} account: {}'.format(self.account['num'], self.account['type'], self.account['user']))
            lprint('[{}] RPC Session Token: {}'.format(self.account['num'], self.account['access_token']))
            location = LAT_C, LNG_C
            set_api_endpoint(location, self.account)
            lprint('[{}] API endpoint: {}'.format(self.account['num'], self.account['api_url']))
            if acc_tos:
                accept_tos(location, self.account)
            # /////////////////
            synch_li.get()
            synch_li.task_done()

            # ////////////////////
            while True:
                location = addlocation.get()
                h = heartbeat(location, self.account)
                count = 0
                while emptyheartbeat(h) and count < tries:
                    count += 1
                    h = heartbeat(location, self.account)
                if emptyheartbeat(h):
                    if dumb or not smartscan:
                        empty_loc[all_loc.index(location)] += 1
                        empty_thisrun += 1
                    else:
                        lprint('[-] Non-empty cell returned as empty.')
                else:
                    if dumb or not smartscan:
                        empty_loc[all_loc.index(location)] = 0
                        countmax = max(countmax, count)
                        countall += count
                    for cell in h.map_cells:
                        for p in range(0,len(cell.wild_pokemons)):
                            if cell.catchable_pokemons[p].expiration_timestamp_ms == -1:
                                cell.wild_pokemons[p].time_till_hidden_ms = -1
                            addpokemon.put(cell.wild_pokemons[p])
                        if not smartscan:
                            for fort in cell.forts:
                                addforts.put(fort)
                if not smartscan:
                    addspawns.put((location,h))
                    curR += 1
                addlocation.task_done()

#########################################################################
#########################################################################
    class fortjoiner(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
        def run(self):
            fort = addforts.get()
            while not smartscan:
                if fort.id not in list_forts:
                    list_forts.add(fort.id)
                    thisfort = {'id': fort.id, 'lat': fort.latitude, 'lng': fort.longitude}
                    if fort.type == 1:
                        scandata['stops'].append(thisfort)
                    else:
                        scandata['gyms'].append(thisfort)
                addforts.task_done()
                fort = addforts.get()

            addforts.task_done()

#########################################################################
#########################################################################
    class pokejoiner(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)

        def run(self):
            stat_file = '{}/res/spawns{}.txt'.format(workdir, wID)
            POKEMONS = json.load(open('{}/webres/static/{}.json'.format(workdir, LANGUAGE)))
            statheader = 'Name\tid\tSpawnID\tlat\tlng\tspawnTime\tTime\tTime2Hidden\tencounterID\n'

            reappear_texts = ('\n15m later back for 15m','\n15m later back for 30m','\n30m later back for 15m')
            reappear_ind = (0,1,0,2)

            addinfo_phase_sec = (0,time_1q,2*time_1q,time_1q,time_1q)
            addinfo_phase_first = (0,time_1q,time_1q,2*time_1q,time_1q)
            addinfo_pausetime =(0,time_1q,time_1q,time_1q,2*time_1q)

            interval_datwrite = 5
            nextdatwrite = time.time() + interval_datwrite
            init_data()
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

                            mod_tth = wild.time_till_hidden_ms
                            mod_spawntime = 0
                            addinfo = 0
                            if smartscan and not dumb:
                                list_unique.add(wild.encounter_id)
                                if spawnIDint in list_spawns:
                                    spawn = scandata['spawns'][list_spawns.index(spawnIDint)]
                                    if not spawn['type'] in [SPAWN_UNDEF, SPAWN_DEF]:
                                        finished_ms = (wild.last_modified_timestamp_ms - spawn['spawntime']) % time_4q
                                        if spawn['type'] == SPAWN_2x15 and finished_ms < time_1q:
                                            addinfo = 1
                                            mod_phasetime = 2*time_1q
                                        elif spawn['type'] == SPAWN_1x60h2 and finished_ms < time_1q:
                                            addinfo = 2
                                            mod_phasetime = 2*time_1q
                                        elif spawn['type'] == SPAWN_1x60h3 and finished_ms < 2*time_1q:
                                            addinfo = 3
                                            mod_phasetime = 3*time_1q
                                        elif spawn['type'] == SPAWN_1x60h23 and finished_ms < time_1q:
                                            addinfo = 4
                                            mod_phasetime = 2*time_1q
                                        else:
                                            mod_phasetime = time_4q
                                        mod_tth = mod_phasetime - spawn['pausetime'] - finished_ms
                                        if addinfo > 0:
                                            mod_spawntime = wild.last_modified_timestamp_ms + mod_tth - addinfo_phase_first[addinfo]
                                            mod_spawntime_2nd = wild.last_modified_timestamp_ms + mod_tth + addinfo_pausetime[addinfo]
                                        else:
                                            mod_spawntime = wild.last_modified_timestamp_ms - finished_ms
                            if mod_tth > 0:
                                list_unique.add(wild.encounter_id)
                            else:
                                mod_tth = time_1q + 1000
                            if mod_spawntime == 0:
                                mod_spawntime = wild.last_modified_timestamp_ms + mod_tth - time_1q

                            f.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(POKEMONS[wild.pokemon_data.pokemon_id], wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, mod_spawntime,
                                                                                  wild.last_modified_timestamp_ms, mod_tth, wild.encounter_id))
                            if addinfo:
                                f.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(POKEMONS[wild.pokemon_data.pokemon_id], wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, mod_spawntime_2nd,
                                                                                      mod_spawntime_2nd+finished_ms, addinfo_phase_sec[addinfo]-finished_ms, wild.encounter_id))
                            data_buffer.append([wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, int(round((wild.last_modified_timestamp_ms + mod_tth + addinfo_phase_sec[addinfo] + addinfo_pausetime[addinfo]) / 1000.0)) ,addinfo])
                            if not silent:
                                other_ll = LatLng.from_degrees(wild.latitude, wild.longitude)
                                origin_ll = LatLng.from_degrees(LAT_C, LNG_C)
                                diff = other_ll - origin_ll
                                difflat = diff.lat().degrees
                                difflng = diff.lng().degrees
                                distance = int(origin_ll.get_distance(other_ll).radians * 6366468.241830914)
                                direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '') + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')
                                lprint('[+] ({}) {} visible for {} seconds ({}m {} from you)'.format(wild.pokemon_data.pokemon_id, POKEMONS[wild.pokemon_data.pokemon_id], int(mod_tth / 1000.0), distance, direction))

                            if len(PUSHPOKS) > 0 and wild.pokemon_data.pokemon_id in PUSHPOKS:
                                if add_location_name:
                                    try:
                                        location = format_address(geolocator.reverse('{},{}'.format(wild.latitude, wild.longitude)).address, 3)
                                        notification_text = "{} @ {}".format(POKEMONS[wild.pokemon_data.pokemon_id], location)
                                    except:
                                        notification_text = '{} found!'.format(POKEMONS[wild.pokemon_data.pokemon_id])
                                else:
                                    notification_text = '{} found!'.format(POKEMONS[wild.pokemon_data.pokemon_id])
                                disappear_time = datetime.fromtimestamp(int((wild.last_modified_timestamp_ms + mod_tth) / 1000.0)).strftime("%H:%M:%S")
                                time_text = 'disappears at: {} ({}m)'.format(disappear_time, mod_tth / 60000)
                                if addinfo:
                                    time_text += reappear_texts[reappear_ind[addinfo-1]]
                                li = 0
                                while li < len(pb):
                                    try:
                                        pb[li].push_link(notification_text, 'https://maps.google.com/?ll={},{}&q={},{}&z=14'.format(wild.latitude, wild.longitude,wild.latitude, wild.longitude), body=time_text)
                                    except requests.ConnectionError as e:
                                        if re.search('Connection aborted', str(e)) is None:
                                            lprint('[-] Connection Error during Pushbullet, error: {}'.format(e))
                                    except pushbullet.PushbulletError as e:
                                        if e['error_code'] == "pushbullet_pro_required":
                                            lprint('[-] Pushbullet Error: "free limit exceeded", {} is removed from future notifications.'.format(pb[li]))
                                            pb.pop(li)
                                            li -= 1
                                        else:
                                            lprint('[-] Pushbullet Error: {}'.format(e))
                                    except Exception as e:
                                        lprint('[-] Pushbullet Error: {}'.format(e))
                                    li += 1

                                for telegram in telegrams:
                                    try:
                                        telebot.sendMessage(chat_id=telegram, text='<b>' + notification_text + '</b>\n' + time_text, parse_mode='HTML', disable_web_page_preview='False', disable_notification='False')
                                        telebot.sendLocation(chat_id=telegram, latitude=wild.latitude, longitude=wild.longitude)
                                    except Exception as e:
                                        print('[-] Connection Error during Telegram, error: {}'.format(e))
                            if addpokemon.empty() and time.time() < nextdatwrite:
                                time.sleep(1)
                            if addpokemon.empty() or time.time() >= nextdatwrite:
                                update_data()
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
    global all_loc, empty_loc, all_scans, signature_lib, locktime, addlocation, synch_li, smartscan

    def signal_handler(signal, frame):
        sys.exit()
    signal.signal(signal.SIGINT, signal_handler)

    time_1q = 900000
    time_4q = 4 * time_1q

    signature_lib = ctypes.cdll.LoadLibrary(get_encryption_lib_path())
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

    scan_file = '{}/res/{}_{}_{}_{}.json'.format(workdir, LAT_C, LNG_C, HEX_NUM, HEX_R)
    try:
        f = open(scan_file, 'r')
        scandata = json.load(f)
        if not dumb:
            smartscan = True
    except Exception as e:
        smartscan = False
        lprint('[+] Can\'t load location database file: {}.'.format(e))
        lprint('[+] After a learning phase of one hour this file will be created and it\'ll make subsequent scans with the same parameters very efficient.\n')
        scandata = {'parameters': {'lat': LAT_C, 'lng': LNG_C, 'range': HEX_NUM, 'sight': HEX_R}, 'emptylocs': [], 'spawns': [], 'stops': [], 'gyms': []}
    finally:
        if 'f' in vars() and not f.closed:
            f.close()

    latrad = LAT_C * math.pi / 180
    HEX_M = 3.0 ** 0.5 / 2.0 * HEX_R

    x_un = 1.5 * HEX_R / getEarthRadius(latrad) / math.cos(latrad) * safety * 180 / math.pi
    y_un = 1.0 * HEX_M / getEarthRadius(latrad) * safety * 180 / math.pi

    # yvals = [0, -(HEX_NUM * 3 + 1), 1,HEX_NUM * 3 + 2, HEX_NUM * 3 + 1, -1, -(HEX_NUM * 3 + 2)]
    # xvals = [0, HEX_NUM + 1, 2 * HEX_NUM + 1, HEX_NUM, -(HEX_NUM + 1), -(2 * HEX_NUM + 1), -(HEX_NUM)]
    #
    # for n in range(0,7):
    #     lprint('Neighbor {}\t{}, {}'.format(n,LAT_C+y_un*yvals[n],LNG_C+x_un*xvals[n]))
    # sys.exit()

    if not smartscan:
        all_loc = [(LAT_C, LNG_C)]
        empty_loc = []
        all_scans = []

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

                    all_loc.append((lat, lng))

        empty_loc = [0] * len(all_loc)

        lprint('[+] Distributing {} locations to {} threads.'.format(len(all_loc), threadnum))
        runtime = float(len(all_loc) * time_hb) / threadnum
        lprint('[+] Time for each run can vary between {} s (urban) and {} s (rural).'.format(int(round(math.floor(runtime))), int(round(math.ceil(2 * runtime + time_hb)))))
        lprint('[+] If it\'s higher than 600 s (720 s, if you feel lucky), consider adding more workers or reducing the range.\n')
        time.sleep(5)

        for location in all_loc:
            all_scans.append(scan(location))
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

    for i in range(0, threadnum):
        newthread = collector(i, accounts[i])
        newthread.daemon = True
        newthread.start()
        threadList.append(newthread)
        if not login_simu:
            while not synch_li.empty():
                synch_li.put(True)
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
