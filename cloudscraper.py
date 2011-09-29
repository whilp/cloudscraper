#!/usr/bin/env python
# coding: utf-8

import logging
import sys

from collections import namedtuple
from functools import wraps
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
]

Track = namedtuple("Track", "url title artist referer duration")

class Source(object):
    sources = {}

    def __init__(self, **kwargs):
        pass

    def open(self, url):
        return FancyURLopener().open(url)

    @classmethod
    def match(self, url):
        for source in self.sources:
            if source.match(url):
                return source

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

if __name__ == "__main__":
    try:
        ret = main()
    except KeyboardInterrupt:
        ret = None
    sys.exit(ret)
