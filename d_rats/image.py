'''image.py'''
from __future__ import absolute_import
from __future__ import print_function

import logging
import tempfile
import os
if __name__ == "__main__":
    import sys

HAVE_PIL = False
try:
    from PIL import Image
    from PIL import UnidentifiedImageError
    HAVE_PIL = True
except ImportError:
    # This needs to be moved out of main_common
    from .ui.main_common import ask_for_confirmation

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

if not '_' in locals():
    import gettext
    _ = gettext.gettext


from . import inputdialog
from . import miscwidgets
# from . import dplatform #imported by kater apparently not used...

SIZES = [
    "160x120",
    "320x240",
    "640x480",
    "1024x768",
    "Original Size",
    "10%",
    "20%",
    "30%",
    "40%",
    "50%",
    "60%",
    "70%",
    "80%",
    "90%",
    ]


def update_image(filename, dlg):
    '''
    Update Image.

    :param dlg: Dialog widget
    :type dlg: :class:`Gtk.Widget`
    '''
    logger = logging.getLogger("update_image")
    reqsize = dlg.size.get_active_text()
    if "x" in reqsize:
        _h, _w = reqsize.split("x")

        height = int(_h)
        width = int(_w)
    elif "%" in reqsize:
        factor = float(reqsize[0:2]) / 100.0
        height, width = dlg.image.size

        width = int(width * factor)
        height = int(height * factor)
    else:
        height, width = dlg.image.size

    resized = dlg.image.resize((height, width))

    (base, _ext) = os.path.splitext(os.path.basename(filename))
    dlg.resized = os.path.join(tempfile.gettempdir(),
                               "resized_" + base + ".jpg")
    resized.save(dlg.resized, quality=dlg.quality)

    logger.info("Saved to %s", dlg.resized)

    file_handle = open(dlg.resized)
    file_handle.seek(0, 2)
    size = file_handle.tell()
    file_handle.close()

    dlg.sizelabel.set_text("%i KB" % (size >> 10))
    dlg.preview.set_from_file(dlg.resized)


def set_quality(_scale, _event, value, dlg):
    '''
    Set Quality.

    :param _scale: Unused
    :param _event: Unused
    :param value: Quality value to set
    :param dlg: Dialog to update
    :type dlg: :class:`Gtk.Dialog`
    '''
    dlg.quality = int(value)
    dlg.update()


def build_image_dialog(filename, image, dialog_parent=None):
    '''
    Build Image Dialog.

    :param filename: Filename for image
    :type filename: str
    :param image: Image
    :param dialog_parent: Parent widget
    :type dialog_parent: :class:`Gtk.Widget`
    :returns: Field Dialog
    :rtype: :class:`FieldDialog`
    '''
    dialog = inputdialog.FieldDialog(title="Send Image",
                                     parent=dialog_parent)

    def update():
        update_image(filename, dialog)

    dialog.add_field(_("Filename"), Gtk.Label.new(os.path.basename(filename)))

    dialog.sizelabel = Gtk.Label.new("--")
    dialog.add_field(_("Size"), dialog.sizelabel)

    dialog.size = miscwidgets.make_choice(SIZES, False, SIZES[1])
    dialog.size.connect("changed", lambda x: update())
    dialog.add_field(_("Resize to"), dialog.size)
    adjustment = Gtk.Adjustment.new(value=50, lower=1, upper=100,
                                    step_increment=10, page_increment=10,
                                    page_size=0)
    quality = Gtk.Scale.new(orientation=Gtk.Orientation.HORIZONTAL,
                            adjustment=adjustment)
    quality.connect("format-value",
                    lambda s, v: "%i" % v)
    quality.connect("change-value", set_quality, dialog)
    dialog.add_field(_("Quality"), quality)

    dialog.preview = Gtk.Image()
    dialog.preview.show()
    scrollw = Gtk.ScrolledWindow()
    scrollw.add(dialog.preview)
    scrollw.set_size_request(320, 320)
    dialog.add_field(_("Preview"), scrollw, full=True)

    dialog.set_size_request(400, 450)

    dialog.image = image
    dialog.resized = None
    dialog.quality = 50

    dialog.update = update
    dialog.update()

    return dialog


def send_image(filename, dialog_parent=None):
    '''
    Send Image.

    :param dialog_parent: Parent widget, Default None
    :type dialog_parent: :class:`Gtk.Widget`
    :returns: Path to temporary image file
    :rtype: str
    '''
    logger = logging.getLogger("update_image")
    if not HAVE_PIL:
        logger.info("Python pillow library is not installed.")
        msg = _("No support for resizing images.  Send unaltered?")
        if ask_for_confirmation(msg, dialog_parent):
            return filename
        return None
    try:
        img = Image.open(filename)
    except UnidentifiedImageError:
        dialog = Gtk.MessageDialog(buttons=Gtk.BUTTONS_OK, parent=dialog_parent)
        dialog.set_property("text", _("Unknown image type"))
        dialog.run()
        dialog.destroy()
        return None

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    dialog = build_image_dialog(filename, img, dialog_parent)
    run_status = dialog.run()
    temp_file = dialog.resized
    dialog.destroy()

    if run_status == Gtk.ResponseType.OK:
        return temp_file
    return None


def main():
    '''Main for Unit testing.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("image")

    # pylint: disable=global-statement
    global _
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()
    _ = lang.gettext

    try:
        temp_file = send_image(sys.argv[1])
        if temp_file:
            logger.info("sent_image_name %s", temp_file)
        else:
            logger.info('send_image returned None!')
    except IndexError:
        logger.info("Image filename required!")

if __name__ == "__main__":
    main()
