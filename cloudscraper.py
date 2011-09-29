#!/usr/bin/env python
# coding: utf-8

import logging
import sys

from optparse import OptionParser, make_option as Option
from urllib import FancyURLopener

from lxml import etree

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

    command = args.pop(0)
    fn = commands[command]

    return fn(*args)

commands = dict()

if __name__ == "__main__":
    try:
        ret = main()
    except KeyboardInterrupt:
        ret = None
    sys.exit(ret)
