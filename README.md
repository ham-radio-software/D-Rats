# D-RATS

D-RATS is a communications tool for D-STAR amateur radio low-speed data
(DV mode). It provides: Multi-user chat capabilities; File transfers
Structured data transport (forms); and Position tracking and mapping.

## Copyright note

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

---

### Original Author

Dan Smith (KK7DS)

### Maintainers

Maurizio Andreotti IZ2LXI
John E. Malmberg WB8TYW
<https://github.com/ham-radio-software/D-Rats>

## Introduction

D-Rats is a text and data communication tool over Amateur Radio
originally developed and copyrighted by 2008 Dan Smith <dsmith@danplanet.com>.

In 2015 maintenance of D-Rats was started Maurizio Andreotti, IX2LXI.

In 2020 John Malmberg converted the code to Python 3.

The idea here is to read the source, add some comments and eventually do some
modifications and share.

Luckily there is no obligation for anybody to use it, in particular if you are
happy with the one from Dan.

If this works for you I am happy, If it doesn't ...

### A note from Maurizio Andreotti

***Note for awareness and understanding***

I picked up D.Rats code as I needed the maps feature back and after some time I
released  (in 2015 and in 2019) for benefit of everybody.

The program is pretty much the one developed by Dan more than 10 years ago
based on libraries by the Python community which – in many cases - are not
supported anymore by anybody –  not to mention that the operating system
itself changed multiple times, and each of us has a different footprint of
applications installed, making each execution situation different. So there is
no promise from me that it will work on your PC.

Recompiling it (even unchanged) nowadays for Windows has been challenging and
implied going back to windows XP to ensure compatibility and a lot of hours of
tests and investigation, I am glad it works for me and some others.

It was difficult to get it work on my PC (Win10 and XP) with full access to
logs and realtime control of what happens (e.g. clicking on some d-rats
button, and looking d-rats behavior result and logs to sort out things).

If in your case it does not work, that is an unhappy case which I feel it will
continue not working until some magic happens (in particular if there is not
valuable feedback provided to understand why it failed).

If you want to allow some investigation, but there is no obligation, it is
needed to share both the debug log, the config file in use and also describe
in detail the steps you did to open, configure, and use it.

Anyhow the code is published and anybody can go look into it and sort out
things.

---

## Supported systems

This should run on any system with currently supported Python 3 and a GTK 3
library.

There may be commercial Pythons that are free for non-commercial use that
may come with a GTK+ 3 library.  John Malmberg will not be testing any
product that requires a paid license for commercial use.  If someone wants
to contribute instructions on how to install on a Commercial Python to
<https://github.com/ham-radio-software/D-Rats/wiki> that will help others.

### Microsoft Windows

This generally requires installing the msys2 package from
<https://www.msys2.org/wiki/MSYS2-installation/>, which is what is currently
used for testing.

Other alternatives Windows Subsystem for Linux with a Linux installed or
Cygwin <https://www.cygwin.com/install.html>.  At the present time those
are not being tested.

### Linux and MAC OS-X

Current testing is primarily done with Anti-X Linux which is a Debian based distribution that will run on older systems with limited memory.

This version requires Python 3.7+ and GTK-3.

---

## Release notes

See the NEWS.rst file, and for unreleased code also see the changes
directory.

For the 0.3 releases see the change log:
<https://github.com/ham-radio-software/D-Rats/blob/master/changelog>

---

## FOR MORE INFO HAVE A WALK IN THE WIKI

<https://github.com/ham-radio-software/D-Rats/wiki>

---

## Running, Testing and Building packages

### Installing Python and packages

(contrib & credit Marius Petrescu)
Quick update by John Malmberg

See also <https://github.com/ham-radio-software/D-Rats/wiki>

You must have a compatible python3 and GTK 3 installed on the system to run
D-Rats as listed above.

For msys2, the script msys2_packages.sh will hopefully install all the
needed packages after you have installed msys2.  The "dev" parameter
is passed to install extra images needed for development, or installing
 directly from a git archive.

If the script is updating certain packages, it may need to have the msys2
windows shutdown after running, and then need to be re-run to complete the
install.

Repeat running the script until it no longer requests a msys2 restart.
Normally an msys2 restart or install should not require a reboot of
Microsoft Windows.

The installation steps are quite easy (assuming one has all the needed Python
libs installed):

Debian packages needed for running or development.

Below if you are not in a locale that is english, you will need the aspell-
variant dictionary for your locale.  Developers may need aspell- variant
dictionaries for all locales that D-rats has message files for.

The Python 2 packages are only needed for running the Python 2 version
of d-rats.

Anti-x 19 Can run the older d-rats using Python 2, and the newer D-rats using
Python 3

aspell aspell-en bandit(future) gedit python2 python3 pylint pylint3 glade
python-gobject python-gtk2 python3-gi python-glade2 python-serial
python3-serial python-libxml2 python-libxslt1 python3-lxml python-simplejson
python-feedparser python-flask python-gevent python3-gevent python-socketio
python3-greenlet python-ipykernel python-gi-cairo python-geopy python-pil
python3-simplejson python3-feedparser python3-flask python3-ipykernel
python3-gi-cairo python3-geopy python3-pil shellcheck codespell libxml2-utils
aspell-it yamllint

Anti-x 22 Can not run the older D-rats on Python 2, so only the Python 3
packages can be installed.

aspell aspell-en aspell-it bandit(future) codespell gedit glade libxml2-utils
pylint pylint3 python3 python3-feedparser python3-flask python3-geopy
python3-gevent python3-gi python3-gi-cairo python3-greenlet python3-ipykernel
python3-lxml python3-pil python3-pip python3-serial python3-simplejson
python3-sphinx python3_venv shellcheck yamllint

Other Python interpreters should be similar.  If the Python distribution does
not supply all of the packages, then PIP can be used to supply the missing
packages.  PIP generally should always be used with a Python virtual
environment.

See: <https://github.com/ham-radio-software/D-Rats/wiki/101.010-Running-D-Rats-in-a-Python-virtual-environment-and-PIP>

And read the rest of this document for more tips.

If you want to connect to WinLInk, you will need to install lzhuf.

The lzhuf source code is in its own repository and can easily be built on
most Linux or OS-X based systems.
<https://github.com/ham-radio-software/lzhuf>

If you locally build lzhuf on a Linux or Mac OS system, the lzhuf binary
built should be placed in /usr/local/bin for D-Rats to use it.

For some platforms, prebuilt lzhuf binaries may be available for download
from the files section of <https://groups.io/g/d-rats> group.

You must be a member of the <https://groups.io/g/d-rats> group and logged
in to the web page in order for thed ownload link of
<https://groups.io/g/d-rats/files/D-Rats>.

Currently prebuilt MSI packages are available for Microsoft Windows,
and Debian packages for some Debian and Ubuntu releases.

### Running directly from the D-rats source

Running directly from the D-rats source is easily done.

You can clone the git repository into a work directory so that you can
run the latest pre-release, or git allows you to download a compressed
archive of any commit or pull request.

Before running D-Rats there are two optional tasks if you want everything
to work.

If you want Winlink support to work, you need to download or build the lzhuf
binary,  which is now in its own repository as noted above.

If you want the internationalization to work, and especially if you want
to add more languages you have to build the message catalogs.

See <https://github.com/ham-radio-software/D-Rats/wiki/280---Translating-D-Rats-in-your-language>
for the easy steps for building and maintaining the message catalogs.

### Development of D-rats

D-rats is currently hosted on github.com as a git repository.

See the <https://github.com/ham-radio-software/D-Rats/wiki>
for the most current procedures for submitting Pull Requests.

### Build for INSTALL ON LINUX and MSYS2 and others

This should work for all platforms.

When a pull request is submitted, it should have a file put in the changes
directory for the tickets that resolves.

Note that we do not do the 'towncrier build' command.  The packaging
building process will to that.  You can use the 'towncrier build --draft'
command to see what will be appended to the NEWS.rst file.
See <https://pypi.org/project/towncrier/>

If you run the 'towncrier build' command by accident, you will need
revert the local changes that it makes to your checked out git repository.

Normally a git tag with a PEP-440 compliant version will be created before
the Python package build procedure is run, and you would check out that
commit for doing the build.

The current build procedure requires setting up a Python virtual environment
also referred to as a venv.
See: <https://github.com/ham-radio-software/D-Rats/wiki/101.010-Running-D-Rats-in-a-Python-virtual-environment-and-PIPP>

For Msys2, if you have made an update to the Msys2 packages, you may need
to delete and recreate your Python venv.

Activate the venv as per the link above.

Change the default to your D-Rats source directory

Install the packages needed for building into the venv.
issue 'pip install -r requirements.txt'

Microsoft Windows users may need to 'pip install pywin32 into the venv
depending which Python distribution they are using.  It is not needed for
Msys2.

Use 'pip freeze' to see what Python modules are currently installed.

You can upgrade PIP with the command given if yoo are getting a message
about it needing and upgrade.  With the venv activated all changes are
local to the venv.

If you are using a shared directory for multiple platforms, before
running the build procedure remove the old lzhuf binary so the setup
procedure will build the correct binary for the target.

Normally a Python package does not include a pre-built binary, and instead
runs a script to built on a Pip install.  That would add additional software
to be installed by the end user.

Issue 'python -m build'

The build script will use towncrier to build an updated NEWS.rst file.
It will modify the checked out git directory with the changes that it did.

If you are just testing the build process, then you need to revert those
changes from your local git checkout.

For a real release, these changes should be pushed as a followup pull
request for that branch and merged in.

The build procedure will create a dist directory if it does not exist and
create what is known as a tarball, and a wheel file.

We do not currently use the wheel file which has an extension of '.whl'.

The tarball has a double extension on it of ".tar.gz".  As compression
standards evolve, the extension of ".gz" may change to match.

Previously on MS-DOS and other platforms that only supported one dot in a
filename, the extension of ".tgz" was used instead of ".tar.gz", and that convention is still widely used on those platforms.

Before distributing the tarball, it should be renamed to be indicate the
platform and architecture in the name.

The built tarball name of 'D-Rats-0.3.10b2.dev301.tar.gz' has these parts:

- Name: 'D-Rats'

- Version: '0.3.10b2.dev301'

- Extension: '.tar.gz'

The platform specific designation is typically put between the version
and the extension, in the form of '-platform-arch'.

Each Operating System Distribution has conventions on what they use for
platform and version and these should be followed if known.

So a rename for Msys2 would be 'D-Rats-0.3.10b2.dev301-mingw-w64-x86_64.tar.gz'.

For Linux, it is probably more generic so that
'D-Rats-0.3.10b2.dev301-linux-x86_64.tar.gz' can be used.

I do not know what the name would be for Mac-OSX, we need some guidance from
the community.

### Install of a built tarball

To install from a tarball use the command with the path to the tarball.
The build step above puts the tarball in the dist directory.
You will have to adjust the tarball name for specific version.
In the example this is a development version that is 299 commits

For Msys2, I had to set my default directory to a different directory
than the development directory for the pip install to work.

pip install ./dist/D-Rats-0.3.3.10b2.dev300.tar.gz

you can now execute D-Rats from terminal:

> d-rats.py
> d-rats_repeater.py

This should do it. Main scripts are in /usr/local/bin, configuration and logs
will be found in the user's home directory as .d-rats-ev (a hidden directory).

---

## D-RATS CONFIGURATION AND LOG FILES

the D-Rats stores its configuration in the user home folder

- on linux this is here:
     /home/users/ [USERNAME] / ...

- on windows this is here:
    C:\Users\ [USERNAME] \AppData\Roaming\D-RATS
