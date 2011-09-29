#!/usr/bin/env python
# coding: utf-8

import logging
import multiprocessing
import os
import sys
import subprocess
import time

from collections import namedtuple
from functools import partial, wraps
from itertools import count
from optparse import OptionParser, make_option as Option
from urllib import FancyURLopener

try:
    import json
except ImportError:
    json = None

try:
    from lxml import etree
except ImportError:
    etree = None

try:
    NullHandler = logging.NullHandler
except AttributeError:
    class NullHandler(logging.Handler):
        def emit(self, record): pass

log = logging.getLogger(__name__)

def main():
    optionparser = OptionParser(
        option_list=options,
    )
    (opts, args) = optionparser.parse_args(args=sys.argv[1:])

    if not opts.silent:
        log.addHandler(logging.StreamHandler())
        log.level = max(1, logging.WARNING - (10 * (opts.verbose - opts.quiet)))

    root = os.path.abspath(os.path.expanduser(opts.dir))
    makedirs(root)
    os.chdir(root)

    command, url = args[:2]
    if opts.source:
        source = Source.sources.get(opts.source, None)
    else:
        source = Source.match(url)

    if source is None:
        # XXX
        raise Exception()

    source = source(**vars(opts))
    fn = getattr(source, command)

    return fn(url)

options = [
    Option("-q", "--quiet", default=0, action="count",
        help="decrease verbosity"),
    Option("-s", "--silent", default=False, action="store_true",
        help="silence logging"),
    Option("-v", "--verbose", default=0, action="count",
        help="increase verbosity"),
    Option("--source", default=None, action="store",
        help="specify source"),
    Option("--dir", default="~/.cloudscraper", action="store",
        help="application directory"),
]

Track = namedtuple("Track", "url title artist referer duration localname")

class Source(object):
    sources = {}
    player = "mplayer {localname}"
    chunksize = 8192

    def __init__(self, **kwargs):
        pass

    def open(self, url):
        return FancyURLopener().open(url)

    @classmethod
    def match(self, url):
        for source in self.sources.values():
            if source.match(url):
                return source

    def stream(self, url):
        for track in self.scrape(url):
            log.info("streaming %s", track.referer)

            Process = partial(multiprocessing.Process, args=(track,))
            procs = [Process(target=fn) for fn in (self.play, self.download)]
            play, download = procs

            log.debug("downloading %s to %s", track.url, track.localname)
            download.start()

            log.debug("playing %s", track.localname)
            play.start()
            play.join()
            download.terminate()

    def download(self, track):
        stream = self.open(track.url)
        with opener(track.localname, 'wb') as f:
            for chunk in iter(partial(stream.read, self.chunksize), ""):
                f.write(chunk)
                f.flush()

    def play(self, track, buffer=4096):
        counter = count()
        stat = partial(os.stat, track.localname)
        exists = partial(os.path.exists, track.localname)

        while counter.next() < 5 and not (exists() and stat().st_size < buffer):
            time.sleep(.5)

        with opener(os.devnull, 'wb') as null:
            proc = subprocess.Popen(self.player.format(**track._asdict()),
                shell=True, stdout=null, stderr=null)
            proc.wait()

class SoundCloud(Source):

    def tracks(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for data in fn(*args, **kwargs):
                yield Track(
                    title=data["title"],
                    url=data["streamUrl"],
                    artist=data["user"]["username"],
                    referer="http://soundcloud.com{uri}".format(**data),
                    localname=data["uri"].lstrip("/") + ".mp3",
                    duration=data["duration"],
                )
        return wrapper
    
    @tracks
    def scrape(self, url):
        tree = etree.HTML(self.open(url).read())
        scripts = tree.xpath("//div[@id='main-content']//script[@type='text/javascript']/text()")

        for script in scripts:
            try:
                data = json.loads(script[29:-3])
            except (ValueError, TypeError):
                continue
            yield data

        next = tree.xpath("//a[@rel='next']/@href")
        if next:
            next = "http://soundcloud.com{0}".format(next[0])
            for data in self.scrape(next):
                yield data

    @classmethod
    def match(self, url):
        return "soundcloud.com" in url

if etree and json:
    Source.sources["soundcloud"] = SoundCloud

def makedirs(path):
    try:
        os.makedirs(path)
    except OSError, e:
        if e.errno != 17:
            raise

def opener(path, mode='w', encoding='utf-8', root='.'):
    path = os.path.join(root, path)
    if 'w' in mode:
        makedirs(os.path.dirname(path))

    if 'b' in mode:
        return open(path, mode)
    else:
        return codecs.open(path, mode, encoding)

if __name__ == "__main__":
    try:
        ret = main()
    except KeyboardInterrupt:
        ret = None
    sys.exit(ret)
