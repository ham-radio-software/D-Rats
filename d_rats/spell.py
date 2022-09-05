#!/usr/bin/python
#
from __future__ import absolute_import
from __future__ import print_function

#importing printlog() wrapper
from .debug import printlog

import os
import subprocess

class Spelling:
    def __open_aspell(self):
        kwargs = {}
        # pylint: disable=maybe-no-member
        if subprocess.mswindows:
            su = subprocess.STARTUPINFO()
            su.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            su.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = su

        p = subprocess.Popen([self.__aspell, "pipe"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             #close_fds=True,
                             **kwargs)
        return p

    def __close_aspell(self):
        if self.__pipe:
            self.__pipe.terminate()
            self.__pipe = None

    def __init__(self, aspell="aspell", persist=True):
        self.__aspell = aspell
        self.__persist = persist
        self.__pipe = None

    def lookup_word(self, wiq):
        for c in wiq:
            c = ord(c)
            if c < ord('A') or c > ord('z') or \
                    (c > ord('Z') and c < ord('a')):
                return []

        try:
            self.__pipe.stdout.readline()
        except Exception:
            printlog("Demand-opening aspell...")
            self.__pipe = self.__open_aspell()
            self.__pipe.stdout.readline()

        self.__pipe.stdin.write("%s%s" % (wiq, os.linesep))
        suggest_str = self.__pipe.stdout.readline()

        if not self.__persist:
            self.__close_aspell()

        if suggest_str.startswith("*"):
            return []
        elif not suggest_str.startswith("&"):
            raise Exception("Unknown response from aspell: %s" % suggest_str)

        suggestions = suggest_str.split()
        return suggestions[4:]

    def test(self):
        try:
            s = self.lookup_word("speling")
            if s[0] != "spelling,":
                printlog("Spell     : Unable to validate first suggestion of `spelling'")
                printlog(s[0])
                return False
        except Exception as e:
            printlog("Spelling test failed: %s" % e)
            return False

        printlog("Tested spelling okay: %s" % s)
        return True


def test_word(spell, word):
    spell.stdin.write(word + "\n")
    result = spell.stdout.readline()
    spell.stdout.readline()

    if result.startswith("*"):
        return []
    elif result.startswith("&"):
        items = result.split()
        return items[4:]
    else:
        printlog("Unknown response: `%s'" % result)

SPELL = None
def get_spell():
    #m this is executed when d-rats starts
    global SPELL
    if not SPELL:
        SPELL = Spelling()
    return SPELL

def __do_fly_spell(buffer):
    cursor_mark = buffer.get_mark("insert")
    start_iter = buffer.get_iter_at_mark(cursor_mark)
    end_iter = buffer.get_iter_at_mark(cursor_mark)

    if not start_iter.starts_word():
        start_iter.backward_word_start()
    if end_iter.inside_word():
        end_iter.forward_word_end()

    text = buffer.get_text(start_iter, end_iter)
    word = text.strip()
    #print "Got: '%s' (%s)" % (text, word)

    if not word:
        return

    end_iter.backward_chars(len(text) - len(word))

    if " " in word:
        mispelled = False
    else:
        speller = get_spell()
        mispelled = bool(speller.lookup_word(word))

    if text.endswith(" ") and mispelled:
        buffer.apply_tag_by_name("misspelled", start_iter, end_iter)
    else:
        buffer.remove_tag_by_name("misspelled", start_iter, end_iter)

def prepare_TextBuffer(buf):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    from gi.repository import Pango

    tags = buf.get_tag_table()
    tag = Gtk.TextTag("misspelled")
    tag.set_property("underline", Pango.UNDERLINE_SINGLE)
    tag.set_property("underline-set", True)
    tag.set_property("foreground", "red")
    tags.add(tag)

    buf.connect("changed", __do_fly_spell)

if __name__ == "__main__":
    s = Spelling()
    printlog(s.lookup_word("speling"))
    printlog(s.lookup_word("teh"))
    printlog(s.lookup_word("foo"))
