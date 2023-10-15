'''Version information'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# minor mods 2015-2020 by Maurizio Andreotti iz2lxi
#                         <maurizioandreottilc@gmail.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
#
# This module contains the d-rats version variables

# Version parsing rules intended to be compliant with PEP-440.
# PEP-440 specifies: [N!]N(.N)*[{a|b|rc}N][.postN][.devN]

# WL2K requires a N.N.N format where N is a digit for internal use.

# The version number will be generated by "git describe --tags" when running
# out of a directory created from a git repository and parsed
# for PEP-440 compliance.
# https://peps.python.org/pep-0440/

# This means that future git tags need to follow a convention compliant
# with PEP-440.  A 'v' prefix is allowed for more readability.
# The EPOCH "N!" will be ignored as we have no reason to set an
# EPOCH in the foreseeable future.
# The ".post" and ".dev" should not be used in git tags.

# When the git metadata is not available the version data is expected
# to be in the PKG-INFO file generated by the packaging process and the
# packaging process is expected to have been run from a directory created
# from a checkout of a git repository.

# If the PKG-INFO file has not been generated, this means that source
# was from an archive of the git repository, and will fall back to
# being the default version specified in this file, and for PEP-440
# will have a ".devN" appended where N is the modification date of this file.

import logging
from os import remove
from os.path import dirname
from os.path import exists
from os.path import isdir
from os.path import join
from os.path import realpath
import re
import subprocess

if not '_' in locals():
    import gettext
    _ = gettext.gettext

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)


DRATS_NAME = "d-rats"
DRATS_DESCRIPTION = "D-RATS"
DRATS_LONG_DESCRIPTION = _("A communications tool for D-STAR")
AUTHORS = "Dan Smith, KK7DS \n" \
          "Maurizio Andreotti, IZ2LXI \n" \
          "Marius Petrescu, YO2LOJ \n" \
          "John E. Malmberg, WB8TYW \n\n"
AUTHORS_EMAIL = "Dan Smith KK7DS <dsmith@danplanet.com>\n"  \
          "Maurizio Andreotti IZ2LXI <maurizioandreottilc@gmail.com>\n" \
          "Marius Petrescu YO2LOJ <marius@yo2loj.ro>\n" \
          "John E. Malmberg WB8TYW <wb8tyw@wsl.net>"
AUTHOR_COPYRIGHT = "2008-2010 Dan Smith (KK7DS)\n" \
          "2014-2022 Maurizio Andreotti (IZ2LXI) &\n"  \
          "Marius Petrescu (YO2LOJ)\n" \
          "2021-2022 John E. Malmberg (WB8TYW)."
DATA_COPYRIGHT = "Location and Map data Copyright www.thunderforest.com and\n" \
          "copyright OpenStreetMap Contributors, www.osm.org/copyright.\n" \
          "Some Map Data courtesy of the U.S. Geological Survey.\n" \
          "Weather data provided by OpenWeather (TM), openweathermap.org"
COPYRIGHT = 'Copyright ' + AUTHOR_COPYRIGHT + '\n' + DATA_COPYRIGHT
LICENSE = "You should have received a copy of the" \
	      " GNU General Public License along with this program.\n" \
		  "  If not, see <http://www.gnu.org/licenses/>."
WEBSITE = "https://groups.io/g/d-rats"
TRANSLATIONS = "Dutch: \n" \
            "Italian: Leo, IZ5FSA / Maurizio IZ2LXI \n" \
                "German: \n"\
                "Spanish: \n"

# DRATS_VERSION_NUM can not have "-" characters in it.
# That will break w2lk

class Version:
    '''Version.'''

    DRATS_VERSION_NUM_DEFAULT = "0.4.1"
    logger = logging.getLogger("Version")

    _version = {}
    _short_version = None
    _pep440_version = None
    _full_version = None
    _version_re = re.compile('^Version: (.+)$', re.M)

    @classmethod
    def _get_short_version(cls):
        cls._get_version()
        # short version string
        cls._short_version = "%d.%d.%s" % \
            (cls._version['major'], cls._version['minor'],
             cls._version['micro'])

    @property
    def short_version(self):
        '''
        :returns: short 3 digit version number separated by dots
        :rtype: str
        '''
        if not self._short_version:
            self._get_short_version()
        return self._short_version

    @classmethod
    def _get_pep440_version(cls):
        cls._get_version()
        if not cls._short_version:
            cls._get_short_version()
        pep440 = cls._short_version
        if cls._version['pico']:
            pep440 += cls._version['pico']
        if cls._version['alpha']:
            pep440 += cls._version['alpha']
        if cls._version['beta']:
            pep440 += cls._version['beta']
        if cls._version['candidate']:
            pep440 += cls._version['candidate']
        if cls._version['post']:
            pep440 += cls._version['post']
        if cls._version['dev']:
            pep440 += cls._version['dev']
        elif cls._version['commits']:
            # The git describe commits count is used for a dev section.
            pep440 += '.dev%s' % cls._version['commits']
            cls._version['pep440'] = pep440
        cls._pep440_version = pep440
        my_dir = realpath(dirname(__file__))
        base_dir = dirname(my_dir)
        if exists(join(base_dir, '.git')):
            # We need to know if we are running from a git checkout, in that
            # case we want to use the data from the git checkout directory
            # instead of data from a previous package install.
            setup_version = join(base_dir, 'd_rats', 'setup_version.py')
            with open(setup_version, 'w') as version_file:
                version_file.write("'''Setup Version.'''\n")
                version_file.write("# This file generated by version.py\n")
                version_file.write('SETUP_VERSION = "%s"\n' %
                                   cls._pep440_version)
                cls.logger.debug('Created d_rats/setup_version.py')

    @property
    def pep440_version(self):
        '''
        :returns: PEP 440 compliant version string
        :rtype: str
        '''
        # pep044 version string, not enforcing all rules.
        if not self._pep440_version:
            self._get_pep440_version()
        return self._pep440_version

    @classmethod
    def _get_full_version(cls):
        if not cls._pep440_version:
            cls._get_pep440_version()
        cls._full_version = cls._pep440_version
        if cls._version['git_hash']:
            cls._full_version += '-' + cls._version['git_hash']
        if cls._version['dirty']:
            cls._full_version += cls._version['dirty']

    @property
    def full_version(self):
        '''Full version for display in the program.'''
        if not self._full_version:
            self._get_full_version()
        return self._full_version

    @classmethod
    def _extra_dev_parsing(cls):
        '''Special extra dev parsing.'''
        if not cls._version['extra']:
            return
        # This is somehow missed in the above regex sometimes.
        if not cls._version['dev']:
            release_re = re.search(r'(dev\d+)?(.*)?',
                                   cls._version['extra'])
            if release_re.group(1):
                cls._version['dev'] = '.' + release_re.group(1)
                cls._version['extra'] = release_re.group(2)


    @classmethod
    def _extra_parsing(cls):
        '''
        Extra Parsing of version dictionary.
        '''
        if not cls._version['extra']:
            return
        # Handle some non PEP-440 compliant tags
        regex0 = r'^(?:(?:\.)?(a\d+)?(b\d+)?(r?c\d+)?)?(.*)?'
        release0_re = re.search(regex0, cls._version['extra'])
        cls._version['alpha'] = release0_re.group(1)
        cls._version['beta'] = release0_re.group(2)
        cls._version['candidate'] = release0_re.group(3)
        cls._version['extra'] = release0_re.group(4)
        if not cls._version['extra']:
            return

        # Look for PEP-440 compliant release
        regex = r'^(?:(\.\d+)*)?' + \
                r'(a\d+)?(b\d+)?(r?c\d+)?(.dev\d+)?(.post\d+)?(.*)?'
        release_re = re.search(regex, cls._version['extra'])
        cls._version['pico'] = release_re.group(1)
        cls._version['dev'] = release_re.group(2)
        if not cls._version['alpha']:
            cls._version['alpha'] = release_re.group(3)
        if not cls._version['beta']:
            cls._version['beta'] = release_re.group(4)
        if not cls._version['candidate']:
            cls._version['candidate'] = release_re.group(5)
        cls._version['post'] = release_re.group(6)
        cls._version['extra'] = release_re.group(7)

        cls._extra_dev_parsing()
        if not cls._version['extra']:
            return
        # If this is from git-describe and not on a version tag,
        # then there will be some optional text, a dash, a number
        # a second dash followed by a git hash beginning with a letter g.
        # with a possible "-dirty" if there are un-committed changes
        # to the repository
        git_regex = r'^([^-]*)?(?:\-(\d+))?(?:-(g[^-]+))?(-dirty)?(.*)?'
        git_re = re.search(git_regex, cls._version['extra'])
        if git_re:
            cls._version['commits'] = git_re.group(2)
            cls._version['git_hash'] = git_re.group(3)
            cls._version['dirty'] = git_re.group(4)
            cls._version['extra'] = git_re.group(1)

        if not cls._version['extra']:
            return
        # Try to fix up old git tags and version issues
        old_regex = r'^\s*(beta|alpha)?(\d+)?(.*)?'
        old_re = re.search(old_regex, cls._version['extra'])
        if not old_re:
            return
        key = old_re.group(1)
        if not key:
            return
        if not cls._version[key]:
            beta_num = '1'
            if old_re.group(2):
                beta_num = old_re.group(2)
                cls._version[key] = 'b' + beta_num
                cls._version['extra'] = old_re.group(3)

    @classmethod
    def _parse_version(cls, raw_version):
        '''
        Parse the version string into parts.

        :param raw_version: Raw version string
        :type raw_version: str
        :returns: Dictionary numeric version and extra version
        :rtype: dict
        '''
        cls._version = {}
        cls._version['epoch'] = None
        cls._version['major'] = 0
        cls._version['minor'] = 0
        cls._version['micro'] = 0
        cls._version['pico'] = None
        cls._version['dev'] = None
        cls._version['alpha'] = None
        cls._version['beta'] = None
        cls._version['post'] = None
        cls._version['candidate'] = None
        cls._version['commits'] = None
        cls._version['dirty'] = None
        cls._version['git_hash'] = None
        cls._version['extra'] = ''
        # we do not enforce PEP-440, as we want to be more liberal here.
        version_re = re.search(r'^v?(\d+!)?(\d+)?\.?(\d+)?\.?(\d+)?(.+)?',
                               raw_version)
        cls._version['epoch'] = version_re.group(1)
        find_version = True
        for group_num in range(2, version_re.lastindex + 1):
            part = version_re.group(group_num)
            if find_version:
                # We do not know how many numeric version numbers separated
                # by dots that there will be.
                # for w2lk we need to capture the first three.
                try:
                    part_num = int(part)
                    if group_num == 2:
                        cls._version['major'] = part_num
                        continue
                    if group_num == 3:
                        cls._version['minor'] = part_num
                        continue
                    if group_num == 4:
                        cls._version['micro'] = part_num
                        continue
                except ValueError:
                    find_version = False
        if cls._version['extra']:
            cls._version['extra'] += '.'
        cls._version['extra'] += part
        cls._extra_parsing()

    @classmethod
    def _update_pkg_info(cls, file_name):
        '''
        Update the pkg_info file if needed.

        :param file_name: Filename of pkg_info file.
        :type file_name: str
        '''
        try:
            # Extract the version from the PKG-INFO file.
            with open(file_name, encoding="utf-8") as file_handle:
                raw_version = cls._version_re.search(
                    file_handle.read()).group(1)
                if raw_version != cls._pep440_version:
                    remove(file_name)
                    return
        except OSError:
            pass
        # Minimal PKG-INFO file, packaging like RPM/Debian packages
        # should create a more detailed file.
        with open(file_name, 'w', encoding="utf-8") as file_handle:
            file_handle.write('Metadata-Version: 1.0\n')
            file_handle.write('Name: d-rats\n')
            file_handle.write('Version: %s\n' % cls._pep440_version)
            file_handle.write('Summary: D-RATS\n')
            file_handle.write('Home-page: %s\n' % WEBSITE)
            file_handle.write('Author: %s\n' % AUTHORS)
            file_handle.write('License: GPL\n')
            file_handle.write('Description: A communications tool for D-STAR\n')

    @classmethod
    def _get_version(cls):
        '''
        Get version number.

        If we are running from a git repository checkout, get the version
        number from the git repository.

        Otherwise try to get it from the file generated by setuptools.

        Finally fall back to a default in this module.
        '''
        if cls._version:
            return
        file_dir = dirname(__file__)
        module_dir = dirname(file_dir)
        pkg_info_file = join(module_dir, 'PKG-INFO')

        if isdir(join(module_dir, '.git')):
            # Get the version using "git describe".
            cmd = 'git describe --tags --dirty'.split()
            try:
                raw_version = subprocess.check_output(cmd).decode().strip()
                cls._parse_version(raw_version)
                cls._get_pep440_version()
                cls._update_pkg_info(pkg_info_file)
            # Error should be CalledProcessError,
            # Microsoft Windows throws FileNotFoundError
            except (subprocess.CalledProcessError, FileNotFoundError):
                cls.logger.info('Unable to get version number from git tags')

        if not cls._version:
            cls.logger.debug('Not running from a git repository')
            # The new python build procedure will add setup_version.py
            # to the d_rats directory.
            try:
                # comments below suppresses pylint and pylance diagnostics
                # because this module is not in the checked out source tree
                # pylint: disable=import-outside-toplevel
                # pylint: disable=import-error, no-name-in-module
                from d_rats.setup_version import SETUP_VERSION # type: ignore
                cls._parse_version(SETUP_VERSION)
            except ModuleNotFoundError:
                pass
        if not cls._version:
            try:
                # Extract the version from the PKG-INFO file.
                with open(pkg_info_file, encoding='utf-8') as file_handle:
                    raw_version = cls._version_re.search(
                        file_handle.read()).group(1)
                    cls._parse_version(raw_version)

            except OSError:
                cls.logger.info('Could not get an accurate version.')
                raw_version = cls.DRATS_VERSION_NUM_DEFAULT + '.dev0'
                cls._parse_version(raw_version)


GLOBAL_VERSION = Version()

DRATS_VERSION_NUM = GLOBAL_VERSION.short_version
DRATS_VERSION = GLOBAL_VERSION.full_version
DRATS_PEP440_VERSION = GLOBAL_VERSION.pep440_version
__version__ = DRATS_PEP440_VERSION

HTTP_CLIENT_HEADERS = {'User-Agent':  DRATS_NAME + "/" +  DRATS_VERSION}


def main():
    '''Main package for testing.'''

    # Each class should have their own logger.
    logger = logging.getLogger("version_test")

    logger.info("DRATS_VERSION:         %s", DRATS_VERSION)
    logger.info("DRATS_PEP440_VERSION:  %s", DRATS_PEP440_VERSION)
    logger.info("DRATS_NAME:            %s", DRATS_NAME)
    logger.info("DRATS_DESCRIPTION:     %s", DRATS_DESCRIPTION)
    logger.info("DRATS_LONG_DESCRIPTION:%s", DRATS_LONG_DESCRIPTION)
    logger.info("AUTHORS:               %s", AUTHORS)
    logger.info("AUTHORS_EMAIL:         %s", AUTHORS_EMAIL)
    logger.info("COPYRIGHT:             %s", COPYRIGHT)
    logger.info("LICENSE:               %s", LICENSE)
    logger.info("WEBSITE:               %s", WEBSITE)
    logger.info("TRANSLATIONS:          %s", TRANSLATIONS)


if __name__ == "__main__":
    main()
