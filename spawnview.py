from flask import Flask, render_template, g, request, jsonify
from flask_compress import Compress
import os, sys
import socket
import SocketServer
import BaseHTTPServer
import signal
from s2sphere import CellId, LatLng, Cell, MAX_AREA, Point, LatLngRect, RegionCoverer
import res.maplib as mapl
import json
import threading

workdir = os.path.dirname(os.path.realpath(__file__))
plandir = workdir + '/res/learning/learn_plans/new'

EARTH_R = 6371000.0
EARTH_Rmax = 6378137.0
EARTH_Rmin = 6356752.3

max_size = 1 << 30
lvl_big = 10
lvl_small = 17
HEX_R = 70.0
safety = 0.999
safety_border = 0.9

def signal_handler(signal, frame):
    sys.exit()
signal.signal(signal.SIGINT, signal_handler)

def patched_finish(self):
    try:
        if not self.wfile.closed:
            self.wfile.close()
    except socket.error as e:
        sys.stdout.write('socket error: {}\n'.format(e))
    self.rfile.close()

SocketServer.StreamRequestHandler.finish = patched_finish
BaseHTTPServer.HTTPServer.allow_reuse_address = False

def server_start():
    list_plans = []
    port = 8000

    lock_plans = threading.Lock()

    compress = Compress()
    app = Flask(__name__,template_folder=workdir+'/'+'webres',static_url_path='/static',static_folder=workdir+'/webres/static')
    app.config['COMPRESS_MIN_SIZE'] = 0
    app.config['COMPRESS_LEVEL'] = 6
    app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript', 'application/octet-stream', 'image/svg+xml']
    compress.init_app(app)

    @app.after_request
    def add_header(response):
        if response.headers['Content-Type'] == "image/png":
            response.headers['Cache-Control'] = 'must-revalidate, public, max-age=86400'
        else:
            response.headers['Cache-Control'] = 'must-revalidate, public, max-age=-1'
        return response

    @app.route('/_remove_plan')
    def remove_plan():
        location = (request.args.get('lat', type=float), request.args.get('lng', type=float))
        cid = CellId.from_lat_lng(LatLng.from_degrees(location[0],location[1])).parent(lvl_big)
        token = cid.to_token()

        lock_plans.acquire()
        if token in list_plans:
            list_plans.pop(list_plans.index(token))
        lock_plans.release()
        return jsonify("")

    @app.route('/_write_plans')
    def writeplans():
        subplans = request.args.get('subplans', type=int)
        plans = []
        lock_plans.acquire()
        for token in list_plans:
            center = LatLng.from_point(Cell(CellId.from_token(token)).get_center())
            center = (center.lat().degrees, center.lng().degrees)
            for ind_sub in range(1,subplans+1):
                plans.append({'type': 'seikur0_s2', 'token': token, 'location': [center[0],center[1]], 'subplans': subplans, 'subplan_index': ind_sub})
        lock_plans.release()

        for plan in plans:
            filename = '{}_{}_{}.plan'.format(plan['token'],plan['subplan_index'],plan['subplans'])
            try:
                f = open(plandir+'/'+filename, 'w', 0)
                json.dump(plan, f, indent=1, separators=(',', ': '))
                print('[+] Plan file {} was written.'.format(filename))
            except Exception as e:
                print('[+] Error while writing plan file, error : {}'.format(e))
            finally:
                if 'f' in vars() and not f.closed:
                    f.close()

        return jsonify("")

    @app.route('/_add_regionplans')
    def regionplans():
        lat_f,lat_t,lng_f,lng_t = request.args.get('lat_f', type=float),request.args.get('lat_t', type=float),request.args.get('lng_f', type=float),request.args.get('lng_t', type=float)
        locations = mapl.cover_region_s2((lat_f,lng_f),(lat_t,lng_t))

        return jsonify(locations)

    @app.route('/_add_plan')
    def add_plan():
        location = (request.args.get('lat', type=float),request.args.get('lng', type=float))
        all_loc,border,cid = mapl.get_area_cell(location,True)
        grid = mapl.Hexgrid()
        # all_loc = grid.cover_cell(cid)
        center = LatLng.from_point(Cell(cid).get_center())
        center = (center.lat().degrees, center.lng().degrees)
        token = cid.to_token()
        lock_plans.acquire()
        list_plans.append(token)
        lock_plans.release()
        return jsonify((all_loc, border,[center,token],[]))

    @app.route("/_main")
    def mainfunc():

        grid = mapl.Hexgrid()
        locations = grid.cover_region((0.1, -0.1), (-0.1, 0.1)) # even: 53.0894833975485
        return jsonify(locations)

    @app.route("/")
    def mainapp():
        return render_template('spawn-view.html')

    while True:
        try:
            app.run(host='127.0.0.1', port=port, threaded=True)
        except socket.error as e:
            if e.errno == 10048:
                print('[-] Error: The specified port {} is already in use.'.format(port))
                break

if __name__ == "__main__":
    server_start()
