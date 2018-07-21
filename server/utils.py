from datetime import datetime, timedelta
import json
import os
import re
import pytz
from collections import deque
import typing
from urllib import parse, request

from django.conf import settings
from django.contrib.gis.geos import GeometryCollection, GEOSGeometry, Point
from django.contrib.gis.measure import D
from django.contrib.gis.geos.polygon import Polygon

import site_config


def normalize(s):
    """
    Downcases string s, removes special characters and replaces spaces with _.

    :s: a string
    """
    s = re.sub(r"[',!@#$%^&*()-=[\]]+", "", s)
    s = re.sub(r"\s+", "_", s)

    return s.casefold()


def extension(path):
    "Returns the last piece of the filename after the extension separator."
    _, ext = os.path.splitext(os.path.basename(path))
    return ext[1:] if ext else ""


def split_list(pred, items=None):
    if items is None:
        items = pred
        pred = lambda item: bool(item)

    yes = []
    no = []
    for item in items:
        if pred(item):
            yes.append(item)
        else:
            no.append(item)
    return yes, no


class pushback_iter(object):
    """An iterator that implements a pushback() method, allowing values to
be added back to the 'stack' after consideration.
    """
    def __init__(self, it):
        """
        :it: an iterable object
        """
        self.iterable = iter(it)
        self.pushed = deque()

    def pushback(self, v):
        self.pushed.append(v)

    def __iter__(self):
        return self

    def __next__(self):
        if self.pushed:
            return self.pushed.pop()
        return next(self.iterable)


def decompose_coord(ll):
    """
    :ll: degrees latitude or longitude.

    Return a tuple of (degrees, minutes, seconds)
    """
    degrees = int(ll)
    minutes = ll % 1 * 60
    seconds = minutes % 1 * 60

    return (degrees, int(minutes), seconds)


prettify_format = "{d}\N{DEGREE SIGN} {m}' {s:.2f}\" {h}"


def prettify_lat(lat):
    """
    :lat: degrees latitude

    Returns a human-friendly string representing latitude
    """
    d, m, s = decompose_coord(lat)

    return prettify_format.\
        format(d=d, m=m, s=s, h="N" if lat > 0 else "S")


def prettify_long(lng):
    """
    :lng: degrees longitude

    Returns a human-friendly string representing longitude
    """
    d, m, s = decompose_coord(lng)

    return prettify_format.\
        format(d=d, m=m, s=s, h="E" if lng > 0 else "W")


def add_params(url, extra=None, remove=None):
    """Given a URL, add new query parameters by merging in the contents of the
    `extra` dictionary.

    :param url: (str)
    :param extra: (dict)
    :param remove: (list or set)

    :returns: (str) URL including new parameters
    """
    if not (extra or remove):
        return url

    parsed = parse.urlparse(url)._asdict()
    params = parse.parse_qsl(parsed["query"])

    if extra:
        params += list(extra.items())
    if remove:
        params = [pair for pair in params if pair[0] not in remove]

    parsed["query"] = parse.urlencode(params, doseq=True)

    return parse.urlunparse(parse.ParseResult(**parsed))


def bounds_from_box(box):
    """Converts a `box` string parameter to a Polygon object. If given a Polygon,
    it is returned unchanged.

    :param box: (str) with the format latMin,longMin,latMax,longMax

    """
    if isinstance(box, Polygon):
        return box

    coords = [float(coord) for coord in box.split(",")]
    assert len(coords) == 4
    # Coordinates are submitted to the server as
    # latMin,longMin,latMax,longMax, but from_bbox wants its arguments in a
    # different order:
    return Polygon.from_bbox((coords[1], coords[0], coords[3], coords[2]))


def point_from_str(coord):
    """Converts a `circle` string parameter to a center point and radius. If
    given a Point, it is returned unchanged.

    """
    if isinstance(coord, Point):
        return coord

    coords = coord.split(",")

    return Point(float(coords[1]), float(coords[0]), srid=4326)


units_patt = "(" + "|".join(D.UNITS.keys()) + ")"
distance_patt = rf"(\d+(?:\.\d+)?)\s*{units_patt}?\s*$"
def distance_from_str(distance):
    if isinstance(distance, str):
        m = re.match(distance_patt, distance)
        if m:
            unit = m.group(2) or "m"
            return D(**{unit: float(m.group(1))})
    else:
        return D(m=float(distance))


def _geometry(feat):
    if feat["type"] == "FeatureCollection":
        return sum([_geometry(f) for f in feat["features"]], [])

    return [GEOSGeometry(json.dumps(feat["geometry"]))]


def geometry(feat):
    """Constructs a GEOSGeometryCollection from a GeoJSON dict.
    """
    return GeometryCollection(_geometry(feat), srid=4326)


def geometry_from_url(url):
    """Constructs a GEOSGeometryCollection from a URL that points to a GeoJSON
    resource.
    """
    with request.urlopen(url) as resp:
        raw = resp.read().decode("utf-8")
        return geometry(json.loads(raw))


def utc_now():
    return pytz.utc.localize(datetime.utcnow())


def lazy(fn):
    memo = [None, False]

    def wrapped():
        if not memo[1]:
            memo[0:2] = fn(), True
        return memo[0]
    return wrapped


def add_locations(dicts, geocoder,
                  get_address=lambda d: d["all_addresses"][0],
                  region=lambda d: d.get("region_name", "")):
    """Alters an iterable of dictionaries in place, adding a "location" field
                  that contains the geocoded latitude and longitude of each
                  dictionary's address field.

    :param geocoder: an instance of a geocoder object that takes a 
    """
    get_region = region if callable(region) else (lambda _: region)
    locations = geocoder.geocode(
        f"{get_address(d)}, {get_region(d)}" for d in dicts)
    for d, location in zip(dicts, locations):
        if not location:
            continue
        d["location"] = {"lat": location["location"]["lat"],
                         "long": location["location"]["lng"],
                         "formatted": location["formatted_name"],
                         "score": location["properties"].get("score"),
                         "google_place_id": location["properties"].get("place_id")}


def fn_chain(val, *fns):
    for fn in fns:
        val = fn(val) if callable(fn) else val.get(fn)
        if val is None:
            return val
    return val


def make_fn_chain(*fns):
    return lambda x: fn_chain(x, *fns)


def parse_duration(s):
    h, m = s.split(":")
    return timedelta(hours=int(h), minutes=int(m))


def read_n_from_end(fp: typing.IO, n,
                    split_chunk=lambda c: c.split(b"\n"),
                    chunksize=1000):
    """
    Consume a file in reverse, splitting with function `split_chunk`. By
    default, takes the last `n` lines from the reader.

    :fp: file handle, must be opened in 'rb' mode
    :n: the number of lines
    :split_chunk: function to split chunks into lines
    """
    start_pos = fp.tell()
    lines = deque()
    pos = fp.seek(0, 2)
    current = b""
    try:
        while True:
            last_pos = pos
            pos = fp.seek(-chunksize, 1)

            current = fp.read(last_pos - pos) + current
            current, *found_lines = split_chunk(current)
            lines.extendleft(reversed(found_lines[0:n-len(lines)]))

            if len(lines) >= n:
                break

    except OSError as _err:
        if len(lines) < n:
            lines.appendleft(current)

    fp.seek(start_pos, 0)

    return lines


def make_absolute_url(path, site_name=None):
    if re.match(r"^https?://", path):
        return path

    if site_name:
        config = site_config.by_hostname(site_name)
        if settings.BASE_URL:
            url_base = settings.BASE_URL
            path = add_params(path, {"_hostname": config.hostname})
        else:
            url_base = f"https://{config.hostname}"
    else:
        hostname = settings.SERVER_DOMAIN
        scheme = "http" if hostname.startswith("localhost") else "https"
        url_base = f"{scheme}://{hostname}"

    return parse.urljoin(url_base, path)


def today():
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

def request_ip(req):
    # TODO Make this function more robust

    # if "HTTP_X_FORWARDED_FOR" in req.META:
    #     ips = req.META["HTTP_X_FORWARDED_FOR"].split(",")
    #     stop_at_ip = os.environ.get("CLUSTER_SUBNET_MASK", )
    return req.META.get("HTTP_X_REAL_IP", req.META["REMOTE_ADDR"])
