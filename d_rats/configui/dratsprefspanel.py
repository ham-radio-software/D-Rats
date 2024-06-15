# File configui/dratsprefspanel.py

'''D-Rats Preferences Panel Module.'''

# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2021-2024 John. E. Malmberg - Python3 Conversion
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import glob
import os
from pathlib import Path
HAVE_PYCOUNTRY = False
try:
    from pycountry import countries
    from pycountry import languages
    HAVE_PYCOUNTRY = True
except (ModuleNotFoundError, ImportError):
    pass
import logging

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from ..config_defaults import DEFAULT_COUNTRY
from ..config_defaults import DEFAULT_LANGUAGE_CODE

from .dratspanel import DratsPanel
from .dratspanel import disable_with_toggle
from .dratsconfigwidget import DratsConfigWidget

from ..dplatform import Platform


class DratsPrefsPanel(DratsPanel):
    '''
    D-Rats Preferences Panel.

    :param dialog: D-Rats Config UI Dialog, unused.
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsPrefConfig")

    # pylint: disable=unused-argument, too-many-locals, too-many-statements
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        val = DratsConfigWidget(section="user", name="callsign")
        val.add_upper_text(8)
        self.make_view(_("Callsign"), val)

        val = DratsConfigWidget(section="user", name="name")
        val.add_text()
        self.make_view(_("Name"), val)

        val1 = DratsConfigWidget(section="prefs", name="dosignon")
        val1.add_bool()
        val2 = DratsConfigWidget(section="prefs", name="signon")
        val2.add_text()
        self.make_view(_("Sign-on Message"), val1, val2)
        disable_with_toggle(val1.child_widget, val2.child_widget)

        val1 = DratsConfigWidget(section="prefs", name="dosignoff")
        val1.add_bool()
        val2 = DratsConfigWidget(section="prefs", name="signoff")
        val2.add_text()
        self.make_view(_("Sign-off Message"), val1, val2)
        disable_with_toggle(val1.child_widget, val2.child_widget)

        val = DratsConfigWidget(section="user", name="units")
        val.add_combo([_("Imperial"), _("Metric")])
        self.make_view(_("Units"), val)

        val = DratsConfigWidget(section="prefs", name="useutc")
        val.add_bool()
        self.make_view(_("Show time in UTC"), val)

        val = DratsConfigWidget(section="settings", name="ping_info")
        val.add_text(hint=_("Version and OS Info"))
        self.make_view(_("Ping reply"), val)

        # Need to know all the locales on the system
        locale_list = Platform.get_locales()

        drats_languages = {}
        language_list = []
        # Now look for what languages we have translations for.
        localedir = os.path.join(Platform.get_platform().sys_data(),
                                 "locale","*","LC_MESSAGES","D-RATS.mo")
        for mo_file in glob.glob(localedir):
            parts = Path(mo_file).parts
            part_index = 0
            for part in parts:
                part_index += 1
                if part == 'locale':
                    language_code = parts[part_index]
                    # Fall back to the language name.
                    language_name = language_code
                    language = None
                    # Allow the pycountry package to be
                    if HAVE_PYCOUNTRY:
                        language = languages.get(alpha_2=language_code)
                        if language:
                            language_name = language.name
                    lang_info = {}
                    lang_info['code'] = language_code
                    lang_info['name'] = language_name
                    lang_info['countries'] = []
                    drats_languages[language_code] = lang_info
                    language_list.append(_(language_name))

        # Now need to find the locales on the system to go with the
        # drats languages installed.
        # This should be eventually be cached at first call the the
        # config UI.
        for sys_locale in locale_list:
            sys_lang_code = sys_locale[0:2]
            if not sys_lang_code in drats_languages:
                continue
            # found a language we have now get the country for it.
            country_code = sys_locale[3:5]
            country_name = country_code
            if HAVE_PYCOUNTRY:
                country = countries.get(alpha_2=country_code)
                if country:
                    country_name = country.name
            drats_languages[sys_lang_code]['countries'].append(country_name)

        val = DratsConfigWidget("prefs", "language")
        val.add_combo(language_list)
        self.make_view(_("Language"), val)
        language_val = val

        def get_countries(my_language):
            '''Return list of countries for a language.'''
            language_code = DEFAULT_LANGUAGE_CODE
            country_names = [DEFAULT_COUNTRY]
            if len(my_language) == 2:
                language_code = my_language
            if HAVE_PYCOUNTRY:
                try:
                    language = languages.get(name=my_language)
                    if language:
                        language_code = language.alpha_2
                except LookupError:
                    self.logger.info(
                        "System does not have %s locale package installed.",
                        my_language)
                if language_code in drats_languages:
                    country_names = drats_languages[language_code]['countries']
            return country_names

        def lang_changed(language_box, country_box):
            '''
            Combo Box changed handler.

            :param combo_box: Entry widget
            :type combo_box: :class:`Gtk.ComboBoxText`
            '''
            new_language = language_box.get_active_text()
            country_box.remove_all()
            new_countries = get_countries(new_language)
            for country in new_countries:
                country_box.append_text(country)
            country_box.set_active(0)

        val = DratsConfigWidget("prefs", "country")
        my_language = self.config.get('prefs', 'language')
        country_list = get_countries(my_language)
        val.add_combo(country_list)
        language_val.child_widget.connect("changed",
                                          lang_changed, val.child_widget)

        self.make_view(_("Country"), val)

        mval = DratsConfigWidget(section="prefs", name="blink_messages")
        mval.add_bool()

        cval = DratsConfigWidget(section="prefs", name="blink_chat")
        cval.add_bool()

        fval = DratsConfigWidget(section="prefs", name="blink_files")
        fval.add_bool()

        event_val = DratsConfigWidget(section="prefs", name="blink_event")
        event_val.add_bool()

        self.message_group(_("Blink tray on"),
                           _("Incoming Messages"), mval,
                           _("New Chat Messages"), cval,
                           _("Incoming Files"), fval,
                           _("Received Events"), event_val)
