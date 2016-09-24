from math import pi,radians, cos, sin, asin, sqrt, ceil, floor
from s2sphere import CellId, LatLng, Cell, MAX_AREA, Point
from operator import itemgetter

earth_Rmean = 6371000.0
earth_Rrect = 6367000.0
earth_Rmax = 6378137.0
earth_Rmin = 6356752.3
def earth_Rreal(latrad):
    return (1.0 / (((cos(latrad)) / earth_Rmax) ** 2 + ((sin(latrad)) / earth_Rmin) ** 2)) ** 0.5

max_size = 1 << 30
lvl_big = 10
lvl_small = 17
HEX_R = 70.0
safety = 0.999
safety_border = 0.9

def get_distance(location1, location2):
    lat1, lng1 = location1
    lat2, lng2 = location2

    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))

    d = sin(0.5*(lat2 - lat1)) ** 2 + cos(lat1) * cos(lat2) * sin(0.5*(lng2 - lng1)) ** 2
    return 2 * earth_Rrect * asin(sqrt(d))

def get_border_pseudohex(coords, HEX_NUM):
    border = []
    for a in range(0, 6):
        tcoord = coords[-HEX_NUM * (6 - a)]
        tcoord = neighbor_circle(tcoord, a, False, 0.5)
        border.append(tcoord)
    border.append(border[0])
    return border

def get_border_cell(s2_id):
    locs = []
    s2_cell = Cell(s2_id)
    for i in [0, 1]:
        for j in [0, 1]:
            locs.append([s2_cell.get_latitude(i, j) * 180 / pi, s2_cell.get_longitude(i, j) * 180 / pi])
    output = [locs[0], locs[1], locs[3], locs[2], locs[0]]
    return output

def neighbor_pseudohex(location, HEX_NUM, pos):
    pos = pos % 6
    torange = HEX_NUM * (3 ** 0.5) + 1
    while torange > 1:
        location = neighbor_circle(location, pos, shift=True)
        torange -= 1
    location = neighbor_circle(location, pos, shift=True, factor=torange)
    location = neighbor_circle(location, pos + 2, shift=True, factor=0.5)
    return location

def get_pseudo_hex(location, layer_max, layer_min=0):
    coords = []
    if layer_max < 0 or layer_min > layer_max:
        return coords
    coords.append(location[:])
    if layer_max < 1:
        return coords
    for b in range(0, 6):
        coords.append(neighbor_pseudohex(coords[0], 30, b))
    offs = 1
    for n in range(1, layer_max):
        offs = offs + 6 * (n - 1)
        for b in range(0, 6 * n):
            coords.append(neighbor_pseudohex(coords[b + offs], 30, b / n))
            if b % n == n - 1:
                coords.append(neighbor_pseudohex(coords[b + offs], 30, b / n + 1))
    if layer_min < 1:
        return coords

    ind_f = 1
    for l in range(1, layer_min):
        ind_f += 6 * l
    return coords[ind_f:]

def neighbor_circle(location, pos, shift=False, factor=1.0):
    pos = pos % 6
    latrad = location[0] * pi / 180
    x_un = factor * safety / earth_Rrect / cos(latrad) * 180 / pi
    y_un = factor * safety / earth_Rrect * 180 / pi
    if not shift:
        y_un = y_un * (3.0 ** 0.5) / 2.0 * HEX_R
        x_un = x_un * HEX_R * 1.5
        yvals = [-2, -1, 1, 2, 1, -1]
        xvals = [0, 1, 1, 0, -1, -1]
    else:
        y_un = y_un * HEX_R * 1.5
        x_un = x_un * (3.0 ** 0.5) / 2.0 * HEX_R
        yvals = [-1, 0, 1, 1, 0, -1]
        xvals = [1, 2, 1, -1, -2, -1]

    newlat = location[0] + y_un * yvals[pos]
    newlng = ((location[1] + x_un * xvals[pos] + 180) % 360) - 180
    return (newlat, newlng)

def get_area_spiral(location, layer_max, layer_min=0):
    coords = []
    if layer_max < 0:
        return coords
    coords.append(location[:])
    if layer_max < 1:
        return coords
    for b in range(0, 6):
        coords.append(neighbor_circle(coords[0], b))
    offs = 1
    for n in range(1, layer_max):
        offs = offs + 6 * (n - 1)
        for b in range(0, 6 * n):
            coords.append(neighbor_circle(coords[b + offs], b / n))
            if b % n == n - 1:
                coords.append(neighbor_circle(coords[b + offs], b / n + 1))
    if layer_min < 1:
        return coords
    elif layer_min > layer_max:
        return []

    ind_f = 1
    for l in range(1, layer_min):
        ind_f += 6 * l
    return coords[ind_f:]

def ij_offs(cell_in, offs_i, offs_j):  # input type is CellId
    face, i, j = cell_in.to_face_ij_orientation()[0:3]
    size = cell_in.get_size_ij(cell_in.level())

    i_new = i + size * offs_i
    j_new = j + size * offs_j
    out = cell_in.from_face_ij_same(face, i_new, j_new, j_new >= 0 and i_new >= 0 and i_new < max_size and j_new < max_size).parent(cell_in.level())

    return out  # output type is CellId

def neighbor_s2_circle(location, i_dir=0.0, j_dir=0.0):  # input location can be list, tuple or Point
    if type(location) in (list, tuple):
        ll_location = LatLng.from_degrees(location[0], location[1])
    elif type(location) is Point:
        ll_location = LatLng.from_point(location)
    elif type(location) is LatLng:
        ll_location = location
    else:
        return None

    cid_large = CellId.from_lat_lng(ll_location).parent(lvl_big)

    cid_small = cid_large.child_begin(lvl_small)
    vec_to_j = (Cell(ij_offs(cid_small, 0, 1)).get_center() - Cell(cid_small).get_center()).normalize()
    vec_to_i = (Cell(ij_offs(cid_small, 1, 0)).get_center() - Cell(cid_small).get_center()).normalize()

    vec_newlocation = ll_location.to_point() + safety * HEX_R / earth_Rrect * (i_dir * 3 ** 0.5 * vec_to_i + j_dir * 1.5 * vec_to_j)

    return vec_newlocation  # output is Point

def get_area_cell(location,unfilled=False):
    border = []
    locs = []

    cid_large = CellId.from_lat_lng(LatLng.from_degrees(location[0], location[1])).parent(lvl_big)
    border.append(get_border_cell(cid_large))

    if unfilled:
        return [], border, cid_large

    corner = neighbor_s2_circle(LatLng.from_degrees(border[-1][0][0], border[-1][0][1]), safety_border*0.5, safety_border/3.0)
    j_maxpoint = LatLng.from_point(neighbor_s2_circle(LatLng.from_degrees(border[-1][1][0], border[-1][1][1]), safety_border*0.5, (1-safety_border)/3.0))
    i_maxpoint = LatLng.from_point(neighbor_s2_circle(LatLng.from_degrees(border[-1][3][0], border[-1][3][1]), (1-safety_border)*0.5, safety_border/3.0))

    base = corner
    p_start = base

    dist_j = j_maxpoint.get_distance(LatLng.from_point(p_start))
    last_dist_j = None
    j = 0
    while last_dist_j is None or dist_j < last_dist_j:
        dist_i = i_maxpoint.get_distance(LatLng.from_point(p_start))
        last_dist_i = None
        while last_dist_i is None or dist_i < last_dist_i:
            locs.append(LatLng.from_point(p_start))
            p_start = neighbor_s2_circle(p_start, 1.0, 0.0)
            last_dist_i = dist_i
            dist_i = i_maxpoint.get_distance(LatLng.from_point(p_start))
        base = neighbor_s2_circle(base, 0.0, 1.0)
        last_dist_j = dist_j
        dist_j = j_maxpoint.get_distance(LatLng.from_point(base))
        if j % 2 == 1:
            p_start = base
        else:
            p_start = neighbor_s2_circle(base, -0.5, 0.0)
        j += 1

    all_loc = []
    for loc in locs:
        all_loc.append([loc.lat().degrees, loc.lng().degrees])

    return all_loc, border,cid_large

def workers_for_level(lvl,parts):
    area = MAX_AREA.get_value(lvl) * earth_Rmean**2
    area_scan = 1.5*3**0.5 * HEX_R**2
    num_scans = area / area_scan
    num_scans_ph_max = num_scans * 5 * 2 #10 minute time (* 6) and all cells empty (* 2)
    num_worker_scans_ph = 3600.0 / 10 - 2 #reauthorizations (- 2)
    num_workers_required = int(ceil(num_scans_ph_max / parts /num_worker_scans_ph))
    return num_workers_required

def workers_for_number(num_scans,parts=1):
    num_scans_ph_max = num_scans * 5 * 2 #10 minute time (* 6) and all cells empty (* 2)
    num_worker_scans_ph = 3600.0 / 10 - 2 #reauthorizations (- 2)
    num_workers_required = int(ceil(num_scans_ph_max/ num_worker_scans_ph /parts))
    return num_workers_required

class Hexgrid(object):
    earth_R = earth_Rrect
    param_shift = 217.91
    param_stretch = 591
    r_sight = 70.0
    safety = 0.999

    def __init__(self):
        self.grid = self.init_grid()

    def init_lats(self):
        latrad = 0.0
        lats = []

        c = 0.5 * self.r_sight * self.safety
        while latrad < pi / 2:
            lats.append(latrad)
            latrad += c / self.earth_R
        return lats

    def init_grid(self):
        grid_all = []
        lats = self.init_lats()
        c = 2 * pi / (3 ** 0.5 * self.r_sight * self.safety) * self.earth_R

        even_lng = True

        strip_amount = int(ceil(c))
        grid_all.append((0, strip_amount, even_lng))
        ind_lat = 2

        while ind_lat < len(lats):
            amount = int(ceil(c * cos(lats[ind_lat])))
            if amount < strip_amount - (sin(lats[ind_lat]*2)*self.param_shift+self.param_stretch):
                ind_lat -= 1
                strip_amount = int(ceil(c * cos(lats[ind_lat])))
            else:
                even_lng = not even_lng

            if ind_lat + 1 < len(lats):
                lat = lats[ind_lat + 1] * 180 / pi
                grid_all.append((lat, strip_amount, even_lng))
            ind_lat += 3

        grid_all.append((90.0, 1, True))  # pole

        return grid_all

    def dist_cmp(self, location1, location2):
        return sin(0.5 * (location2[0] - location1[0])) ** 2 + cos(location2[0]) * cos(location1[0]) * sin(0.5 * (location2[1] - location1[1])) ** 2

    def cover_circle(self,loc,radius):
        lat,lng = loc
        output = []
        r_lat = radius / earth_Rrect*180/pi
        r_lng = r_lat /cos(min(abs(lat)+r_lat,90.0)*pi/180)
        locations = self.cover_region((lat-r_lat,lng-r_lng),(lat+r_lat,lng+r_lng))
        for location in locations:
            dist = get_distance(loc,location)
            if dist < radius:
                output.append(location)
        return output

    def cover_cell(self, cid):
        lats = []
        lngs = []
        output = []
        s2_cell = Cell(cid)
        lvl = s2_cell.level()
        for i in [0, 1]:
            for j in [0, 1]:
                lats.append(s2_cell.get_latitude(i, j)/pi*180)
                lngs.append(s2_cell.get_longitude(i, j)/pi*180)
        locations = self.cover_region((min(lats),min(lngs)),(max(lats),max(lngs)))
        for location in locations:
            testid = CellId.from_lat_lng(LatLng.from_degrees(location[0],location[1])).parent(lvl)
            if testid == cid:
                output.append(location)

        return output

    def cover_region(self, location1, location2):
        l_lat1 = location1[0]
        l_lat2 = location2[0]
        l_lng1 = location1[1]
        l_lng2 = location2[1]

        if l_lat1 > l_lat2:
            l_lat1, l_lat2 = l_lat2, l_lat1
        range_lat = []
        if l_lat1 >= 0 and l_lat2 >= 0:
            range_lat.append([[l_lat1, l_lat2], False])
        elif l_lat1 <= 0 and l_lat2 <= 0:
            range_lat.append([[-l_lat2, -l_lat1], True])
        else:
            range_lat.append([[0.0, -l_lat1], True])
            range_lat.append([[0.0, l_lat2], False])

        if l_lng1 > l_lng2:
            l_lng1, l_lng2 = l_lng2, l_lng1
        l_lng1 = l_lng1 % 360
        l_lng2 = l_lng2 % 360
        range_lng = []
        if l_lng1 > l_lng2:
            range_lng.append([l_lng1, 360.0])
            range_lng.append([0.0, l_lng2])
        else:
            range_lng.append([l_lng1, l_lng2])

        points = []
        for r_lat in range_lat:
            for r_lng in range_lng:
                newpoints = self.cover_region_simple((r_lat[0][0], r_lng[0]), (r_lat[0][1], r_lng[1]))
                for point in newpoints:
                    if point[1] == 360.0:
                        continue
                    if r_lat[1]:
                        if point[0] == 0.0:
                            continue
                        else:
                            point[0] = -point[0]

                    point[1] = (point[1] + 180) % 360 - 180
                    points.append(point)
        points.sort(key=itemgetter(0,1))
        return points

    def cover_region_simple(self, location1, location2):  # lat values must be between -90 and +90, lng values must be between -180 and 180
        l_lat1 = location1[0]
        l_lat2 = location2[0]
        l_lng1 = location1[1]
        l_lng2 = location2[1]

        ind_lat_f = 0
        while l_lat1 > self.grid[ind_lat_f][0]:
            ind_lat_f += 1

        ind_lat_t = ind_lat_f + 1
        while ind_lat_t < len(self.grid) and l_lat2 >= self.grid[ind_lat_t][0]:
            ind_lat_t += 1
        points = []
        for ind_lat in range(ind_lat_f, ind_lat_t):
            d_lng = 360.0 / self.grid[ind_lat][1]
            if self.grid[ind_lat][2]:
                c_lng = 0.0
            else:
                c_lng = 0.5

            ind_lng_f = int(ceil(l_lng1 / d_lng - c_lng))
            ind_lng_t = int(floor(l_lng2 / d_lng - c_lng))
            for ind_lng in range(ind_lng_f, ind_lng_t + 1):
                points.append([self.grid[ind_lat][0], d_lng * (ind_lng + c_lng)])

        return points

    def to_grid_point(self, location):
        l_lat = location[0]
        l_lng = location[1]
        if l_lat < 0:
            l_lat = -l_lat
            neg_lat = True
        else:
            neg_lat = False
            l_lng = l_lng % 360

        poss = []
        ind_lat = 0
        while l_lat > self.grid[ind_lat][0]:
            ind_lat += 1

        if l_lat == self.grid[ind_lat][0]:
            ind_f = ind_lat
        else:
            ind_f = ind_lat - 1
        if ind_lat + 1 == len(self.grid):
            ind_t = ind_lat
            poss.append([90.0, 0.0])
        else:
            ind_t = ind_lat + 1

        for ind_tlat in range(ind_f, ind_t):
            d_lng = 360.0 / self.grid[ind_tlat][1]
            lng = floor(l_lng / d_lng) * d_lng
            if not self.grid[ind_tlat][2]:
                lng += 0.5 * d_lng
            poss.append([self.grid[ind_tlat][0], lng])
            poss.append([self.grid[ind_tlat][0], lng + d_lng])

        dist_min = 3.0
        ind_min = 0
        for p in range(0, len(poss)):
            dist = self.dist_cmp(location, poss[p])
            if dist < dist_min:
                dist_min = dist
                ind_min = p

        if neg_lat:
            poss[ind_min][0] = -poss[ind_min][0]
        poss[ind_min][1] = (poss[ind_min][1] + 180) % 360 - 180

        return poss[ind_min]