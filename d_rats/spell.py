#!/usr/bin/python
'''Spell.'''
#
from __future__ import absolute_import
from __future__ import print_function

import os
import logging
import subprocess
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Pango


class SpellException(Exception):
    '''Generic Spell Exception.'''


class SpellNoSpellCheckerError(SpellException):
    '''No Spell Checker program found.'''


class SpellBadResponseError(SpellException):
    '''Spelling Bad response error.'''


class Spelling:
    '''
    Spelling.

    :param aspell: Spelling program, default 'aspell'
    :type aspell: str
    :param persist: Keep subprocess to spelling program running
    :type persis: bool
    '''

    def __init__(self, aspell="aspell", persist=True):
        self.logger = logging.getLogger("Spelling")
        self.__aspell = aspell
        self.__persist = persist
        self.__pipe = None
        self._spell_good = True

    def __open_aspell(self):
        kwargs = {}
        stderr_pipe = None
        if sys.platform == "win32":
            subproc = subprocess.STARTUPINFO()
            subproc.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subproc.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = subproc

            # msys2 aspell has an issue with the nroff formatter
            # This hides the diagnostic for it but requires python 3.3
            if subprocess.DEVNULL:
                stderr_pipe = subprocess.DEVNULL

        # pylint: disable=consider-using-with
        proc = subprocess.Popen([self.__aspell, "pipe"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=stderr_pipe,
                                bufsize=1,
                                universal_newlines=True,
                                #close_fds=True,
                                **kwargs)
        return proc

    def __close_aspell(self):
        if self.__pipe:
            self.__pipe.terminate()
            self.__pipe = None

    def lookup_word(self, wiq):
        '''
        Lookup Word.

        :param wiq: wiq string
        :type wiq: str
        :returns: List of matching words
        :rtype: list of str
        :raises: :class:`SpellNoSpellCheckerError` if no spelling program found.
        :raises: :class:`SpellBadResponseError` if program has bad response.
        '''
        if not self._spell_good:
            raise SpellNoSpellCheckerError("Program %s present" % self.__aspell)
        for char in wiq:
            char = ord(char)
            if char < ord('A') or char > ord('z') or \
                    (ord('Z') < char < ord('a')):
                return []

        error = None
        try:
            self.__pipe.stdout.readline()

        except AttributeError:
            self.logger.info("Demand-opening aspell...")
            try:
                self.__pipe = self.__open_aspell()
                self.__pipe.stdout.readline()
            except FileNotFoundError as local_error:
                error = local_error
                self._spell_good = False
        if error:
            raise SpellNoSpellCheckerError("Program %s not present" %
                                           self.__aspell)

        self.__pipe.stdin.write("%s%s" %(wiq, os.linesep))
        suggest_str = self.__pipe.stdout.readline()

        self.logger.debug("spell: suggest_str = %s", suggest_str)
        if not self.__persist:
            self.__close_aspell()

        if suggest_str.startswith("*"):
            return []
        if not suggest_str.startswith("&"):
            self._spell_good = False
            raise SpellBadResponseError("Unknown response from aspell: %s" %
                                        suggest_str)

        suggestions = suggest_str.split()
        return suggestions[4:]

    def test(self):
        '''
        Test.

        :returns: True if test passes
        :rtype: bool
        '''
        try:
            spell = self.lookup_word("speling")
            if spell[0] != "spelling,":
                self.logger.info(
                    "Unable to validate first suggestion of `spelling' %s",
                    spell[0])
                return False
        except SpellNoSpellCheckerError:
            self.logger.debug("Did not find %s program", self.__aspell,
                              exc_info=True)
            return False

        except SpellBadResponseError:
            self.logger.info("Spelling failed check",
                             exc_info=True)
            return False

        self.logger.info("Tested spelling okay: %s", spell)
        return True


def test_word(spell, word):
    '''
    Test Word.

    :param spell: Spelling object
    :type spell: :class:`Spelling`
    :param word: Word pattern to check
    :type word: str
    :returns: list of words that may match a misspelled word
    :rtype: list of str
    '''
    logger = logging.getLogger("sell_test_word")
    spell.stdin.write(word + "\n")
    result = spell.stdout.readline()
    spell.stdout.readline()

    if result.startswith("*"):
        return []
    if result.startswith("&"):
        items = result.split()
        return items[4:]
    logger.info("Unknown response: `%s'", result)
    return []


SPELL = None


def get_spell():
    '''
    Get Spell.

    :returns: Spelling object
    :rtype: :class:`Spelling`
    '''
    # m this is executed when d-rats starts
    # pylint: disable=global-statement
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

    text = buffer.get_text(start_iter, end_iter, False)
    word = text.strip()
    # print "Got: '%s' (%s)" % (text, word)

    if not word:
        return

    end_iter.backward_chars(len(text) - len(word))

    if " " in word:
        misspelled = False
    else:
        speller = get_spell()
        misspelled = bool(speller.lookup_word(word))

    if text.endswith(" ") and misspelled:
        buffer.apply_tag_by_name("misspelled", start_iter, end_iter)
    else:
        buffer.remove_tag_by_name("misspelled", start_iter, end_iter)


# pylint: disable=invalid-name
def prepare_TextBuffer(buf):
    '''
    Prepare Text Buffer.

    :param buf: Buffer widget
    :type buf: :class:`Gtk.TextBuffer`
    '''
    tags = buf.get_tag_table()
    tag = Gtk.TextTag.new("misspelled")
    tag.set_property("underline", Pango.Underline.SINGLE)
    tag.set_property("underline-set", True)
    tag.set_property("foreground", "red")
    tags.add(tag)

    buf.connect("changed", __do_fly_spell)


def main():
    '''Unit test.'''

    logging.basicConfig(level=logging.DEBUG)

    logger = logging.getLogger("spell_test")

    spell = Spelling()

    # just to make sure that this code is tested.
    entry_buf = Gtk.TextBuffer.new()
    prepare_TextBuffer(entry_buf)

    result = spell.test()
    if not result:
        logger.info("Spell sanity check failed.")
        # return
    logger.info(spell.lookup_word("speling"))
    logger.info(spell.lookup_word("teh"))
    logger.info(spell.lookup_word("foo"))


if __name__ == "__main__":
    main()
