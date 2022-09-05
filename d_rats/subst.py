#!/usr/bin/python
'''subst'''

from __future__ import absolute_import
from __future__ import print_function
import six.moves.configparser

# importing printlog() wrapper
from .debug import printlog

from . import dplatform

sublist = None

class SubstitutionList(object):
    delim = "/"

    def __init__(self, configfile):
        self.config = six.moves.configparser.ConfigParser()
        self.config.read(configfile)

    def get_sub(self, key):
        if not self.config.has_section("subs") or \
                not self.config.has_option("subs", key):
            return ""

        return self.config.get("subs", key)

    def subst(self, string):
        while string.count(self.delim) >= 2:
            first, _, rest = string.partition(self.delim)
            key, _, last = rest.partition(self.delim)

            sub = self.get_sub(key)

            printlog("Subst",
                     "     : Substitution for %s was: %s" % (key, sub))

            string = first + sub + last

        return string

def load_subs():
    global sublist

    if sublist:
        return True

    f = dplatform.get_platform().config_file("subst.conf")
    if not f:
        return False

    sublist = SubstitutionList(f)

    return True

def subst_string(string):
    if not load_subs():
        printlog("Subst","     : Unable to load substitution list")
        return string
    else:
        return sublist.subst(string)

if __name__ == "__main__":
    printlog(subst_string("Status: /10-14/"))
