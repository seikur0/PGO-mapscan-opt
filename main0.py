import requests
import re
import json
import argparse

import POGOProtos
import POGOProtos.Data_pb2
import POGOProtos.Enums_pb2
import POGOProtos.Inventory_pb2
import POGOProtos.Map_pb2
import POGOProtos.Settings_pb2
import POGOProtos.Networking
import POGOProtos.Networking.Envelopes_pb2
import POGOProtos.Networking.Requests_pb2
import POGOProtos.Networking.Responses_pb2
import POGOProtos.Networking.Requests
import POGOProtos.Networking.Requests.Messages_pb2

import time
from datetime import datetime
import sys
import math

from s2sphere import CellId, LatLng
from gpsoauth import perform_master_login, perform_oauth
from shutil import move

def getNeighbors():
    origin = CellId.from_lat_lng(LatLng.from_degrees(FLOAT_LAT, FLOAT_LNG)).parent(15)

    level = 15
    max_size = 1 << 30
    size = origin.get_size_ij(level)

    face, i, j = origin.to_face_ij_orientation()[0:3]

    walk=  [origin.id(),
            origin.from_face_ij_same(face, i, j - size, j - size >= 0).parent(level).id(),
            origin.from_face_ij_same(face, i, j + size, j + size < max_size).parent(level).id(),
            origin.from_face_ij_same(face, i - size, j, i - size >= 0).parent(level).id(),
            origin.from_face_ij_same(face, i + size, j, i + size < max_size).parent(level).id(),
            origin.from_face_ij_same(face, i - size, j - size, j - size >= 0 and i - size >=0).parent(level).id(),
            origin.from_face_ij_same(face, i + size, j - size, j - size >= 0 and i + size < max_size).parent(level).id(),
            origin.from_face_ij_same(face, i - size, j + size, j + size < max_size and i - size >=0).parent(level).id(),
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
SESSION = requests.session()
SESSION.verify = False
NET_MAXWAIT = 30
LOGIN_MAXWAIT = 30
MAXWAIT = LOGIN_MAXWAIT

FLOAT_LAT = None
FLOAT_LNG = None
FLOAT_ALT = None
EARTH_Rmax = 6378137.0
EARTH_Rmin = 6356752.3
HEX_R = 100.0 #range of detection for pokemon = 100m
HEX_M = 3.0**(0.5)/2.0*HEX_R
safety=0.999

LOGGING = False
DATA = []
UPLOAD = []

F_LIMIT = None
LANGUAGE = None
HEX_NUM = None
wID = None
interval = None

LI_TYPE=None
li_user=None
li_password=None
LAT_C,LNG_C,ALT_C = [None,None,None]

api_endpoint = None
access_token = None
response = {}
r = None


SETTINGS_FILE='res/usersettings.json'

def do_settings():
    global LANGUAGE
    global li_user
    global li_password
    global LI_TYPE
    global LAT_C,LNG_C,ALT_C
    global wID
    global HEX_NUM
    global interval
    global F_LIMIT

    parser = argparse.ArgumentParser()
    parser.add_argument("-id", "--id", help="worker id")
    parser.add_argument("-r", "--range", help="scan range")
    parser.add_argument("-t", "--timeinterval", help="time interval")
    parser.add_argument("-lt", "--logintype", help="ptc or google")
    parser.add_argument("-u", "--username", help="username")
    parser.add_argument("-p", "--password", help="password")
    parser.add_argument("-lat", "--latitude", help="latitude")
    parser.add_argument("-lng", "--longitude", help="longitude")
    parser.add_argument("-alt", "--altitude", help="altitude")
    args = parser.parse_args()
    wID=args.id
    HEX_NUM=args.range
    interval=args.timeinterval
    LI_TYPE=args.logintype
    li_user=args.username
    li_password=args.password
    LAT_C=args.latitude
    LNG_C=args.longitude
    ALT_C=args.altitude

    if wID is None:
        wID=0
    else:
        wID=int(wID)

    try:
        f = open(SETTINGS_FILE, 'r')
        try:
            allsettings=json.load(f)
        except ValueError as e:
            print("[-] Error: The settings file is not in a valid format, {}".format(e))
            f.close()
            sys.exit()
    finally:
        f.close()

    LANGUAGE=allsettings['language']
    idlist=[]
    for i in range(0,len(allsettings['profiles'])):
        idlist.append(allsettings['profiles'][i]['id'])

    if wID in idlist:
        tID=idlist.index(wID)
        if LI_TYPE is None:
            LI_TYPE=allsettings['profiles'][tID]['type']
        if li_user is None:
            li_user=allsettings['profiles'][tID]['username']
        if li_password is None:
            li_password=allsettings['profiles'][tID]['password']
    else:
        print("[-] Error: No profile exists for the set id.")
        sys.exit()

    if HEX_NUM is None:
        HEX_NUM=allsettings['range']
    else:
        HEX_NUM=int(HEX_NUM)
    if interval is None:
        interval=allsettings['scaninterval']
    else:
        interval=int(interval)

    if allsettings['unique_coordinates'] and not allsettings['centralscan']:
        if LAT_C is None:
            LAT_C = allsettings['profiles'][tID]['coordinates']['lat']
        else:
            LAT_C = float(LAT_C)
        if LNG_C is None:
            LNG_C = allsettings['profiles'][tID]['coordinates']['lng']
        else:
            LNG_C = float(LNG_C)
        if ALT_C is None:
            ALT_C = allsettings['profiles'][tID]['coordinates']['alt']
        else:
            ALT_C = float(ALT_C)
    else:
        if LAT_C is None:
            LAT_C = allsettings['standard_coordinates']['lat']
        else:
            LAT_C = float(LAT_C)
        if LNG_C is None:
            LNG_C = allsettings['standard_coordinates']['lng']
        else:
            LNG_C = float(LNG_C)
        if ALT_C is None:
            ALT_C = allsettings['standard_coordinates']['alt']
        else:
            ALT_C = float(ALT_C)

    if allsettings['centralscan']:
        centralscan_location()
    else:
        set_location_coords(LAT_C,LNG_C,ALT_C)
    F_LIMIT=int(allsettings['backup_size']*1024*1024)
    if F_LIMIT==0:
        F_LIMIT=9223372036854775807

def prune_data():
    # prune despawned pokemon
    cur_time = int(time.time())
    for i, poke in reversed(list(enumerate(DATA))):
        if cur_time>poke['despawnTime']:
            DATA.pop(i)

def write_data_to_file(DATA_FILE):
    try:
        f = open(DATA_FILE, 'w')
        json.dump(DATA, f, indent=2)
    finally:
        f.close()

def write_upload_to_file(UPLOAD_FILE):
    try:
        f = open(UPLOAD_FILE, 'a')
        while len(UPLOAD) > 0:
            obj = UPLOAD.pop()
            out = json.dumps(obj, separators=(',', ':'))
            f.write(out + '\n')
    finally:
        f.close()

def add_pokemon(pokeId, spawnID, lat, lng, despawnT):
    DATA.append({
        'id': pokeId,
        'spawnID': spawnID,
        'lat': lat,
        'lng': lng,
        'despawnTime': despawnT,
    });

def log_pokemon(pokeID, spawnID, lat, lng, encID, timestamp, despawn):
    data = {
        'pokemon_id':pokeID,
        'last_modified_timestamp_ms': timestamp,
        'time_till_hidden_ms':despawn,
        'encounter_id': encID,
        'spawnpoint_id': spawnID,
        'longitude': lng,
        'latitude': lat
    }
    UPLOAD.append(data)

def getEarthRadius(latrad):
    return (1.0/(((math.cos(latrad))/EARTH_Rmax)**(2) + ((math.sin(latrad))/EARTH_Rmin)**(2)))**(1.0/2)

def set_location_coords(lat, lng, alt):
    global FLOAT_LAT, FLOAT_LNG, FLOAT_ALT
    FLOAT_LAT = lat
    FLOAT_LNG = lng
    FLOAT_ALT = alt

def centralscan_location():
    latrad=LAT_C*math.pi/180

    a=(HEX_NUM+0.5)
    x_un=1.5*HEX_R/getEarthRadius(latrad)/math.cos(latrad)*safety*a*180/math.pi
    y_un=3.0*HEX_M/getEarthRadius(latrad)*safety*a*180/math.pi
    xmod=[0,1,2,1,-1,-2,-1]
    ymod=[0,-1,0,1,1,0,-1]
    lat = LAT_C+ymod[wID]*y_un
    lng = LNG_C+xmod[wID]*x_un

    set_location_coords(lat,lng,ALT_C)

def login_google(username,password):
    global access_token
    global login_type

    ANDROID_ID='9774d56d682e549c'
    SERVICE='audience:server:client_id:848232511240-7so421jotr2609rmqakceuu1luuq0ptb.apps.googleusercontent.com'
    APP='com.nianticlabs.pokemongo'
    APP_SIG='321187995bc7cdc2b5fc91b11a96e2baa8602c62'

    while True:
        try:
            retry_after=1
            login1 = perform_master_login(username, password, ANDROID_ID)
            while login1.get('Token') is None:
                print('[-] Google Login error, retrying in {} seconds (step 1)'.format(retry_after))
                time.sleep(retry_after)
                retry_after=min(retry_after*2,MAXWAIT)
                login1 = perform_master_login(username, password, ANDROID_ID)

            retry_after=1
            login2 = perform_oauth(username, login1.get('Token'), ANDROID_ID, SERVICE, APP, APP_SIG)
            while login2.get('Auth') is None:
                print('[-] Google Login error, retrying in {} seconds (step 2)'.format(retry_after))
                time.sleep(retry_after)
                retry_after=min(retry_after*2,MAXWAIT)
                login2 = perform_oauth(username, login1.get('Token', ''), ANDROID_ID, SERVICE, APP, APP_SIG)

            access_token = login2['Auth']
            return
        except Exception as e:
            print('[-] Unexpected google login error: {}'.format(e))
            print('[-] Retrying...')
            time.sleep(2)

def login_ptc(username, password):
    global access_token
    global login_type

    LOGIN_URL = 'https://sso.pokemon.com/sso/login?service=https%3A%2F%2Fsso.pokemon.com%2Fsso%2Foauth2.0%2FcallbackAuthorize'
    LOGIN_OAUTH = 'https://sso.pokemon.com/sso/oauth2.0/accessToken'

    while True:
        try:
            #SESSION.headers.update({'User-Agent': 'Niantic App'})
            SESSION.headers.update({'User-Agent': 'niantic'})
            r = SESSION.get(LOGIN_URL)
            retry_after=1
            while r.status_code!=200:
                print('[-] Connection error {}, retrying in {} seconds (step 1)'.format(r.status_code,retry_after))
                time.sleep(retry_after)
                retry_after=min(retry_after*2,MAXWAIT)
                r = SESSION.get(LOGIN_URL)


            jdata = json.loads(r.content)
            data = {
                'lt': jdata['lt'],
                'execution': jdata['execution'],
                '_eventId': 'submit',
                'username': username,
                'password': password,
            }
            r = SESSION.post(LOGIN_URL, data=data)
            retry_after=1

            while r.status_code!=500 and r.status_code!=200:
                print('[-] Connection error {}, retrying in {} seconds (step 2)'.format(r.status_code,retry_after))
                time.sleep(retry_after)
                retry_after=min(retry_after*2,MAXWAIT)
                r = SESSION.post(LOGIN_URL, data=data)

            ticket = None
            ticket = re.sub('.*ticket=', '', r.history[0].headers['Location'])
            data1 = {
                'client_id': 'mobile-app_pokemon-go',
                'redirect_uri': 'https://www.nianticlabs.com/pokemongo/error',
                'client_secret': 'w8ScCUXJQc6kXKw8FiOhd8Fixzht18Dq3PEVkUCP5ZPxtgyWsbTvWHFLm2wNY0JR',
                'grant_type': 'refresh_token',
                'code': ticket,
            }
            r = SESSION.post(LOGIN_OAUTH, data=data1)
            while r.status_code!=200:
                print('[-] Connection error {}, retrying in {} seconds (step 3)'.format(r.status_code,retry_after))
                time.sleep(retry_after)
                retry_after=min(retry_after*2,MAXWAIT)
                r = SESSION.post(LOGIN_OAUTH, data=data1)

            access_token = re.sub('&expires.*', '', r.content)
            access_token = re.sub('.*access_token=', '', access_token)
            return

        except Exception as e:
            print('[-] Unexpected ptc login error: {}'.format(e))
            if r is not None:
                print('[-] Connection error, http code: {}'.format(r.status_code))
            else:
                print('[-] Error happened before network request.')
            print('[-] Retrying...')
            time.sleep(2)

def do_login():
    if LI_TYPE=='ptc':
        print('[+] login for ptc account: {}'.format(li_user))
        login_ptc(li_user,li_password)
    elif LI_TYPE=='google':
        print('[+] login for google account: {}'.format(li_user))
        login_google(li_user,li_password)
    else:
        print("[-] Error: Login type should be either ptc or google.")
        sys.exit()

def api_req(api_endpoint, access_token, *mehs, **kw):
    r=None;
    while True:
        try:
            p_req = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope()
            p_req.request_id = 1469378659230941192

            p_req.status_code = POGOProtos.Networking.Envelopes_pb2.GET_PLAYER

            p_req.latitude, p_req.longitude, p_req.altitude = (FLOAT_LAT, FLOAT_LNG, FLOAT_ALT)

            p_req.unknown12 = 989 #transaction id, anything works
            if 'useauth' not in kw or not kw['useauth']:
                p_req.auth_info.provider = LI_TYPE
                p_req.auth_info.token.contents = access_token
                p_req.auth_info.token.unknown2 = 14
            else:
                p_req.auth_ticket.start = kw['useauth'].start
                p_req.auth_ticket.expire_timestamp_ms = kw['useauth'].expire_timestamp_ms
                p_req.auth_ticket.end = kw['useauth'].end

            for meh in mehs:
                p_req.MergeFrom(meh)
            protobuf = p_req.SerializeToString()
            r = SESSION.post(api_endpoint, data=protobuf, verify=False)

            retry_after=1
            while r.status_code!=200:
                print('[-] Connection error {}, retrying in {} seconds'.format(r.status_code,retry_after))
                time.sleep(retry_after)
                retry_after=min(retry_after*2,MAXWAIT)
                r = SESSION.post(api_endpoint, data=protobuf, verify=False)

            p_ret = POGOProtos.Networking.Envelopes_pb2.ResponseEnvelope()
            p_ret.ParseFromString(r.content)
            return p_ret

        except Exception as e:
            print('[-] Unexpected connection error, error: {}'.format(e))
            if r is not None:
                print('[-] Unexpected connection error, http code: {}'.format(r.status_code))
            else:
                print('[-] Error happened before network request.')
            print('[-] Retrying...')
            time.sleep(2)

def get_profile(access_token, api, useauth, *reqq):
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

    newResponse = api_req(api, access_token, req, useauth = useauth)

    retry_after=0.26
    while newResponse.status_code not in [1,2,53,102]: #1 for hearbeat, 2 for profile authorization, 53 for api endpoint, 52 for error, 102 session token invalid
        print('[-] Response error, status code: {}, retrying in {} seconds'.format(newResponse.status_code,retry_after))
        time.sleep(retry_after)
        retry_after=min(retry_after*2,MAXWAIT)
        newResponse = api_req(api, access_token, req, useauth = useauth)

    return newResponse

def set_api_endpoint():
    global api_endpoint
    p_ret = get_profile(access_token, API_URL, None)
    while p_ret.status_code==102:
        print('[-] Error, invalid session, retrying...')
        time.sleep(300) #at that point the severs are pretty much done for, so waiting for 5 min
        p_ret = get_profile(access_token, API_URL, None)

    api_endpoint = ('https://%s/rpc' % p_ret.api_url)

def authorize_profile():
    global response
    response = get_profile(access_token, api_endpoint, None)

def heartbeat():
    while True:
        lastR_t = int(time.time()*1000)
        m5 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
        #m5.request_type = POGOProtos.Networking.Envelopes_pb2.DOWNLOAD_SETTINGS
        m51 = POGOProtos.Networking.Requests.Messages_pb2.DownloadSettingsMessage()
        m51.hash = "05daf51635c82611d1aac95c0b051d3ec088a930"
        m5.request_message = m51.SerializeToString()

        m4 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
        #m4.request_type = POGOProtos.Networking.Envelopes_pb2.CHECK_AWARDED_BADGES
        #m41 = POGOProtos.Networking.Requests.Messages_pb2.CheckAwardedBadgesMessage()


        m3 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
        #m3.request_type = POGOProtos.Networking.Envelopes_pb2.GET_INVENTORY
        m31 = POGOProtos.Networking.Requests.Messages_pb2.GetInventoryMessage()
        m31.last_timestamp_ms = lastR_t
        m3.request_message = m31.SerializeToString()


        m2 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
        #m2.request_type = POGOProtos.Networking.Envelopes_pb2.GET_HATCHED_EGGS
        #m21 = POGOProtos.Networking.Requests.Messages_pb2.GetHatchedEggsMessage()


        m1 = POGOProtos.Networking.Envelopes_pb2.RequestEnvelope().requests.add()
        m1.request_type = POGOProtos.Networking.Envelopes_pb2.GET_MAP_OBJECTS
        m11 = POGOProtos.Networking.Requests.Messages_pb2.GetMapObjectsMessage()

        walk = sorted(getNeighbors())
        m11.cell_id.extend(walk)

        m11.since_timestamp_ms.extend([0]*len(walk))
        m11.latitude = FLOAT_LAT
        m11.longitude = FLOAT_LNG
        m1.request_message = m11.SerializeToString()
        newResponse = get_profile(access_token, api_endpoint, response.auth_ticket, m1, m2, m3, m4, m5)
        if newResponse.status_code==1:
            payload = newResponse.returns[0]
            heartbeat = POGOProtos.Networking.Responses_pb2.GetMapObjectsResponse()
            heartbeat.ParseFromString(payload)
            return heartbeat
        elif newResponse.status_code==2:
            authorize_profile()
        elif newResponse.status_code==102:
            print('[-] Error, refreshing login')
            do_login()
            set_api_endpoint()
            authorize_profile()
        else:
            print('[-] Heartbeat error, status code: {}'.format(newResponse.status_code)) #should not happen, probably unused
            print('[-] Retrying...')
            time.sleep(2)

def fixNum(int_type):
    length = 0
    int_ret = ~int_type
    while (int_ret):
        int_ret >>= 1
        length += 1
    int_ret = int_type ^ (-1 << length)
    return int_ret

def statfile_new(statfile):
    try:
        f=open(statfile,'a')
        if f.tell()==0:
            f.write('Name\tid\tSpawnID\tlat\tlng\tspawnTime\tTime\tTime2Hidden\tencounterID\n')
    finally:
        f.close()

def main():
    global MAXWAIT

    do_settings()

    DATA_FILE = 'res/data{}.json'.format(wID)
    UPLOAD_FILE = 'res/upload{}.log'.format(wID)
    STAT_FILE = 'res/spawns{}.json'.format(wID)
    pokemons = json.load(open('res/'+LANGUAGE+'.json'))

    do_login()
    print('[+] RPC Session Token: {}'.format(access_token))

    set_api_endpoint()
    print('[+] API endpoint: {}'.format(api_endpoint))
    authorize_profile()
    print('[+] Login successful')

    payload = response.returns[0]
    profile = POGOProtos.Networking.Responses_pb2.GetPlayerResponse()
    profile.ParseFromString(payload)

    print('[+] Username: {}'.format(profile.player_data.username))

    creation_time = datetime.fromtimestamp(int(profile.player_data.creation_timestamp_ms)/1000)
    print('[+] You are playing Pokemon Go since: {}'.format(creation_time.strftime('%Y-%m-%d %H:%M:%S')))
    for curr in profile.player_data.currencies:
        print('[+] {}: {}'.format(curr.name, curr.amount))

    MAXWAIT=NET_MAXWAIT
    origin = LatLng.from_degrees(FLOAT_LAT, FLOAT_LNG)
    all_ll = [origin]
    maxR = 1;

    for a in range(1,HEX_NUM+1):
        for i in range(0,a*6):
            latrad = origin.lat().radians

            x_un=1.5*HEX_R/getEarthRadius(latrad)/math.cos(latrad)*safety*180/math.pi
            y_un=1.0*HEX_M/getEarthRadius(latrad)*safety*180/math.pi
            if i < a:
                lat = FLOAT_LAT+y_un*(-2*a+i)
                lng = FLOAT_LNG+x_un*i
            elif i < 2*a:
                lat = FLOAT_LAT+y_un*(-3*a+2*i)
                lng = FLOAT_LNG+x_un*a
            elif i < 3*a:
                lat = FLOAT_LAT+y_un*(-a+i)
                lng = FLOAT_LNG+x_un*(3*a-i)
            elif i < 4*a:
                lat = FLOAT_LAT+y_un*(5*a-i)
                lng = FLOAT_LNG+x_un*(3*a-i)
            elif i < 5*a:
                lat = FLOAT_LAT+y_un*(9*a-2*i)
                lng = FLOAT_LNG+x_un*-a
            else:
                lat = FLOAT_LAT+y_un*(4*a-i)
                lng = FLOAT_LNG+x_un*(-6*a+i)

            all_ll.append(LatLng.from_degrees(lat,lng))
            maxR+=1;

    #/////////////////

    #////////////////////
    print('')
    statfile_new(STAT_FILE)

    seen = set([])
    uniqueE = set([])
    backup = False
    while True:
        curT=int(time.time())
        #curR=0;
        print("[+] Time: " + datetime.now().strftime("%H:%M:%S"))
        try:
            f= open(STAT_FILE,'a',1)
            for this_ll in all_ll:
                #if LOGGING:
                    #print('[+] Finished: '+str(100.0*curR/maxR)+' %')
                #curR+=1
                set_location_coords(this_ll.lat().degrees, this_ll.lng().degrees, ALT_C)
                h = heartbeat()

                for cell in h.map_cells:
                    for wild in cell.wild_pokemons:
                        if (wild.encounter_id not in seen):
                            seen.add(wild.encounter_id)
                            if (wild.encounter_id not in uniqueE):
                                spawnIDint=int(wild.spawn_point_id, 16)
                                org_tth=wild.time_till_hidden_ms
                                if wild.time_till_hidden_ms < 0:
                                    wild.time_till_hidden_ms=901000
                                else:
                                    uniqueE.add(wild.encounter_id)

                                f.write('{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n'.format(pokemons[wild.pokemon_data.pokemon_id],wild.pokemon_data.pokemon_id,spawnIDint,wild.latitude,wild.longitude,(wild.last_modified_timestamp_ms+wild.time_till_hidden_ms)/1000.0-900.0,wild.last_modified_timestamp_ms/1000.0,org_tth/1000.0,wild.encounter_id))
                                add_pokemon(wild.pokemon_data.pokemon_id,spawnIDint, wild.latitude, wild.longitude, int((wild.last_modified_timestamp_ms+wild.time_till_hidden_ms)/1000.0))
                                log_pokemon(wild.pokemon_data.pokemon_id, spawnIDint, wild.latitude, wild.longitude, wild.encounter_id, wild.last_modified_timestamp_ms, wild.time_till_hidden_ms)

                                if LOGGING:
                                    other = LatLng.from_degrees(wild.latitude, wild.longitude)
                                    diff = other - origin
                                    difflat = diff.lat().degrees
                                    difflng = diff.lng().degrees
                                    direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '')  + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')
                                    print("<<>> (%s) %s visible for %s seconds (%sm %s from you)" % (wild.pokemon_data.pokemon_id, pokemons[wild.pokemon_data.pokemon_id], int(wild.time_till_hidden_ms/1000.0), int(origin.get_distance(other).radians * 6366468.241830914), direction))
                    write_upload_to_file(UPLOAD_FILE)
                write_data_to_file(DATA_FILE)
                #if LOGGING:
                    #print('')
            if f.tell()>F_LIMIT:
                backup=True
        finally:
            f.close()

        uniqueE=uniqueE & seen
        seen.clear()

        if backup:
            print('[+] File size is over the set limit, doing backup.')
            move(STAT_FILE,STAT_FILE[:-5]+'.'+time.strftime('%Y%m%d_%H%M')+'.json')
            statfile_new(STAT_FILE)
            backup=False

        curT = int(time.time())-curT
        print('[+] Scan Time: {} s'.format(curT))
        curT=max(interval-curT,0)
        print('[+] Sleeping for {} seconds...'.format(curT))
        time.sleep(curT)
        prune_data()
if __name__ == '__main__':
    main()
