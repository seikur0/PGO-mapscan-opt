from flask import Flask, render_template, g, request, jsonify
from flask_compress import Compress
import os, sys
import logging
import socket
import SocketServer
import BaseHTTPServer
import signal
import time
import json
import sqlite3

workdir = os.path.dirname(os.path.realpath(__file__))
data_file = '{}/webres/data.db'.format(workdir)
settings_file = '{}/res/usersettings.json'.format(workdir)
exclude_ids = None

def signal_handler(signal, frame):
    sys.exit()
signal.signal(signal.SIGINT, signal_handler)

def isnotExcluded(id):
    return not (id in exclude_ids)


def server_start():
    global exclude_ids
    try:
        f = open(settings_file, 'r')
        try:
            allsettings = json.load(f)
        except ValueError as e:
            print('[-] Error: The settings file is not in a valid format, {}'.format(e))
            f.close()
            sys.exit()
        f.close()
    finally:
        if 'f' in vars() and not f.closed:
            f.close()

    exclude_ids = allsettings['exclude_ids']
    port = allsettings['port']
    if allsettings['icon_set'] == 'standard':
        icon_set = 'icons_gen1_standard.png'
    elif allsettings['icon_set'] == 'shuffle':
        icon_set = 'icons_gen1_shuffle.png'
    elif allsettings['icon_set'] == 'alt':
        icon_set = 'icons_gen1_alt.png'
    elif allsettings['icon_set'] == 'toon':
        icon_set = 'icons_gen1_toon.png'
    else:
        print('[-] Error: Icon set in settings file is invalid, possible sets are: "standard", "shuffle", "toon", "alt".')
    list_profiles = []
    list_lats = []
    list_lngs = []
    for i in range(0, len(allsettings['profiles'])):
        if allsettings['profiles'][i]['id'] not in list_profiles:
            list_profiles.append(allsettings['profiles'][i]['id'])
            list_lats.append(allsettings['profiles'][i]['coordinates']['lat'])
            list_lngs.append(allsettings['profiles'][i]['coordinates']['lng'])

    if len(list_profiles) == 0:
        print('[-] Error: No profiles in settings file.')
        sys.exit()
    else:
        main_ind = 0

    def patched_finish(self):
        try:
            if not self.wfile.closed:
                self.wfile.close()
        except socket.error as e:
            sys.stdout.write('socket error: {}\n'.format(e))
        self.rfile.close()
    SocketServer.StreamRequestHandler.finish = patched_finish
    BaseHTTPServer.HTTPServer.allow_reuse_address = False

    compress = Compress()
    app = Flask(__name__,template_folder=workdir+'/'+'webres',static_url_path='/static',static_folder=workdir+'/webres/static')
    app.config['COMPRESS_MIN_SIZE'] = 0
    app.config['COMPRESS_LEVEL'] = 6
    app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript', 'application/octet-stream', 'image/svg+xml']
    compress.init_app(app)

    def get_db():
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(data_file)
        return db

    @app.teardown_appcontext
    def close_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    @app.after_request
    def add_header(response):
        if response.headers['Content-Type'] == "image/png":
            response.headers['Cache-Control'] = 'must-revalidate, public, max-age=86400'
        else:
            response.headers['Cache-Control'] = 'must-revalidate, public, max-age=-1'
        return response

    @app.route('/_getdata')
    def add_numbers():
        datatill = request.args.get('data_till', 0, type=int)
        profile = request.args.get('profile', -1, type=int)
        db = get_db()
        timenow = int(round(time.time(),0))
        db.create_function("isnotExcluded", 1, isnotExcluded)
        with db:
            cursor = db.cursor()
            if profile == -1:
                results = cursor.execute('SELECT spawnid, latitude, longitude, spawntype, pokeid, expiretime FROM spawns WHERE isnotExcluded(pokeid) AND (expiretime > ?) AND (fromtime >= ?)',(timenow,datatill))
            else:
                results = cursor.execute('SELECT spawnid, latitude, longitude, spawntype, pokeid, expiretime FROM spawns WHERE isnotExcluded(pokeid) AND (profile == ?) AND (expiretime > ?) AND (fromtime >= ?)', (profile,timenow, datatill))

        return jsonify([timenow,results.fetchall()])

    @app.route("/")
    def mainapp():
        return render_template('index.html',api_key=allsettings['api_key'],icon_scalefactor=allsettings['icon_scalefactor'],mobile_scale=allsettings['mobile_scalefactor'],lat=list_lats[main_ind],lng=list_lngs[main_ind],language=allsettings['language'],icon_set = icon_set, profile=-1)

    @app.route("/id<int:profile>")
    def subapp(profile):
        if profile in list_profiles:
            sub_ind = list_profiles.index(profile)
            return render_template('index.html', api_key=allsettings['api_key'], icon_scalefactor=allsettings['icon_scalefactor'], mobile_scale=allsettings['mobile_scalefactor'],lat=list_lats[sub_ind],lng=list_lngs[sub_ind], language=allsettings['language'], icon_set = icon_set, profile=profile)

    while True:
        try:
            app.run(host='0.0.0.0', port=port, threaded=True)
        except socket.error as e:
            if e.errno == 10048:
                print('[-] Error: The specified port {} is already in use.'.format(port))
                break

if __name__ == "__main__":
    server_start()
