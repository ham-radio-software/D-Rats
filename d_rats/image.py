from __future__ import absolute_import
from __future__ import print_function
import gtk
import tempfile
import os

from . import inputdialog
from . import miscwidgets
from . import dplatform #imported by kater apparently not used...

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


def has_image_support():
    '''Has Image Support'''
    global IMAGE
    try:
        from PIL import Image
    except ImportError:
        try:
            import Image
        except ImportError:
            return False

    IMAGE = Image

    return True


def update_image(filename, dlg):
    '''Update Image'''
    reqsize = dlg.size.get_active_text()
    if "x" in reqsize:
        _h, _w = reqsize.split("x")

        h = int(_h)
        w = int(_w)
    elif "%" in reqsize:
        factor = float(reqsize[0:2]) / 100.0
        h, w = dlg.image.size

        w = int(w * factor)
        h = int(h * factor)
    else:
        h, w = dlg.image.size

    resized = dlg.image.resize((h, w))

    (base, _ext) = os.path.splitext(os.path.basename(filename))
    dlg.resized = os.path.join(tempfile.gettempdir(),
                               "resized_" + base + ".jpg")
    resized.save(dlg.resized, quality=dlg.quality)
    
    print("Saved to %s" % dlg.resized)

    f = open(dlg.resized)
    f.seek(0, 2)
    size = f.tell()
    f.close()

    dlg.sizelabel.set_text("%i KB" % (size >> 10))        
    dlg.preview.set_from_file(dlg.resized)


def set_quality(scale, event, value, dlg):
    '''Set Quality'''
    dlg.quality = int(value)
    dlg.update()


def build_image_dialog(filename, image, dlgParent=None):
    '''Build Image Dialog'''
    d = inputdialog.FieldDialog(title="Send Image",
                                parent=dlgParent)

    def update():
        update_image(filename, d)

    d.add_field(_("Filename"), gtk.Label(os.path.basename(filename)))

    d.sizelabel = gtk.Label("--")
    d.add_field(_("Size"), d.sizelabel)

    d.size = miscwidgets.make_choice(SIZES, False, SIZES[1])
    d.size.connect("changed", lambda x: update())
    d.add_field(_("Resize to"), d.size)

    quality = gtk.HScale(gtk.Adjustment(50, 1, 100, 10, 10))
    quality.connect("format-value",
                    lambda s,v: "%i" % v)
    quality.connect("change-value", set_quality, d)
    d.add_field(_("Quality"), quality)

    d.preview = gtk.Image()
    d.preview.show()
    sw = gtk.ScrolledWindow()
    sw.add_with_viewport(d.preview)
    sw.set_size_request(320,320)
    d.add_field(_("Preview"), sw, full=True)

    d.set_size_request(400, 450)

    d.image = image
    d.resized = None
    d.quality = 50

    d.update = update
    d.update()

    return d


def send_image(filename, dlgParent=None):
    '''Send Image'''
    if not has_image_support():
        msg = _("No support for resizing images.  Send unaltered?")
        from .ui import main_common
        if main_common.ask_for_confirmation(msg, dlgParent):
            return filename
        else:
            return None

    try:
        img = IMAGE.open(filename)
    except IOError as err:
        print("%s: %s" % (filename, err))
        dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK, parent=dlgParent)
        dialog.set_property("text", _("Unknown image type"))
        dialog.run()
        dialog.destroy()
        return None

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    dialog = build_image_dialog(filename, img, dlgParent)
    run_status = dialog.run()
    temp_file = dialog.resized
    dialog.destroy()

    if run_status == gtk.RESPONSE_OK:
        return temp_file
    else:
        return None


def main():
    '''Main for Unit testing'''
    import sys

    import gettext
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

    supported = has_image_support()

    if supported:
        try:
            temp_file = send_image(sys.argv[1])
            if temp_file:
                print("sent_image_name %s" % temp_file)
            else:
                print('send_image returned None!')
        except IndexError:
            print("Image filename required!")
    else:
        print('No image Support found!')


if __name__ == "__main__":
    main()
