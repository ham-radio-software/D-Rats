# D-RATS

D-RATS is a communications tool for D-STAR amateur radio low-speed data
(DV mode). It provides: Multi-user chat capabilities; File transfers
Structured data transport (forms); and Position tracking and mapping.

## License note

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

The installation is now primarily done from inside the MobaXterm application
using.
<https://github.com/ham-radio-software/D-Rats/wiki/010.020-Installation-of-D%E2%80%90Rats-on-Microsoft-Windows-with-MobaXterm>

This generally requires installing the msys2 package from
<https://www.msys2.org/wiki/MSYS2-installation/>, which is what is currently
used for testing.

Other alternatives Windows Subsystem for Linux with a Linux installed or
Cygwin <https://www.cygwin.com/install.html>.  At the present time those
are not being tested.  Windows Subsystem for linux may have issues accessing
serial devices.

### Linux and MAC OS-X

Current testing is primarily done with Raspbian Bookworm and Ubuntu 22.04
which are a Debian Linux based distributions.

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

The MobaXterm package contains a local Cygwin environment that is good
enough to run D-Rats.

The free MobaXterm can be download from
<https://mobaxterm.mobatek.net/download.html>
and then installed on a Microsoft Windows system.

If you already have a copy of the install script downloaded then you need
to delete it:

> rm -f d-rats_in_mobaxterm_install.sh

From the local terminal use the wget command to fetch the install script.

<!-- markdownlint-disable MD034 -->
> wget https://raw.githubusercontent.com/ham-radio-software/D-Rats/master/d-rats_in_mobaxterm_install.sh
<!-- markdownlint-enable MD034 -->

If you are testing a github Pull Request for a new copy of this script, then
you need to look up the "raw" URL for the script or you will be getting

The permission of the script may need to be fixed.
> chmod 0755 d-rats_in_mobaxterm_install.sh

Then run the script.  It will run for a bit and install everything needed to
run D-Rats
> ./d-rats_in_mobaxterm_install.sh

Then to run use:

> ./d-rats

The MobaXterm installs or updates d-rats from the master branch of the git
repository.  The MobaXterm is a new install and will not use any pre-existing
D-Rats configuration.  In MobaXterm, files in your windows drives can be
accessed by starting the path with /drives, as in /drives/c/ instead of c:\.

Cygwin install has not yet been tested.  MobaXterm uses Cygwin for some of its
Linux emulation, with a few changes.  MobaXterm uses a program named busybox
instead of the separate programs that Cygwin and Linux use and then creates
aliases to make it appear that the separate programs are installed.  Those
aliases can not be used in the install script and busybox must be used
instead, and Cygwin does not use an apt installer.

In theory with Cygwin, you can install all the packages that the MobaXterm
script installs with the Cygwin Gui installer and then use the commands from
the script for PIP installs, D-Rats should install on Cygwin.

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

D-Rats will now default to attempting to use the default locale as specified
for the system.  Some of the locale setting API settings are not working for
Msys2 on Windows-7 and currently have only been tested on Anti-X Linux.

A restart of D-Rats is needed after changing the country and language settings
in the configuration.  Invalid country and language setting changes will
probably result in some type of fallback behavior.

The shell command "locale" will show you what locale is set by default for
your system.  Changing the "LC_ALL" setting is what will affect D-Rats locale
use.

The shell command "locale -a" will show you all the locales that are
installed on your system.  D-Rats will only use the locales with the ".utf8"
suffix.

You may need to install additional locales on your system.

Debian packages needed for running or development.

Below if you are not in a locale that is english, you will probably want the
aspell-variant dictionary for your locale.  Developers may need aspell-variant
dictionaries for all locales that D-rats has message files for.
Not all platforms may have all aspell locales.

Anti-x 22 Can not run the older D-rats on Python 2.

aspell aspell-en aspell-it bandit(future) codespell gedit glade libcairo2-dev
libgirepository1.0-dev libxml2-utils pkg-config pylint pylint3 python3
python3-dev python3-feedparser python3-flask python3-geopy python3-gevent
python3-gi python3-gi-cairo python3-greenlet python3-ipykernel python3-lxml
python3-pil python3-pip python3-pyaudio python3_pycountry python3-pydub
python3-serial python3-simplejson python3-sphinx python3_venv shellcheck
yamllint

Other Python interpreters on other distributions should be similar.  If the
Python distribution does not supply all of the packages, then PIP can be
used to supply the missing packages.  PIP generally should always be used
with a Python virtual environment.

See: <https://github.com/ham-radio-software/D-Rats/wiki/101.010-Running-D-Rats-in-a-Python-virtual-environment-and-PIP>

And read the rest of this document for more tips.

If you want to connect to WinLink, you will need to install lzhuf.

The lzhuf source code is in its own repository and can easily be built on
most Linux or OS-X based systems.
<https://github.com/ham-radio-software/lzhuf>

If you locally build lzhuf on a Linux or Mac OS system, the lzhuf binary
built should be placed in /usr/local/bin for D-Rats to use it.

For some platforms, prebuilt lzhuf binaries may be available for download
from the files section of <https://groups.io/g/d-rats> group.

You must be a member of the <https://groups.io/g/d-rats> group and logged
in to the web page in order for the download link of
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

Make sure that you set your editors to use line-feeds line ends,
which may not be the default for Microsoft Windows tools.

### Build for INSTALL ON LINUX and MSYS2 and others

This should work for all platforms.

We use towncrier for maintaining the NEWS.rst file.
See <https://pypi.org/project/towncrier/>

When a pull request is submitted, it should have a file put in the
"changes" directory for the tickets that it resolves.

This file will have filename of the GitHub ticket number and a suffix of
".doc" for documentation change, ".bugfix" for bug fix, ".feature" for a
new feature, and ".misc" for most others.

Note that we do not do the 'towncrier build' command.  The packaging
building process will to that.  You can use the 'towncrier build --draft'
command to see what will be appended to the NEWS.rst file.

If you run the 'towncrier build' command by accident, you will need
revert the local changes that it makes to your checked out git repository.

Normally a git tag with a PEP-440 compliant version will be created before
the Python package build procedure is run, and you would check out that
commit for doing the build.

The current build procedure requires setting up a Python virtual environment
also referred to as a venv.
See: <https://github.com/ham-radio-software/D-Rats/wiki/101.010-Running-D-Rats-in-a-Python-virtual-environment-and-PIPP>

Activate the venv as per the link above.

Change the default to your D-Rats source directory

Install the packages needed for building into the virtual environment.

If you make any major upgrades to your development platform, you will likely
need to delete and recreate the virtual environment.

Issue 'pip install -r requirements.txt'.

You should be able to do add a "-U" after the install.  It will take
a lot longer to run, and I have only tested it on AntiX-21.
The upgrade option may not work because it may try to upgrade the
Gi/GOobject/GTK packages, and that does not work on all platforms at this
time.

Microsoft Windows users may need to 'pip install pywin32 into the venv
depending which Python distribution they are using.  It is not needed for
Msys2.

Use 'pip freeze' to see what Python modules are currently installed if you
are curious.

Issue 'python ./python_prebuild.py'

This does a preparation for creating a package.

The script all the internationalization message catalogs, and compresses some
documentation files.

The script will use towncrier to build an updated NEWS.rst file.
It will modify the checked out git directory with the changes that it did.

If you are just testing the build process, then you need to revert those
changes from your local git checkout.

After a real release is made, the default version in the file
d_rats/version.py should have DRATS_VERSION_NUM_DEFAULT set to the current
version.

The version.py and the towncrier created changes should be pushed as a
followup pull request for that branch and merged in.

Issue 'python -m build'

The build procedure will create a dist directory if it does not exist and
create what is known as a tarball, and a wheel file.

We do not currently use the wheel file which has an extension of '.whl' for
Msys2 or Linux.  It may be needed for Mac OS-X installs.

The tarball has a double extension on it of ".tar.gz".  As compression
standards evolve, the extension of ".gz" may change to match.

Previously on MS-DOS and other platforms that only supported one dot in a
filename, the extension of ".tgz" was used instead of ".tar.gz", and that
convention is still widely used on those platforms.

A tarball built on any platform should be usable on any other platform as
it does not contain any binaries or build any binaries when it is installed.

The built tarball name of 'D-Rats-0.3.10b2.dev301.tar.gz' has these parts:

- Name: 'D-Rats'

- Version: '0.3.10b2.dev301'

- Extension: '.tar.gz'

### Install of a built tarball

To install from a tarball use the command with the path to the tarball.
The build step above puts the tarball in the dist directory.
You will have to adjust the tarball name for specific version.
In the example this is a development version that is 299 commits

For Msys2, I had to set my default directory to a different directory
than the development directory for the pip install to work.

pip install ./dist/D-Rats-0.3.3.10b2.dev300.tar.gz

Note, due to some bug, this will fail on AntiX-21 linux until you issue
a command of 'pip install -U pip' to upgrade pip.  This may be needed
on other platforms.

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
