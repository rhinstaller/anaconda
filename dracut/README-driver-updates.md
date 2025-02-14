# Driver Update Disks Developer Documentation

_v1.0, Mon Feb 15 2016_

This document describes implementation details of how Driver Update Disks
(usually abbreviated DUD or DD) are loaded and used by the installer, as a
reference for developers working on the code.

**_NOTE: This is not a specification. Filenames, paths, and procedures may
change without warning. Avoid contact with eyes and skin and avoid inhaling
fumes. Keep out of reach of children and customers. Any resemblance to real
code, living or dead is purely coincidental._**

Most of the important code is in `driver_updates.py`, which uses the utilities
from `dracut/dd` to actually handle driver RPMs. There's also support code
sprinkled through this directory and in the installer itself, which will be
described below. But first...

# A Quick Overview

## What is a DUD?

A DUD (Driver Update Disk) is a disk (or disk image - typically a `.iso` file)
that contains some _metadata_ and one or more _repos_ which contain
_driver RPMs_ and/or _installer enhancement RPMs_.

## What are they for?

These are used to add kernel modules and/or userspace programs to the installer
*before* the installer's second stage is loaded. This is most commonly needed
when trying to install onto a system whose disk (or network) controllers are
not supported by the existing installer.

## How does it work?

Here's a short summary; please see below for important technical details of
each part of the process.

1. **Boot argument**: `inst.dd=<driverdisk>` specifies where to look for
   driver disks.
2. **Automatic DUD handling**: If a disk partition labeled `OEMDRV` is found
   during startup (before `udev` settles) it's assumed to be a driver disk.
3. **Interactive DUD selection**: The user may pass the argument `inst.dd`
   by itself to request interactive driver disk selection via a text menu.
   The user can choose a device to examine, pick an `.iso` image to load from
   (if multiple images are present), and choose individual drivers to load.
4. **Driver RPM selection**: `dd_list` is used to list the contents of a DUD
   repo; it will only list RPMs that have one of these headers, matching the current kernel/installer version:
     * `Provides: kernel-modules <version-expr>`
     * `Provides: installer-enhancement <version-expr>`
5. **Driver extraction**: For all matching RPMs, `dd_extract` extracts
   kernel modules and firmware (if the `kernel-modules` header was present)
   and binaries and libraries (if `installer-enhancement` was present)
   into the initrd and installer environment.
6. **Driver loading**: After processing each DUD, `driver_updates.py` runs
   `depmod` and tries to manually `modprobe` all extracted drivers.
7. **Repo copying and package listing**: `driver_updates.py` saves
   a list of the extracted package names and a copy of each DUD repo used into
   the installer environment. When `anaconda` runs, it enables any DUD repos
   it finds and adds all the named packages to the install transaction.

# Overall design notes

Here are a few things to keep in mind about the overall design of the DUD code.

1. **The real action happens in the dracut initqueue**

    We need both `udev` and `dracut` to be processing events so that other
    dependent events are handled as usual.

    It's tempting to think that we should just handle DUDs *before* the
    initqueue mainloop so that the devices will magically already be present
    when we start the initqueue, as if we had started with them loaded.
    Except then you need to start running `udevadm trigger` and `udevadm settle`
    yourself to make the DUD devices appear, and then handle them manually, and
    now you've gone and re-written the dracut mainloop.

    Too clever is stupid. Just use initqueue.

    *Any long-running action that's going to be performed inside
    one of the dracut scriptlets should be using `/sbin/initqueue` to add items
    to the initqueue instead of executing the code itself in-place.*

    (See, for example, the way `driver-updates-genrules.sh` handles DUDs that
    are already present inside the initramfs.)

2. **Let `dracut` handle devices and downloads**

    `dracut`'s main purpose in life is to bring up and initialize the devices
    needed to start the system (or, in this case, the installer image).

    Dracut's far better at handling disks and image mounting than Python is,
    and in general we want upstream dracut to be responsible for handling as
    much as possible of the bootup process. (That's kind of its job, after all.)

    *Anything that directly handles probing devices, downloading images,
    calling udev, etc. should be done in dracut scriptlets, not     `driver_updates.py`.*

    (The current invocation of `udevadm` that's in there should be moved to a
    dracut scriptlet as soon as we can get away with changing it.)

3. **Let `dd_list`/`dd_extract` handle driver RPMs**

    Neither `dracut` nor `driver_updates.py` should be messing with RPM headers,
    unpacking individual RPMs, etc.

    *Use `dd_list` to list the driver RPMs that are available in a repo, and
    use `dd_extract` to extract their contents. Don't mess with RPMs directly.*

4. **Use as little Python as possible in initrd**

    If you know Python better than dracut or C, it might be tempting to solve
    problems by hacking on the Python parts of the DUD code.
    This leads to redundant code - and more code for us to maintain.

    `driver_updates.py`'s purpose is basically just to mount disks or disk
    images and find valid DUD repos therein (either automatically or
    interactively), and to save needed data to places where the installer
    can find it later.

    *Any other tasks should be handled in dracut scriptlets,
    the C utilities, or the main installer program.*

    (If you must add Python code, avoid pulling in new libraries. It
    makes building images much more fragile and bloats the initramfs.)

# Boot arguments

The `inst.dd` (or `dd`) boot argument is used to specify the location of a
DUD to use, or to start interactive mode. It has three forms:

1. Network URLs
  * example: `inst.dd=http://host.fake.domain/path/to/dd.iso`
  * Target should be a `.iso` (or other disk image) or driver `.rpm`
  * Target will be downloaded and then handled appropriately
2. Block devices
  * examples: `inst.dd=cdrom:/dev/cdrom`, `inst.dd=hd:LABEL=DRIVERZ`
  * The `hd:` or `cdrom:` prefix is stripped
  * `TAG=VALUE` pairs are looked up using `blkid`
3. Interactive mode
  * `inst.dd` (or `dd`)
  * Brings up text-based menu:
    1. Choose from a list of disk devices
    2. (if device contains multiple `.iso` images) Choose an `.iso`
    3. Choose from a list of drivers found in the DUD

If one (or more) of these are specified, dracut will wait until all specified
`inst.dd` items have been handled before starting the main installer image.

# Automatic DUD handling (`OEMDRV`)

If no `inst.dd` boot argument is specified, dracut watches for a readable
disk partition labeled `OEMDRV`. If one appears before dracut finishes waiting
for required devices, it is automatically handled like a normal DUD.

## NOTE: device autodetection limitations

Once the kernel's device probing finishes, `udev` waits for and processes
responses from devices. Once every response has been handled and no more new
responses arrive for a short period of time (no less than 500ms), dracut assumes
all devices have been found and declares the system "settled".

If there's no response from any `OEMDRV` device by then, the installer starts
normally.

_Because disks can take some time to appear, an additional delay of 5 seconds
has been added.  This can be overridden by boot argument
`inst.wait_for_disks=<value>` to let dracut wait up to <value> additional
seconds (0 turns the feature off, causing dracut to only wait up to 500ms).
Alternatively, if the `OEMDRV` device is known to be present but too slow to be
autodetected, the user can boot with an argument like `inst.dd=hd:LABEL=OEMDRV`
to indicate that dracut should expect an `OEMDRV` device and not start the
installer until it appears._

# DUD filesystem layout

A driver updates disk may contain one or more driver repos, which are usually
laid out as follows:

    /
    |rhdd3   - DD marker, contains the DD's description string
    /rpms
      |  /i686 - contains RPMs for this arch and acts as package repo
      |  /x86_64
      |  /ppc64
      |  /...  - any other architecture the DD provides drivers for

In other words, a DUD is a directory containing:
1. a file named `rhdd3` (which contains the description for that DUD), and
2. a directory named `rpms/`, under which there is at least one directory
   which matches the output of `uname -m`. Under there are RPMs that contain
   the special DUD headers (see the next section for more info).

By convention, the "repos" under `rpms/` usually have yum metadata, but this is
not required or enforced by the tools. If there's no metadata present,
anaconda will run `createrepo` (or whatever the backend requires to make
that directory usable).

# Driver Updates RPM Headers

When `dd_list` examines a driver disk, it checks the `Provides:` headers of
each RPM to see if it provides either `kernel-modules` or
`installer-enhancement`. RPMs that contain kernel modules or firmware must
provide `kernel-modules`, and RPMs that contain libraries or binaries must
provide `installer-enhancement`.

## RPM header version matching

Usually the packages will have a header like one of
these:

    Provides: kernel-modules >= 3.6.9
    Provides: installer-enhancement >= 19

The given version comparison expression is compared against either the running
kernel or the installer version; if the kernel or installer matches the
expression, then the RPM is considered valid for use inside this installer
environment, and it will be listed by `dd_list`. Otherwise, `dd_list` (and,
therefore, the rest of the DUD code) will ignore that RPM.

Note that RPM operations are handled entirely by `dd_list` and `dd_extract`.

### `installer-enhancement` versioning

The DUD code does _not_ use the actual running installer version; instead it
hardcodes the value `19`. I think (at some point) there _were_ DUDs in
the wild that required this fact, and so it's just been left as-is.

If the Anaconda Add-on API changes, this version should *definitely* be changed.

# `dracut` component details

This section describes all the various bits of driver update support code that
live in `dracut` and how they get called or call each other.

## cmdline: `parse-anaconda-dd.sh`

If any `inst.dd=...` (or `dd=...`) arguments are found, this scriptlet parses
their values and writes appropriate values to `/tmp/dd_disk`, `/tmp/dd_net`, or
`/tmp/dd_interactive`, as follows:

1. Values that start with `http:`, `https:`, `ftp:`, or `nfs:` are assumed to
   be network URLs and get written to `/tmp/dd_net`.
2. Values of the form `hd:<dev>`, `cdrom:<dev>`, `file:<path>`, or `path:<path>`
   will have the `<dev>` or `<path>` part written to `/tmp/dd_disk`.
3. Any other value is assumed to be a disk device, and therefore also gets
   written to `/tmp/dd_disk`.
4. If a plain `dd` or `inst.dd` boot argument (without a value) is found, the
   word "menu" is written to `/tmp/dd_interactive`.

Finally, the contents of all three files are combined to create `/tmp/dd_todo`.

## pre-trigger: `driver-updates-genrules.sh`

This sets up the udev rules and dracut scriptlets that will handle any DUDs
that appear. Specifically:

1. If `/tmp/dd_todo` exists, call `anaconda-lib.sh:wait_for_dd()` so that
   dracut will not start the installer until `/tmp/dd.done` exists.
2. If `/tmp/dd_interactive` exists, add an initqueue item to start
   `driver-updates@.service` once the initqueue starts.
3. If `/tmp/dd_interactive` does *not* exist, add a udev rule to automatically
   handle any `OEMDRV` devices that appear.
4. For each item specified in `/tmp/dd_disk`, either:
    * create a udev rule that will execute `driver-updates --disk` when that
      disk appears, or
    * if the item is a DUD image that already exists in the initrd: add an
      initqueue item to run `driver-updates --disk` once the initqueue starts.
5. Set up a `initqueue/finished` scriptlet to force dracut to stay in the
   initqueue until `initqueue/settled` runs at least once.

## initqueue/online: `fetch-driver-net.sh`

This script runs every time a network device comes online and tries to handle
each image URL listed in in `/tmp/dd_net`, as follows:

1. If the URL is listed in `/tmp/dd_net.done`, it is skipped
2. The URL is fetched using dracut's `fetch_url` function
3. If the image is successfully downloaded:
   * append URL to `/tmp/dd_net.done`
   * run `driver-updates --net URL IMAGE`
4. Otherwise: if the fetch failed, warn the user and exit

## `parse-kickstart`

When `parse-kickstart` handles a `driverdisk` command it emits the appropriate
`inst.dd=` argument, which will then get parsed and handled as usual when
the `run_kickstart` function does its thing (see `anaconda-lib.sh` for
details on how `run_kickstart` works).

There's two valid forms for the `driverdisk` command - here's how those get
handled by `parse-kickstart`:

| kickstart command              | `parse-kickstart` output
|--------------------------------|--------------------------
| `driverdisk <partition>`       | `inst.dd=hd:<partition>`
| `driverdisk --source=<url>`    | `inst.dd=<url>`

Check the [kickstart documentation] for more info.

[kickstart documentation]: https://github.com/pykickstart/pykickstart/blob/main/docs/kickstart-docs.rst#driverdisk

## initqueue: `driver-updates@.service`

This service launches the interactive driver update menu.
It handles hiding the `plymouth` splash screen, quieting kernel messages,
and connecting the menu to the tty so that the user can select drivers.

This gets started from the initqueue by `driver-updates-genrules.sh`,
if interactive mode was requested.

## initqueue: `driver_updates.py`

Handles a single DUD request: extract and load drivers, save the DUD repo(s)
for later use, and keep track of which requests have been handled. (Also
handles the interactive mode - more on that below.)

**NOTE:** inside the initrd environment this file is named
`/bin/driver-updates`. (See `module-setup.sh` if you want to know more about
what files get put where inside the initrd.)

### Invocation

For disk devices, `driver-updates-genrules.sh` sets up a udev rule that will
run `/sbin/initqueue` to add an initqueue job which will run `driver-updates`.

For initrd-embedded images, `driver-updates-genrules.sh` skips udev and runs
`/sbin/initqueue` itself to add the job to the initqueue.

For network images, `fetch-driver-net.sh` (in the `initqueue/online` hook) runs
`driver-updates` itself.

### Arguments

* `driver-updates --disk PART DEVNODE`
* `driver-updates --net URL LOCALFILE`

In both cases, the first argument is the string provided by the user - either
the partition specifier (like `LABEL=DRIVERS`) or the URL. This string will
also be in `/tmp/dd_net` or `/tmp/dd_disk`, and `/tmp/dd_todo`.

The second argument is the actual image or device node to be mounted and
processed. Dracut is responsible for downloading images or finding the disk
device and passing that to `driver-updates` here.

In the case of `inst.dd=file:/dd.img`, both items will be `/dd.img`.

### Driver Updates Disk Handling

Here, roughly, is how `driver-updates` handles a DUD:

1. Mount the disk (the `DEVNODE` or `LOCALFILE` argument above)
2. For all valid `rhdd3` repos found, list the RPMs using `dd_list`
    * A valid repo is a directory containing a file named `rhdd3` and a
      subdirectory named `rpms/$ARCH`.
      (See [DUD filesystem layout](#dud-filesystem-layout), above)
3. For all matching RPMs found, `dd_extract` the RPM into `/updates`
    * `/updates` is overlaid onto the installer image when we switch there
4. If the package contains drivers, write the name of the package to
   `/run/install/dd_packages`
5. If the current repo had any driver RPMs, copy it to
   `/run/install/DD-1` (`DD-2`, `DD-3`, etc.)
6. Load all the drivers that were extracted:
    1. Copy the drivers and firmware to the `updates/` dirs:
        * `/lib/modules/$(uname -r)/updates/`
        * `/lib/firmware/updates/`
    2. Run `depmod -a` and then `modprobe -a <module names>`
4. Append the `PART` or `URL` argument string to `/tmp/dd_finished`
5. If every item in `/tmp/dd_todo` is now also in `/tmp/dd_finished`,
   create `/tmp/dd.done` so dracut knows it can exit the initqueue.

### Bash helper scripts called from driver_updates.py

* anaconda-ifdown
    * This script sets the interface down and removes all flags in dracut for
      future re-setting. This is useful for replacing existing network drivers.

* find-net-intfs-by-driver
    * Find all network interfaces which depend on the given driver (command
      line argument), then return a list of the network interfaces.

## pre-pivot: `anaconda-depmod.sh`

If any drivers were installed or downloaded, run depmod on `$NEWROOT` so we can
load the drivers later, if needed.

(To determine whether drivers were installed it simply checks to see if
`/run/install/DD-1` exists.)

# Testing

Testing the DUD code is a little tricky, since it's pretty hardware dependent.
Here are some tools and resources that should help if you're trying to test the
DUD code.

## Integration tests & unit tests

There are unit tests for `driver_updates.py` in
`tests/dracut_tests/test_driver_updates.py`. Please do add test cases for
any bugs that are found or new methods that get added.

There are also some tests for `dd_list` and `dd_extract`, in
`tests/dd_tests/dd_test.py`. These tests ensure that the utilities behave the
way that `driver_updates.py` expects them to.

(These tests run as part of the normal suite of tests that run during
`make check`.)

Finally, the [kickstart-tests] repo has at least one functional/integration
test for the `driverdisk` command. It also contains a helper program,
`mkdud.py`, which can be used to generate (fake) DUD images for test purposes.

[kickstart-tests]: https://github.com/rhinstaller/kickstart-tests

## Real-world DUD images

Here's a Red Hat Knowledgebase article that links to some Red Hat-provided
images: https://access.redhat.com/articles/64322 (Sadly, you have to log in to
download them)

# References

Old driverdisc docs from the RHEL7 [anaconda source]:

* [docs/driverdisc.rst]: describes the driver disc format and motivations for
  its design.
* [dracut/README-dd]: developer documentation on the dd code in dracut.

[anaconda source]: https://github.com/rhinstaller/anaconda
[docs/driverdisc.rst]: https://github.com/rhinstaller/anaconda/blob/rhel7-branch/docs/driverdisc.rst
[dracut/README-dd]: https://github.com/rhinstaller/anaconda/blob/rhel7-branch/dracut/README-dd
