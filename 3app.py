#!/usr/bin/env python3
import os
import gettext
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gettext import gettext as _

APP_NAME = "D-RATS"


class MultiLanguageApp(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title=_("D-RATS"))
        self.set_default_size(250, 150)

        # Create a label
        label = Gtk.Label()
        label.set_label(_("HELLO_WORLD"))

        # Create a button
        button = Gtk.Button.new_with_label(_("Click Me"))

        # Connect button click event
        button.connect("clicked", self.on_button_clicked)

        # Create a vertical box and add the label and button to it
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.pack_start(label, True, True, 0)
        box.pack_start(button, True, True, 0)

        # Add the box to the window
        self.add(box)

        # D-RATS IMPORTED INTERFACE
        # Update the text of translatable objects from the Glade file
        wtree = Gtk.Builder()
        wtree.set_translation_domain(APP_NAME)
        wtree.add_from_file("ui/mainwindow.glade")

        # Retrieve the main window object from the Glade file
        main_window = wtree.get_object("mainwindow")


        # Retrieve other translatable objects and set their text
        label_from_builder = wtree.get_object("main_menu_bcast")
        label_from_builder.set_label(_("Broadcast Text File"))
        
        label_from_builder = wtree.get_object("main_menu_exportmsg")                                      
        label_from_builder.set_label(_("Export Message"))

        label_from_builder = wtree.get_object("main_menu_importmsg")
        label_from_builder.set_label(_("Import Message"))        
        
        button_from_builder = wtree.get_object("button1")
        button_from_builder.set_label(_("Click Me"))


        # Show the main window
        main_window.show_all()




    def on_button_clicked(self, button):
        print(_("HELLO_WORLD"))
        label_from_builder = wtree.get_object("main_menu_importmsg")
        label_from_builder.set_label(_("IMPORTATO"))    

    def run(self):
        self.show_all()
        Gtk.main()


def main():
    # Set the LANG environment variable to Italian
    locale = "it"
    os.environ["LANG"] = locale

    # Set the PYTHONUTF8 environment variable
    os.environ["PYTHONUTF8"] = "1"

    # Initialize gettext for localization
    gettext.bindtextdomain(APP_NAME, "locale")
    gettext.textdomain(APP_NAME)
    gettext.bindtextdomain(APP_NAME, "locale")
    gettext.textdomain(APP_NAME)

    # Check if gettext works
    try:
        print(_("HELLO_WORLD"))
    except Exception as error:
        print("Error during translation:", error)

    # Create and run the application
    app = MultiLanguageApp()
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
