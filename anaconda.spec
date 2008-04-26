%define livearches %{ix86} x86_64 ppc ppc64

Summary: Graphical system installer
Name:    anaconda
Version: 11.4.0.77
Release: 1
License: GPLv2+
Group:   Applications/System
URL:     http://fedoraproject.org/wiki/Anaconda

Source0: anaconda-%{version}.tar.bz2

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

# Versions of required components (done so we make sure the buildrequires
# match the requires versions of things).
%define dmver 1.02.17-6
%define gettextver 0.11
%define intltoolver 0.31.2-3
%define libdhcpver 1.99.8-1
%define libnlver 1.0
%define libselinuxver 1.6
%define mkinitrdver 5.1.2-1
%define pykickstartver 0.96
%define rpmpythonver 4.2-0.61
%define slangver 2.0.6-2
%define yumver 2.9.2
%define rhplver 0.170
%define partedver 1.8.1
%define syscfgdatever 1.9.0
%define pythonpyblockver 0.24-1
%define libbdevidver 5.1.2-1
%define rhpxlver 0.25
%define desktopfileutilsver 0.8

BuildRequires: audit-libs-devel
BuildRequires: booty
BuildRequires: bzip2-devel
BuildRequires: device-mapper-devel >= %{dmver}
BuildRequires: e2fsprogs-devel
BuildRequires: elfutils-devel
BuildRequires: gettext >= %{gettextver}
BuildRequires: gtk2-devel
BuildRequires: intltool >= %{intltoolver}
BuildRequires: isomd5sum-devel
BuildRequires: libX11-devel
BuildRequires: libXt-devel
BuildRequires: libXxf86misc-devel
BuildRequires: libdhcp-devel >= %{libdhcpver}
BuildRequires: libnl-devel >= %{libnlver}
BuildRequires: libselinux-devel >= %{libselinuxver}
BuildRequires: libsepol-devel
BuildRequires: libxml2-python
BuildRequires: mkinitrd-devel >= %{mkinitrdver}
BuildRequires: newt-devel
BuildRequires: pango-devel
BuildRequires: popt-devel
BuildRequires: pykickstart >= %{pykickstartver}
BuildRequires: python-devel
BuildRequires: python-urlgrabber
BuildRequires: rhpl
BuildRequires: rpm-python >= %{rpmpythonver}
BuildRequires: slang-devel >= %{slangver}
BuildRequires: xmlto
BuildRequires: yum >= %{yumver}
BuildRequires: zlib-devel
%ifarch %livearches
BuildRequires: desktop-file-utils
%endif

Requires: policycoreutils
Requires: rpm-python >= %{rpmpythonver}
Requires: comps-extras
Requires: rhpl >= %{rhplver}
Requires: booty
Requires: parted >= %{partedver}
Requires: pyparted >= %{partedver}
Requires: yum >= %{yumver}
Requires: libxml2-python
Requires: python-urlgrabber
Requires: system-logos
Requires: pykickstart >= %{pykickstartver}
Requires: system-config-date >= %{syscfgdatever}
Requires: device-mapper >= %{dmver}
Requires: device-mapper-libs >= %{dmver}
Requires: dosfstools
Requires: e2fsprogs
%ifarch %{ix86} x86_64 ia64
Requires: dmidecode
%endif
Requires: python-pyblock >= %{pythonpyblockver}
Requires: libbdevid >= %{libbdevidver}
Requires: libbdevid-python
Requires: audit-libs
Requires: libuser-python
Requires: newt-python
Requires: authconfig
Requires: gnome-python2-gtkhtml2
Requires: system-config-firewall
Requires: cryptsetup-luks
Requires: mdadm
Requires: lvm2
Requires: util-linux-ng
%ifnarch s390 s390x ppc64
Requires: rhpxl >= %{rhpxlver}
Requires: system-config-keyboard
%endif
Requires: hal, dbus-python
%ifarch %livearches
Requires: usermode
Requires: zenity
Requires(post): desktop-file-utils >= %{desktopfileutilsver}
Requires(postun): desktop-file-utils >= %{desktopfileutilsver}
%endif
Obsoletes: anaconda-images <= 10

%description
The anaconda package contains the program which was used to install your 
system.  These files are of little use on an already installed system.

%package runtime
Summary: Graphical system installer portions needed only for fresh installs
Group:   Applications/System
Requires: libxml2-python, python, rpm-python >= %{rpmpythonver}
Requires: anaconda = %{version}-%{release}
Requires: createrepo >= 0.4.7, squashfs-tools, mkisofs
%ifarch %{ix86} x86_64
Requires: syslinux
Requires: makebootfat
Requires: device-mapper
%endif
%ifarch s390 s390x
Requires: openssh
%endif
Requires: xorg-x11-font-utils, netpbm-progs
Requires: busybox-anaconda
Requires: isomd5sum
Requires: yum-utils >= 1.1.11-3
Requires: util-linux

%description runtime
The anaconda-runtime package contains parts of the installation system which 
are needed for installing new systems.  These files are used to build media 
sets, but are not meant for use on already installed systems.

%prep
%setup -q

%build
%{__make} depend
%{__make} %{?_smp_mflags}

%install
%{__rm} -rf %{buildroot}
%{__make} install DESTDIR=%{buildroot}

%ifarch %livearches
desktop-file-install --vendor="" --dir=%{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/applications/liveinst.desktop
%endif

%find_lang %{name}

%clean
%{__rm} -rf %{buildroot}

%ifarch %livearches
%post
/usr/bin/update-desktop-database %{_datadir}/applications
%endif

%ifarch %livearches
%postun
/usr/bin/update-desktop-database %{_datadir}/applications
%endif

%files -f %{name}.lang
%defattr(-,root,root)
%doc COPYING
%doc ChangeLog
%doc docs/command-line.txt
%doc docs/install-methods.txt
%doc docs/kickstart-docs.txt
%doc docs/mediacheck.txt
%doc docs/anaconda-release-notes.txt
%{_bindir}/mini-wm
%{_sbindir}/anaconda
%ifarch i386 x86_64
%{_sbindir}/gptsync
%{_sbindir}/showpart
%endif
%{_datadir}/anaconda
%{_prefix}/lib/anaconda
%ifarch %livearches
%{_bindir}/liveinst
%{_sbindir}/liveinst
%{_sysconfdir}/pam.d/*
%{_sysconfdir}/X11/xinit/xinitrc.d/*
%{_sysconfdir}/security/console.apps/*
%{_datadir}/applications/*.desktop
%endif

%files runtime
%defattr(-,root,root)
%{_prefix}/lib/anaconda-runtime

%triggerun -- anaconda < 8.0-1
/sbin/chkconfig --del reconfig >/dev/null 2>&1 || :

%changelog
* Fri Apr 25 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.77-1
- Preserve 'set the hostname' setting when going Next/Back (#443414) (dcantrell)
- Avoid traceback on network configuration screen (#444184) (dcantrell)
- Add missing backslashes for the .profile here document. (dcantrell)
- Label the efi boot filesystem on ia64 as well. (pjones)
- Don't use size to determine if a partition is an EFI system
  partition; instead, (pjones)
- Handle the DVD having a disknumber of ALL. (443291) (jkeating)
- Make the LUKS passphrase prompt fit on an 80x25 screen. (#442100) (dlehman)
- Don't dd the image from /dev/zero _and_ use
  "mkdosfs -C <image> <blockcount>" (pjones)
- label the filesystem in efidisk.img so that HAL and such won't try to
  mount it. (pjones)
- fix testiso Makefile target - boot.iso, not netinst.iso (wwoods)

* Thu Apr 24 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.76-1
- Use the execWithCapture wrapper to be consistent. (jgranado)
- Call the mdadm with full path. (jgranado)
- Use the correct ls(1) alias. (dcantrell)
- Set PS1 and ls(1) alias for tty2 shell. (dcantrell)
- Lookinig for the capabilities file in xen is valid in more cases. (jgranado)
- Avoid putting virtualization option when in Xen or VMware.
  (#443373) (jgranado)
- If the stage2 image is on a CD, don't bother copying it (#441336). (clumens)
- Once we've found the stage2 media on CD, always use it (#443736). (clumens)
- Change mount point for CD to /mnt/stage2 when looking for stage2
  (#443755). (clumens)
- Switch to using 'yum clean all' to clean up after preupgrade
  (#374921) (katzj)
- Handle .utf8 vs .UTF-8 (#443408) (katzj)
- Avoid dividing by zero (#439160) (katzj)
- Changes related to BZ #230949 (dcantrell)
- $XORGDRIVERS no longer exists (markmc)
- Bump version. (katzj)
- Write IPv6 values to /etc/sysconfig/... correctly (#433290) (dcantrell)
- Use the right base class for autopart handler. (clumens)

* Fri Apr 18 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.75-1
- Listing the directories before expiring yum caches helps (katzj)

* Fri Apr 18 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.74-1
- Don't look for .discinfo on the rescue CD (#442098). (clumens)
- Use /var/cache/yum as the cachedir since /tmp might be 
  too small (#443083). (clumens)
- Revert "Don't look for a .discinfo file in rescue 
  mode (jvonau, #442098)." (clumens)
- Revert "Fix figuring out that the CD has stage2 on it and should 
  be mounted." (clumens)
- We've always expected devices to be strings, not unicode (#443040) (katzj)
- Resizing lvs on top of RAID fails, make the error not a traceback (katzj)
- Don't put an extra slash on the error message (jgranado)
- Kernel changed howw the uevent API works for firmware 
  loading *AGAIN*. (pjones)
- Expose the log file descriptors so fwloader can avoid closing 
  them (pjones)
- Minor UI tweaks to passphrase dialogs (katzj)
- Nuke preupgrade cache once we're done (#442832) (katzj)
- Support bringing up the network if needed with preupgrade (#442610) (katzj)
- Use a real GtkDialog instead of some crazy hacked up dialog (katzj)
- Fix handling of pre-existing raids for the upgrade/rescue 
  case (#441770) (katzj)
- Add missing / (Doug Chapman, #442751) (katzj)

* Wed Apr 16 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.73-1
- Fix figuring out that the CD has stage2 on it and should be mounted. (clumens)
- Don't copy the stage2 image on NFS installs (#438377). (clumens)

* Tue Apr 15 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.72-1
- Don't use megabytes for the livecd size for copying. (notting)
- find moved (katzj)
- Fix up silly syntax error that crept in to this commit (katzj)
- Back to using the raw version of the docs (#442540) (katzj)
- Expire yum caches on upgrade (#374921) (katzj)
- Include KERNEL== in udev rules (#440568) (dwmw2)
- Don't look for a .discinfo file in rescue 
  mode (jvonau, #442098). (clumens)
- Slower machines may take more than five seconds for hal 
  to start (#442113) (katzj)
- Pass the full device path (notting)
- Only include the parts of grub that will work without 
  crazy tricks (#429785) (katzj)

* Thu Apr 10 2008 Peter Jones <pjones@redhat.com> - 11.4.0.71-1
- Fix destdir handling in upd-kernel (markmc)
- Get rid of module ball remnants in mk-images (markmc)
- Make upd-kernel handle version numbers the way we do them now (markmc)
- Fix ia64 kernel path problems (katzj, #441846)
- Don't tag more than one partRequest with mountpoint=/boot/efi (pjones)
- Don't treat tiny disks as EFI System Partitions during autopart (pjones)

* Thu Apr 10 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.70-1
- ide-cd_mod, not ide-cd_rom (thanks to jwb) (katzj)

* Wed Apr 09 2008 Peter Jones <pjones@redhat.com> - 11.4.0.69-1
- Ignore some warnings copying into /etc and /var (clumens)
- Try to mount the NFS source in the loader to verify it is correct (clumens)
- Be as clean as possible when looking for files/directories (jgranado, #431392)
- More ia64 kernel finding fixage (katzj, #441708)
- Fix read permissions on efidisk.img (pjones)
- Use the mount flags passed to isys.mount() (pjones)

* Wed Apr 09 2008 Peter Jones <pjones@redhat.com> - 11.4.0.68-2
- Fix device-mapper dep.

* Tue Apr 08 2008 Peter Jones <pjones@redhat.com> - 11.4.0.68-1
- Handle EFI partitions somewhat better (pjones)
- Fix typo in mk-images.efi's parted usage (pjones)

* Tue Apr 08 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.67-1
- Set the initial state of the auto-encrypt checkbutton (#441018) (katzj)
- Don't treat RAID devices as "disks" to avoid lots of odd
  behavior (#438358) (katzj)
- Log a message if we disable selinux on upgrade (katzj)
- Build efiboot.img on x86_64 and i386 . (pjones)
- When splitting srpms, only link srpms, nothing else. (jkeating)
- Don't cause the text to flicker between installed packages. (clumens)
- Don't cause the screen to jump up and down between
  packages (#441160). (clumens)
- Fix zooming and centering in the timezone screen (#439832). (clumens)
- Handle ia64 kernel path (katzj)
- And add nas to the list (#439255) (katzj)
- Set parent so that the dialog centers (#441361) (katzj)
- Don't show the label column (#441352) (katzj)
- Do string substitution after we've translated (#441053) (katzj)
- Set domain on glade file so translations show up (#441053) (katzj)
- fix compression of modules (notting)
- More build fixing due to translation breakage. (katzj)
- Add code to create efiboot.img on i386 and x86_64 (pjones)
- Remove gnome-panel too, it's no longer multilib. (jkeating)
- Fix raising new NoSuchGroup exception. (clumens)
- remove debugging print (notting)
- Support encrypted RAID member devices. (#429600) (dlehman)
- No longer require Amiga partitions on Pegasos (dwmw2)
- Don't copy the stage2 image every time or on the way back. (clumens)
- Make lukscb.get_data("encrypt") always return a valid value. (pjones)
- Set the scrollbar color so it doesn't surprise me the same way in
  the future. (pjones)
- Translation updates.

* Sun Apr 06 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.66-1
- Another day, another broken translation commit to fix. (katzj)
- Work around GL crashes in anaconda X by disabling them. (jkeating)
- Clean up "finishing upgrade" wait window (katzj)
- Stop refreshing like mad in text-mode on WaitWindow.refresh() (katzj)
- Avoid progress bars going off the end and making newt unhappy (katzj)
- Brute force hack to avoid the number of packages 
  overflowing (#436588) (katzj)
- Revert "Change the default level in /etc/sysconfig/init now 
  (#440058)." (notting)
- Add gnome-applets to the upgrade blacklist, fix kmymoney2 typo. (jkeating)
- Don't enable encryption by default (katzj)
- Print our mount commands to /dev/tty5 for easier debugging. (clumens)
- Change the default level in /etc/sysconfig/init now (#440058). (clumens)
- Make the Back button work when asking for tcp/ip information in 
  loader.c. (#233655) (jgranado)
- Have <F12> work in the network configuration stage (#250982) (jgranado)
- Use a better test to see if a package group doesn't exist (#439922). (clumens)
- avoid behavior in (#208970) (jgranado)
- Correctly label the xen images in the .treeinfo file (jgranado)
- Translation updates

* Wed Apr 02 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.65-1
- Only do verbose hal logging if loglevel=debug (katzj)
- Avoid AttributeError in HardDriveDict (#432362) (pjones)
- Don't use %n with gettext to avoid segfaults (#439861) (katzj)
- Require live installs to be to an ext2 or ext3 filesystem (#397871) (katzj)
- Don't allow migrations to ext4 for now (katzj)
- Change ext4 parameter to ext4, not iamanext4developer (katzj)
- Bootable requests can not be on logical volumes (#439270). (clumens)
- Don't allow /boot to be migrated to ext4 (#439944) (katzj)
- Fix for ia64 (#439876) (katzj)
- Update pkgorder group listings to match current Fedora defaults. (jkeating)
- Lame attempt to try to avoid race condition with udev creating device
  nodes (katzj)
- Don't traceback if stdout is an fd either (katzj)
- iutil doesn't need isys anymore (katzj)
- Free memory only after we're done using it (#439642). (clumens)
- Fix a segfault freeing memory on boot.iso+hdiso installs. (clumens)

* Mon Mar 31 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.64-1
- Fix my tyop (katzj)
- Fuzzy broken string again (katzj)

* Sun Mar 30 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.63-1
- Fix broken translations.  Again. (katzj)

* Sun Mar 30 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.62-1
- Translation updates
- Allow GPT disk labels on ppc/ppc64. (dcantrell)
- Tear down the right loopback device before going to stage2. (clumens)
- Don't pass None as stdout or stderr. (clumens)
- Make sure there's a stdout to write to. (clumens)
- Handle fstype munging in isys.readFSType instead of in various 
  other places. (dlehman)
- Fix a typo in new encrypted LV code. (dlehman)
- Partitioning UI for handling of preexisting encrypted devices. (dlehman)
- Support discovery of preexisting rootfs on LV. (dlehman)
- Improve handling of logical volume device names when encrypted. (dlehman)
- Add support for discovery of preexisting LUKS encrypted devices. (dlehman)
- Add support for retrieving LUKS UUIDs. (dlehman)
- Refresh po files (katzj)
- Mark for translation based on feedback from translators (katzj)
- Just relabel all of /etc/sysconfig (#439315) (katzj)
- When dhcp is selected ensure that bootproto is set to 
  dhcp (RPL-2301) (elliot)
- Fix for test mode repo bits (katzj)
- Try to make the size flow a little more for weird resolution 
  screens (#439297) (katzj)
- Add kmymoney to upgrade remove list (#439255) (katzj)

* Thu Mar 27 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.61-1
- Fix broken translation. (clumens)

* Thu Mar 27 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.60-1
- Have a fallback empty description for devices (#432362) (katzj)
- os.path.join does not work the way we think it should. (clumens)
- Remove the stage2 in all cases now that we're copying it basically
  all the time (katzj)
- Add support for saving the exception to a local directory for live
  installs (katzj)
- Catch errors on resize and present a dialog to the user (katzj)
- Save resize output to a file (/tmp/resize.out) so that it's more
  useful (katzj)
- Make sure we give the command that's run on stdout so that it's
  logged (katzj)
- more mouse-related removals (notting)
- Fix up autopart resizing for the multiple partitions to resize case (katzj)
- Fix up the case where both method= and stage2= are given (katzj)
- Remove mouse screens that haven't been used in 4 years (katzj)

* Wed Mar 26 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.59-1
- Only remove duplicate slashes from the front of the prefix. (clumens)
- Ensure that we take into account new repos (katzj)
- Handle kernel variants a little better at install time too (katzj)
- Make a little bit more future proof for kernel version changing (katzj)
- Add confirmation of closing the installer window (#437772) (katzj)
- Fix SIGSEGV on all mounts without options (katzj)
- Add support for encrypted logical volumes in kickstart. (clumens)
- Add support for encrypted LVs. (dlehman)
- Put in some handling for redundant method calls and devices containing '/'.
  (dlehman)

* Tue Mar 25 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.58-1
- Fuzzy broken string (katzj)

* Tue Mar 25 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.57-1
- Use anaconda-upgrade dir in the preupgrade case (katzj)
- Have 'preupgrade' key doing an upgrade (katzj)
- Fix what we expect to be the message from ntfsprogs (katzj)
- Fix up compile error for new newt (katzj)
- Don't traceback if we have little freespace partitions (#438696) (katzj)
- Translation updates (ko, ru)

* Mon Mar 24 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.56-1
- Translation updates (hi, fr, kn, de, ml, es, mr, ko, te)
- Fix up more unicode shenanigans (#437993) (katzj)
- Move /tmp/stage2.img to /mnt/sysimage to free up some 
  memory (#438377). (clumens)
- Be a little smarter about downloading repo metadata (#437972). (clumens)
- Make sure that devices are set up before using them. (#437858) (dlehman)
- Don't prepend /dev/ on bind mounts either. (clumens)
- Use the repo name instead of id in the group file error 
  message (#437972). (clumens)
- Handle /dev being on hard drive devices in the second stage (katzj)
- Fix the build (katzj)
- The units for /sys/block/foo/size aren't bytes.  Fixes finding some 
  disks (katzj)
- Remove the check for .discinfo on URL installs. (clumens)
- Always unmount /mnt/source on hdiso installs before starting 
  stage2. (clumens)
- Always unmount /mnt/source on nfsiso installs before starting 
  stage2. (clumens)
- Make sure the first disc image is mounted before setting up repos. (clumens)
- Fix $UPDATES for real (katzj)
- Avoid piling up slashes in the UI when retrying (#437516). (clumens)
- Require comps-extras now that we don't require pirut bringing it in (notting)
- Put "ide-cd_mod" in the list of modules to pull in. (pjones)

* Tue Mar 18 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.55-1
- Fix format of method=hd: parameter (#438075). (clumens)
- Work on support for NFSISO installs when using boot.iso. (clumens)
- If a file doesn't exist, don't continue trying to loopback mount
  it. (clumens)
- Make loopback mount error messages more useful. (clumens)
- Focus root password entry box (#436885). (dcantrell)
- Fix a traceback writing out the method string for hdiso installs. (clumens)
- Fix use of sizeof on a malloc()'d char ** (pjones)
- Fix up ppc boot check (#438005) (katzj)
- Support reading the UUID from the disk like we do with labels. (clumens)
- If the protected partition is not yet mounted, mount it now. (clumens)
- Don't add /dev/ to LABEL= or UUID= devices either. (clumens)
- Use arch instead of the name again in package nevra. (clumens)
- Fix traceback with preexisting LUKS partitions in setFromDisk.
  (part of #437858) (dlehman)

* Mon Mar 17 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.54-1
- Translation updates (de, fi, it, gu, ta, pa)
- Fix a typo. (clumens)
- Fix the build. (clumens)
- Make sure we return the same kind of exception in all cases. (clumens)
- Filter so we don't show LVM and RAID components when adding 
  boot entry (#437501) (katzj)
- Only print the filename we're fetching, as newt doesn't like 
  long names. (clumens)
- Fix off by one error reading .buildstamp (pjones)
- Use the right path when trying to fetch .discinfo. (clumens)
- Don't prepend /dev/ onto nfs devices.  Also log mount 
  errors to tty5. (pjones)

* Sun Mar 16 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.53-1
- Update translations (pl, de)
- Use i586 kernel (#437641) (katzj)
- Give indication of success or failure for mediacheck (#437577) (katzj)
- Ensure the UUID for the rootfs is random and not the same for every 
  live image (katzj)
- Make migration from ext3 -> ext4 saner on upgrade (#437567) (katzj)
- Force filesystem mount options on /boot/efi . (pjones)
- On HDISO installs, look for the stage2.img file in the right 
  directory. (clumens)
- Accept devices with or without a leading /dev/. (clumens)
- .buildstamp no longer contains productPath, so change 
  the default (#437509). (clumens)
- Remove references to an uninitialized variable. (clumens)
- Use shortname=winnt instead of shortname=win95 when 
  mounting /boot/efi (pjones)
- Do not strip leading or trailing whiltespace from 
  passphrases. (#437499) (dlehman)
- Set methodstr for nfsiso installs (#437541). (clumens)
- Create and check /boot/efi correctly, and use preexisting 
  one if available. (pjones)
- Handle /boot/efi and /boot both as bootrequests (pjones)
- Emit "efi" as /boot/efi's filesystem type (pjones)
- Add EFI handling to the bootloader setup choices. (pjones)
- Add efi to the ignoreable filesystem list. (pjones)
- Add EFIFileSystem, and getMountName() to hide that it's really vfat. (pjones)
- Add isEfiSystemPartition(), and use it where appropriate (pjones)
- Call getAutoPartitionBoot with our partition list as an arg. (pjones)
- Don't show the epoch in package selection either (#437502). (clumens)
- Fix some errors on reporting which files are being downloaded. (clumens)
- Revert "Handle /boot and /boot/efi separately, plus fixes" (pjones)
- Handle /boot and /boot/efi separately, plus fixes (pjones)
- Get rid of unused >1024 cylindar check, fix text of boot 
  check exceptions. (pjones)
- Make bootRequestCheck() check /each/ boot partition like it's 
  supposed to, (pjones)
- Fix shell quoting on numbers > 9, and fix an error message. (pjones)
- Don't show the epoch in the progress bar (#437502). (clumens)
- Include efibootmgr in the instroot (pjones)

* Thu Mar 13 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.52-1
- Don't unmount NFS source so NFSISO will work. (clumens)
- Fix the format of the method=hd: parameter. (clumens)
- Fix creating new users in kickstart. (clumens)
- "gtk-edit" isn't valid in text mode. (clumens)
- Ignore LUKS headers on partitions containing RAID signatures.
  (#437051) (dlehman)
- The xconfig command with no X running doesn't make sense. (clumens)

* Wed Mar 12 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.51-1
- yum.remove removes installed packages, not to be installed 
  packages (#436226) (katzj)
- Make the /tmp/updates vs RHupdates code at least a little readable. (pjones)
- Allow vfat update images. (pjones)
- Fix syntax error (pjones)
- Add a progress bar for when we're downloading headers (#186789). (clumens)
- mount will set up the loopback device if we let it. (clumens)
- Fix mounting problems with NFSISO images. (clumens)
- Simplify the logic for the upgrade arch check (katzj)
- Add a fallback method for determining the architecture of installed 
  system during an upgrade (#430115) (msivak)
- Avoid a traceback (#436826) (katzj)
- Make sure host lookups work for manual net config (#435574). (dcantrell)

* Tue Mar 11 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.50-1
- Focus root password entry box (#436885). (dcantrell)
- Make sure default is SHA-512 for libuser.conf. (dcantrell)
- Fix detection of ISO images on a hard drive partition. (clumens)
- Devices names aren't prefixed with /dev/. (clumens)
- Filter out /dev/ram* devices from the list of hdiso partitions. (clumens)
- But make sure that we've activated the keymap now that X 
  follows its defaults (katzj)
- Don't set a keyboard in the X config, we should just do this 
  at runtime (katzj)
- Writing out the nfs method line is a lot simpler now. (clumens)
- Use /mnt/sysimage/tmp/cache for the yum cache, instead of the 
  ramdisk. (clumens)
- Translation updates (nl, gu, ml, mr, pa)

* Mon Mar 10 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.49-1
- Use the full path to the .discinfo file (#436855). (clumens)
- List netinst.iso/boot.iso in .treeinfo (#436089) (katzj)
- Convinced to change the name back to boot.iso (katzj)
- Only pass the file path to {ftp,http}GetFileDesc. (clumens)
- Pass the correct NFS method parameter to stage2 (#436360). (clumens)
- Fix logging messages to not display the hostname twice. (clumens)
- Fix traceback with text mode adding iscsi (#436480) (katzj)

* Thu Mar 06 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.48-1
- Don't use the bits from $UPDATES unless $UPDATES exists (katzj)
- Fix horkage with busybox stuff.  There's now start-stop-daemon (katzj)
- Require new enough version of yum-utils (katzj)
- Pass the --archlist option to yumdownloader (jkeating)
- Update pt_BR translation

* Wed Mar 05 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.47-1
- Fix the build again (katzj)

* Wed Mar 05 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.46-1
- Don't require some things which we fall back gracefully when not there (katzj)
- Check for filesystem utilities to see if a filesystem is supported (katzj)
- Write out keyboard settings before installing packages. (related 
  to #429358) (dlehman)
- Update pl translation
- Make sure http:// or ftp:// is specified (#436089) (katzj)
- Fix segfault when port is specified (#435219) (katzj)
- Use ntfsresize -m to get minimum size (#431124) (katzj)
- Use the right path to the .discinfo file when validating a tree. (clumens)

* Tue Mar 04 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.45-1
- Fix the build.

* Tue Mar 04 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.44-1
- Add --archlist to repoquery call. (jkeating)
- Translation updates (pl, nl, ja)
- Handle efibootmgr and grub.efi in upd-instroot. (pjones)
- Merge in branch to implement stage2= parameter. (clumens)
- Revert the memtest86 bits for EFI, since this gets run on multiple arches. (pjones)
- Use iutil.isEfi() instead of testing for ia64-ness. (pjones)
- Only do gptsync if we're not using EFI. (pjones)
- Don't do gptsync if we're using EFI. (pjones)
- Use gpt on all efi platforms. (pjones)
- Rework isEfi() to be slightly more conservative. (pjones)
- Test for using efi rather than arch==ia64 (pjones)
- Don't copy memtest86 in on EFI since it won't work. (pjones)
- Add comment regarding usage of elilo (pjones)
- Free some variables so we can http GET twice if needed. (clumens)
- Change the method config prompts. (clumens)
- Support stage2= for CD installs in loader. (clumens)
- Support stage2= for HD installs. (clumens)
- Support stage2= for NFS installs. (clumens)
- Support stage2= for URL installs. (clumens)
- Update the method string handling for NFS and URL installs. (clumens)
- mountStage2 now needs to take an extra argument for updates. (clumens)
- If stage2= is given, it overrides the check for a CD stage2 image. (clumens)
- Support the stage2= parameter, and add a flag for it. (clumens)

* Mon Mar 03 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.43-1
- Only use UUID= for devices we would have labeled.  Related to #435228 (katzj)
- If we don't find a kernel package, then give a better error (katzj)
- Translation updates (cs, de)

* Sun Mar 02 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.42-1
- Fix a traceback when we have an error.  Related to #433658 (katzj)
- Add virtio_pci in hopes of getting virtio working (katzj)
- Pull in the bits of pirut that we use so that we don't depend on pirut (katzj)
- Default to RAID1 instead of RAID0 (#435579) (katzj)
- Refresh po (katzj)
- Fix traceback leaving task selection screen (#435556) (katzj)
- More ext4 vs ext4dev nonsense.  (#435517) (katzj)
- Fix reverse name lookup. (pjones)

* Thu Feb 28 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.41-1
- Don't write out /etc/rpm/platform anymore. (katzj)
- anaconda-runtime now needs yum-utils (katzj)
- Add 'testiso' target (katzj)
- Remove rescue cd creation scripts (katzj)
- Take --updates with location of additional updates beyond the package 
  set used (katzj)
- Change the ISOs we build (katzj)
- Take advantage of yum repos being available (katzj)
- Allow recovery from some missing repodata conditions. (clumens)
- Rework the repo editor screen to be more modular. (clumens)
- Move doPostImages to be run after the second stage build (katzj)
- Ensure that group info for txmbrs is accurate after we reset (katzj)
- Fix backwards logic for yum verbosity (katzj)
- No more arc (#435175) (katzj)
- Remove an unused method. (clumens)

* Tue Feb 26 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.40-1
- Use non-deprecated HAL properties. (notting)
- More crud to deal with the fact that rawhide trees are composed weird (katzj)
- Gtk does not have the error type, use custom with proper 
  icons. (#224636) (msivak)

* Mon Feb 25 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.39-1
- Fix up symlinks that could be broken with our movement here (#434882) (wwoods)
- pvops xen uses hvc as its console (#434763) (katzj)
- Follow symlinks when looking for the anaconda-runtime package. (jkeating)

* Sun Feb 24 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.38-1
- Write out UUID in the fstab (#364441) (katzj)
- Add support for getting UUID using libblkid (katzj)
- Fix calculation of sizes of LVs when resizing (#433024) (katzj)
- Add back some bits for text mode (katzj)
- Remove advanced bootloader bits (katzj)
- Add support for actually changing where the boot loader gets 
  installed as well (katzj)
- Less text. (katzj)
- Reorder things a little, clean up spacing (katzj)
- Use a tooltip instead of a long bit of text that most people 
  don't read (katzj)
- Remove advanced checkbox (katzj)
- Switch the grub installation radio to be a checkbutton.  Cleanups for 
  grub only (katzj)
- Lets redirect to /dev/null to ensure that what we get in DIR is the 
  result of pwd. (jgranado)
- Catch the error emmited by lvm tools during logical volume 
  creation process (#224636). (msivak)
- Don't try to lock /etc/mtab, fix error detection when mount fails. (clumens)
- Don't append (null) to the NFS mount options. (clumens)
- There's no need to wait if the last download retry failed. (clumens)
- the '-o' is appended to the mount command in imount.c (jgranado)
- Use full path to device for mount in findExistingRootPartitions. (dlehman)
- Map preexisting encrypted devs before mounting everything 
  in mountRootPartition. (dlehman)
- Fix traceback on test mount in findExistingRootPartitions. (dlehman)
- Use SHA-512 by default for password encryption. (dcantrell)
- Clean up root password user interfaces. (dcantrell)

* Tue Feb 19 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.37-1
- Default to the right timezone when language is changed (#432158). (clumens)
- Fix another text mode network config traceback (#433475). (clumens)
- More scripts cleanups. (jgranado)
- Remove more references to ARC (#433229). (clumens)
- Mount flags should be an optional argument (#433279, #433280). (clumens)
- We don't need productpath anymore, so stop taking it as an option (katzj)
- Set yum output level based on whether or not we've passed --debug or
  not (katzj)
- Clean up invocation of mk-images from buildinstall (katzj)
- Clean up invocation of upd-instroot from buildinstall (katzj)
- Remove some legacy stuff that's no longer relevant from
  .discinfo/.treeinfo (katzj)
- Don't depend on product path for finding the anaconda-runtime
  package (katzj)
- Make buildinstall a little clearer (katzj)
- Use $LIBDIR instead of lib globbing to avoid problems with chroots (katzj)
- Add some error handling around populateTs. (clumens)

* Thu Feb 14 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.36-1
- Fix up firmware inclusion.  This didn't actually ever work. (katzj)
- Fix up the groff related stuff for man pages to be done in the correct
  place (katzj)
- remove yumcache (katzj)
- Don't do fixmtimes anymore (katzj)
- Don't compress translations (katzj)
- Don't manually duplicate things from package %post scripts (katzj)
- Remove some unused options (--discs and --buildinstdir) (katzj)
- Keep /etc/nsswitch.conf and /etc/shells (katzj)
- Stop forcing passive mode for FTP by patching urllib (katzj)
- We don't use timezones.gz anymore anywhere (katzj)
- We shouldn't need to remove files that are only in -devel packages (katzj)
- Remove some obsolete files from the list to clean up noise in the
  output (katzj)
- We want nss bits on all arches these days (katzj)
- Just use default /etc/nsswitch.conf and /etc/shells (katzj)
- alpha should have translations probably (katzj)
- Remove some things that aren't used anymore (katzj)
- Don't run pkgorder as a part of buildinstall anymore (katzj)
- Remove duplicate file from the file lists (katzj)
- Don't use the static versions of these anymore as they're likely to go
  away (katzj)
- Remove weird s390 hack that shouldn't be needed any more (katzj)
- Make makebootfat less noisy (katzj)
- Get rid of dangling fobpath stuff; now that we're not mounting to
  create (katzj)
- Ignore .bak files created by glade (katzj)
- Get rid of duplication for yaboot stuff to make scripts less noisy (katzj)
- Correct internationalization of exception handler text (msw)
- More fixing of mount paths (#432720) (katzj)
- securitylevel -> firewall in the spec file. (clumens)
- Include util-linux-ng, which contains mount (#432720). (clumens)
- When mounting stage2 on loopback, add -o loop to mount opts. (clumens)

* Tue Feb 12 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.35-1
- Fix the build (katzj)

* Tue Feb 12 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.34-1
- Handle modules with more than one description (#432414) (katzj)
- Finish HDISO installs, at least for DVDs (#431132). (clumens)
- Move migration to before mounting filesystems (katzj)
- Fix silly thinko in Eric's patch (katzj)
- Allow ext3->ext4 upgrades (sandeen)
- Do the man pages in rescue mode the right way. (jgranado)
- Merge branch 'master' of ssh://git.fedorahosted.org/git/anaconda (notting)
- Use /etc/adjtime as the configuration file for UTC/not-UTC. (notting)
- Remove all our own mount code. (clumens)
- Use the mount program instead of our own code. (clumens)
- Add the real mount programs to stage1. (clumens)
- Use the correct variables to get the ipv6 info. (#432035) (jgranado)
- Update error messages to match function names. (dcantrell)
- Rename nl.c to iface.c and functions to iface_* (dcantrell)
- In rescue mode, show interface configuration (#429953) (dcantrell)
- Add qla2xxx firmware (#377921) (katzj)
- Rename base repo (#430806). (clumens)
- Remove dep on anaconda from pkgorder (katzj)
- Remove no longer used dumphdrlist script (katzj)

* Thu Feb 07 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.33-1
- Fix error message on continuing after changing cds with mediacheck (katzj)
- Fix the progress bar during mediacheck (#431138) (katzj)
- Ensure we disable SELinux if the live image isn't using it (#417601) (katzj)
- Correct nl_ip2str() cache iteration. (dcantrell)
- Check the fstype of the live image (katzj)
- Check for device existence rather than starting with /dev (katzj)
- The FL_TEXT flag has no reason to be here. (#207657) (jgranado)
- Don't traceback when getLabels is called with DiskSet.anaconda set
  to None. (dlehman)
- Pass arguments correctly to anaconda (katzj)
- Cancel on escape being pressed with autopart resizing (katzj)

* Wed Feb 06 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.32-1
- Make passwordEntry appear on the exn saving screen. (clumens)
- Don't allow disabling default repositories. (clumens)
- Make loopback device purposes line up with what stage2 expects. (clumens)
- Fix methodstr handling for hdiso installs (#431132). (clumens)
- Remove our own DNS functions, since glibc's are available now. (clumens)

* Tue Feb 05 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.31-1
- Copy over repodata from media after the install is done (#381721) (katzj)
- Add resizing support in autopartitioning (katzj)
- Fix test mode with python-fedora installed (katzj)
- Add support for encrypted devices in rescue mode (dlehman).
- Allow creation of LUKSDevice with no passphrase. (dlehman)
- Fix hdiso installs in loader and in methodstr (#431132). (clumens)
- Avoid infinite loop in nl_ip2str(). (dcantrell)
- Force users to set a hostname (#408921) (dcantrell)
- Forward-port RHEL-5 fixes for s390x issues. (dcantrell)
- fsset.py tweaks for ext4dev & xfs (sandeen)
- When editing the raid partitions show raid memebers. (#352721) (jgranado)
- mdadm to create the mdadm.conf (#395881) (jgranado)

* Wed Jan 30 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.30-1
- Initialize int in doConfigNetDevice() to fix compiler warnings. (dcantrell)

* Wed Jan 30 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.29-1
- Handle putting updates ahead of anaconda in the updates= case too. (clumens)
- Make sure the device name starts with /dev (#430811). (clumens)
- Revert "Initial support for network --bootproto=ask (#401531)." (clumens)
- (#186439)  handle lv names with "-" when doing kickstart. (jgranado)
- Remove the last references to makeDevInode (#430784). (clumens)
- Don't traceback trying to raise an exception when making
  users (#430772). (clumens)

* Mon Jan 28 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.28-1
- Go back to the method screen if back is hit on nfs config (#430477). (clumens)
- Fix dmidecode dependency (#430394, Josh Boyer <jwboyer)

* Fri Jan 25 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.27-1
- Fix generation of stage1 images. (notting)
- Fix a typo in mk-images. (clumens)
- Allow removing packages by glob now that yum supports it. (clumens)

* Thu Jan 24 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.26-1
- Fix a traceback on the driver selection screen (#428810). (clumens)
- Map 'nousb', 'nofirewire', etc. to be proper module blacklists. (notting)
- Clean off leading and trailing whitespace from descriptions. (notting)
- Write out /etc/rpm/platform on livecd installs. (clumens)

* Wed Jan 23 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.25-1
- Include new firstboot module. (clumens)
- Conditionalize ntfsprogs as not all arches include it. (clumens)
- Remove kudzu-probe-stub. (clumens)
- Remove rogue references to kudzu. (clumens)
- Add dogtail support (#172891, #239024). (clumens)
- Fix some error reporting tracebacks. (clumens)

* Tue Jan 22 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.24-1
- Avoid possible SIGSEGV from empty loaderData values. (dcantrell)
- Do not require glib2-devel for building. (dcantrell)
- Use libnl to get interface MAC and IP addresses (dcantrell)
- Don't refer to the libuser.conf when creating users (#428891). (clumens)
- pcspkr works (or isn't even present), per testing on #fedora-devel (notting)
- Inline spufs loading for ppc. (notting)
- Load iscsi_tcp, so that iSCSI actually works (notting)
- inline ipv6 module loading (notting)
- If we execWith a program, require the package containing it. (clumens)
- Add a repository editor. (clumens)
- Add the default repo to the UI so it can be edited later. (clumens)
- Fix non-latin-1 locale display in the loader. (notting)
- Make sure anaconda has precedence in the search path (#331091). (clumens)
- When starting RAID arrays, the device node may not already exist. (notting)
- Fix a typo that's breaking kickstart network installs. (clumens)
- Don't allow backing up to partitioning (#429618). (clumens)
- Update font paths. (clumens)

* Mon Jan 21 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.23-1
- Try to fix a problem creating users via kickstart (#428891, clumens)
- Fix a loader segfault doing kickstart nfs installs (clumens)
- Move more interactive steps ahead of partitioning (clumens)
- If we can't possibly add advanced devices, don't offer it (#429210, clumens)
- Don't flush after rescanning so recently attached disks are
  available (clumens)
- If bootproto is dhcp, unset any static settings (#218489, dcantrell)
- Add some groups to pkgorder to make the CDs come out right (pjones)
- Fix traceback when using non-encrypted RAID (notting)
- Complete the patch for dhcptimeout (#198147, #254032, msivak)

* Wed Jan 16 2008 David L. Cantrell Jr. <dcantrell@redhat.com> - 11.4.0.22-1
- Require the latest libdhcp (dcantrell)
- Don't set currentMedia when we're on a network install (#428927, clumens)
- Don't offer two reboot options (clumens)
- Remove fsopts that are already defaults (#429039, clumens)
- Remove isofs module to get rid of a FATAL message (clumens)
- Add the crc32c kernel module for iscsi (#405911, clumens)
- Add MAC address to the network device selection screen (#428229, clumens)
- Initial support for network --bootproto=ask (#401531, clumens)
- Remove an extra newline (clumens)
- Add firstaidkit to the rescue image (jgranado)
- Fix the progress bar to hit 100%% on the last package (#428790, clumens)
- Add some output so the startup delay doesn't seem quite so long (clumens)
- Initial kickstart support for encrypted partitions (clumens)

* Mon Jan 14 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.21-1
- Inherit from the right versions of pykickstart classes (clumens)
- Update for nss files moving to /lib (clumens)
- Remove unneeded arguments from detectHardware function (notting)
- Symlink all udev support binaries to udevadm (notting)
- /sbin/restorecon on /etc/modprobe.d (notting)
- Add the kickstart syntax version to the kickstart file (clumens)
- Require latest libdhcp to fix x86_64 SIGABRT problems

* Sun Jan 13 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.20-1
- Install new udev paths so HAL can talk to it (notting)
- Also get DSO deps for setuid binaries (like X). (clumens)
- Fix a bunch of pychecker errors. (clumens)

* Fri Jan 11 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.19-1
- Make sure the arch is listedat the top of all loader screens. (clumens)
- Add the version number really early in the log file too. (clumens)
- Require latest libdhcp (dcantrell)
- Add nicdelay parameter to loader, so we can wait before sending DHCP
  requests. (msivak)
- Add dhcpdelay to loader so we can modify the default dhcp timeout
  (#198147, #254032). (msivak)
- Fix the selected device when disabling entries in Add advanced drive
  dialog. (#248447) (msivak)
- Include mkfs.gfs2 (#356661). (clumens)
- Use the new default Japanese font (#428070). (clumens)
- More urlinstall loader fixes. (clumens)

* Wed Jan 09 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.18-1
- Fix encrypted autopart traceback. (dlehman)
- Allow for better recovery if the CD/DVD is bad. (clumens)
- If downloading the updates image fails, prompt for a new location. (clumens)
- X now relies on libpciaccess, so add it to our list. (clumens)
- Erase temporary packages after installing them on all methods. (clumens)

* Mon Jan 07 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.17-1
- Make text mode root password dialog default match GUI. (clumens)
- Fix a segfault in making the URL dialog box. (clumens)

* Sun Jan 06 2008 Chris Lumens <clumens@redhat.com> - 11.4.0.16-1
- Fix checking the timestamps on split media installs. (clumens)
- Fix reference to isodir to avoid a post-install traceback. (clumens)
- Use a better test when populating the URL panel in loader. (clumens)
- Don't use error messages from dosfslabel as the label (#427457). (clumens)
- No longer require kudzu (#427680). (clumens)

* Thu Jan 03 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.15-1
- Require latest libdhcp (#378641) (dcantrell)

* Thu Jan 03 2008 David Cantrell <dcantrell@redhat.com> - 11.4.0.14-1
- Precreate /etc/modprobe.d in installroot (jkeating)
- 'import sets' in image.py (jkeating)
- Fix traceback when displaying required media (clumens)

* Tue Jan 01 2008 Jeremy Katz <katzj@redhat.com> - 11.4.0.13-1
- Make it obvious which partitions are being formatted and encrypted (katzj)
- Set initial sensitivity of encrypt button correctly (katzj)
- Fix traceback on invalid passphrase (#426887) (katzj)
- Use mkstemp() instead of tempnam() (katzj)
- Don't resize filesystems which are being formatted (#426466) (katzj)
- Add cracklib-dicts (#426444) (katzj)
- Fix build (notting)

* Thu Dec 20 2007 Jeremy Katz <katzj@redhat.com> - 11.4.0.12-1
- Switch away from using kudzu in the loader (notting)
- Use udev in the loader and a dynamically linked stage1 (notting)
- Don't handle all aspects of module loading ourselves - just wrap 
  modprobe. (notting)
- Ensure there's an active net device (katzj)
- Fix error reporting messages (sfernand, #242252). (clumens)
- Don't immediately retry on downloading a package. (clumens)
- Update to work with new system-config-keyboard. (clumens)

* Mon Dec 17 2007 Jeremy Katz <katzj@redhat.com> - 11.4.0.11-1
- Validation of root password with cracklib (hhara)
- Minor fixes to liveinst shell script (katzj)
- Fix path to swapoff (katzj)
- Make doMethodComplete not depend on the yum backend (katzj)
- Remove another line related to the release notes (hhara)
- GPLv2+ changes. (dcantrell)

* Sat Dec 15 2007 Jeremy Katz <katzj@redhat.com> - 11.4.0.10-1
- Add support for encryption via autopart. (katzj)
- Avoid unnecessary downloading and caching by not
  setting mediaid (#422801). (clumens)
- Don't copy the stage2 image over for NFS installs. (clumens)
- Remove an unused function. (clumens)
- Allow going back to package selection after transaction errors. (clumens)
- Add file conflicts to the transaction errors we show the user. (clumens)
- Remove isomd5sum/.gitignore (dcantrell)

* Thu Dec 13 2007 Chris Lumens <clumens@redhat.com> - 11.4.0.9-1
- Update list of crypto mods to load. (dlehman)
- Create full paths before trying to make device nodes. (clumens)
- Unmont filesystems after looking for upgrade targets. (clumens)
- Update crypto module names to keep up with kernel. (dlehman)
- Add mnemonics and make password entry prompts consistent. (katzj)
- Clean up luksPassphrase validation UI. (hhara)
- Blacklist ext4 from being a bootreq. (katzj)
- Fix liveinst on the desktop for locales like pt_BR. (#417301) (katzj)
- Fix a traceback when picking HTTP/FTP method. (clumens)
- Use install system's IP address in kickstart file name. (#420281) (clumens)
- Remove call to makeDMNode. (notting)
- Fix retrying when looking for the install CD in loader. (clumens)

* Mon Dec 10 2007 Chris Lumens <clumens@redhat.com> - 11.4.0.8-1
- Include lshal for debugging (katzj)
- Remove isomd5sum in favor of libcheckisomd5. (notting, katzj)
- makeDevInode no longer exists. (clumens)
- Fix text mode to be able to autopartition (#409301) (katzj)
- Fix method-related tracebacks (katzj, clumens)
- Load ext2 module to allow installing to ext2 for livecd (#408251) (katzj)
- Catch errors from yum, exit on them. (notting)
- Switch to full dejavu-fonts, to match the installed OS default. (notting)

* Fri Dec 07 2007 Chris Lumens <clumens@redhat.com> - 11.4.0.7-1
- Tweak save-exception-to-disk algorithm. (notting)
- Merge the FTP and HTTP methods into a single URL method. (clumens)
- Fixes to the live install method (katzj)
- Use HAL and DBus for probing and device node creation in stage2. (notting)
- Get rid of /tmp/ramfs usage. (katzj)

* Thu Dec 06 2007 Chris Lumens <clumens@redhat.com> - 11.4.0.6-1
- Remove confirmation screen (katzj)
- Use a better cio_ignore line (#253075). (dcantrell)
- Remove the release notes code entirely. (clumens)
- Remove existing InstallMethod code. (clumens)
- Add a specfile rule to bump the version. (katzj)
- Make the tag an annotated tag (katzj)
- Fixup chunk of dwmw2's patch to be cleaner (katzj)
- Update mk-images.ppc for new zImage wrapper (#409691) (dwmw2)
- Remove gdb.i386 on upgrade (#407431) (katzj)
- device nodes are in /dev (or, at least, should be) (notting)

* Mon Dec  3 2007 Jeremy Katz <katzj@redhat.com> - 11.4.0.5-1
- Add support for the Efika platform (dwmw2)
- Fix some tracebacks (clumens, #405951)
- Actually include the crypto mods (dlehman)
- Include more nss libs (clumens, #405921)
- Remove some cruft (notting)
- Use libblkid instead of our custom code for fstype and label probing
- Fix tty switching in graphical install

* Thu Nov 29 2007 Jeremy Katz <katzj@redhat.com> - 11.4.0.4-1
- Initial support for partition and LV resizing.  VERY EXPERIMENTAL!
- Commit partitioning changes to disk earlier
- Add start of ext4 support
- Fix some tracebacks
- Add support back for alpha (Oliver Falk)

* Wed Nov 28 2007 Chris Lumens <clumens@redhat.com> 11.4.0.3-1
- Fix the build by no longer including broken kernel headers (katzj).
- Fix tracebacks when printing disk errors (#403501).
- Fix tracebacks in displaying the text mode exception dialog (#403381).

* Wed Nov 28 2007 Chris Lumens <clumens@redhat.com> 11.4.0.2-1
- Include libuser support libraries.
- Include nss libraries so rpm works again (#396851).
- Fix a traceback starting vnc mode.
- Make --excludedocs work again (#401651).
- Probe for USB on more busses (dwmw2, #401821).
- Add linear.ko to the modules available for rescue mode (#151742).
- Update implantisomd5 usage to give correct option name (#364611).
- Start removing unneeded install method code.
- Run %post scripts on upgrade (#392201).
- Correct nicdelay patch (msivak, #349521).
- Only run media check if we're installing off the CD (#362561).
- Fix display of package names in non-English text installs (#376231).
- Import isys (katzj, #390141).
- Fully handle pae kernel (katzj, #388231).
- Add initial support for encrypted block devices (dlehman).
- Strip out the wiki markup from docs (Paul Frields, #387341).
- Update Romanian keyboard layout and console font (#386751).

* Thu Nov 15 2007 Chris Lumens <clumens@redhat.com> 11.4.0.1-1
- Pull in the /lib/ld-linux.so.2 symlink to stage2.
- Don't segfault on unpartitioned updates devices (#372011).
- Log errors and continue when we can't copy files during livecd (#376741).
- Pull in glibc.i386 and openssl.i386 to stage2 (#367731).
- Fix Macedonian translation (#374561).

* Thu Nov 08 2007 Chris Lumens <clumens@redhat.com> 11.4-1
- Add nicdelay= command line option (msivak, #349521).
- Display more useful ks script error messages.
- Set re-IPL device before reboot on s390x (bhinson, Jan Glauber).
- Enable DASD formatting progress bar (Jan Glauber).
- Add memory error handling to module loading code (HARA Hiroshi).
- Add accelerator keys to the VG editor window (jgranado, #206479).
- Turn off swap and lvm earlier to avoid dmraid problems (katzj, #357401).
- Fix lang-names handling under parallel make (katzj, #358411).
- Rework VNC startup (jgranado, #264841).
- Fix help output for buildinstall (#355871).
- Pull docs from the new wiki location (katzj, #356021).
- Fix handling of XFS under livecd (katzj, #355351).
- Don't show bridged network devices (katzj, #354561).
- Fix handling of Sun disklabels (pjones).
- Add --fsprofile=, deprecate --bytes-per-inode (pjones).
- Rework exception handling dialog UI for future expansion.
- Use the right path for locking under livecd (notting, #354571).
- Add --disc-size= to splittree.py (#149234).
- Write kickstart log files to the right tree when chrooted (#338541).
- Offer to upgrade rpm platform on mismatched arch upgrades (msivak, #217132).
- Don't ask to initialize partition tables in rescue mode (msivak, #331131).
- Add CIFS tools to the rescue image (msivak).
- Fix displaying ampersands in the package progress bar (dcantrell).
- Ignore sg devices in the driveDict (katzj, #330931).
- Create the USB boot image with makebootfat (jgranado).
- Add ntfsprogs to the rescue image (jgranado, #220062).
- Fix retrying when booting off the CD and using a URL method (#330641).
- Allow users to use their own mke2fs.conf (pjones).
- Don't log critical errors if we can retry fetching (sfernand, #350251).
- Clean up usage of /tmp for device nodes (notting).
- Fix shlib dep finding in upd-instroot (Orion Poplawski, pjones).
- Fix runinst and hal-lock usage for livecd (katzj).
- Write out IPV6* variables to ifcfg-eth* correctly (dcantrell, #328931).
- Don't traceback when trying on a failed mirror (#349371).

* Mon Oct 22 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.44-1
- Fix warning about arch changes on upgrade (#222424)
- Fix phantom kernels on upgrade (#325871)
- Add some kde packages to the multilib upgrade blacklist (#339981)
- Require policycoreutils (clumens, #343861)
- Fix typo leading to traceback (clumens)
- Fix processing of ks=nfs (clumens)
- Memory freeing cleanups (pjones)

* Sun Oct 21 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.43-1
- Fix closing of some fds (pjones)
- Fix ip address used in a few cases (clumens, #336761)
- Filter out non-useful networking devices from being 
  displayed (clumens, #338461)
- Fix a quoting bug with pxelinux (#248170)
- Label lost+found (pjones, #335621)
- Update udev rules to not match wmaster (notting)
- gptsync update (pjones)
- Detect invalid harddrives given to bootloader --driveorder (#33861)

* Wed Oct 17 2007 Peter Jones <pjones@redhat.com> 11.3.0.42-1
- Don't include 'sound-and-video' in 'Office and Productivity' since the
  former is enabled by default, and including it here causes disabling OaP
  to result in disabling s-a-v unintentionally.

* Wed Oct 17 2007 Peter Jones <pjones@redhat.com> 11.3.0.41-1
- Fix liveinst build on ppc

* Wed Oct 17 2007 Peter Jones <pjones@redhat.com> 11.3.0.40-1
- Don't build gptsync on ppc (katzj)
- Remove obsolete no.po translation (clumens, #332141)
- Update gptsync to 0.10

* Fri Oct 12 2007 Chris Lumens <clumens@redhat.com> 11.3.0.39-1
- Detect PS3 disks (katzj, #325111).
- Fix lang setting for Romanian (#327431).
- Fix segfault in constructing HTTP headers in the loader (#328191).
- Remove ata_generic from the blacklist (katzj).
- Add dbus to upgrade remove blacklist (katzj).
- Extract firmware in mk-images (katzj).
- Write udev network device name rules (notting, #264901).
- Speed up upd-instroot quite a bit (Orion Poplawski).
- Fix formatting of /etc/hosts (katzj).
- Don't add labels to /etc/fstab for reused LVs (#216561).
- Allow liveinst on ppc (katzj).

* Wed Oct 10 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.38-1
- Copy over modprobe.conf from live system 
- Don't traceback with unconfigured nics (#325071)
- Disable selinux on upgrades if the user has booted with selinux=0 (#242510)
- More speedups building stage2 images (Orion Poplawski)
- Fix some translations (#322681)

* Mon Oct  8 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.37-1
- Use nodocs when building stage2 images (Orion Poplawski)
- Add extra headers to ks.cfg request for arch and release (#315601)
- Fix a traceback in partition sanity checking (#316551, #318841, #300721) 
- Hack to not ignore the ssb driver for wireless (#311421)
- Set repo cost so we pull things from the DVD instead of network (#245696)
- Make boot partitions 200 megs
- Write reboot commands into generated anaconda-ks.cfg (clumens)
- Don't reload the UI if we don't have to (clumens, #290781)
- Use newer version of device command (clumens)

* Fri Sep 28 2007 Chris Lumens <clumens@redhat.com> 11.3.0.36-1
- Fix rescue CD + nfs tree as well.
- More wireless driver blacklist fixing (katzj).

* Thu Sep 27 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.35-1
- Support modname.option=value for passing options to kernel modules
- Fix rescue CD + nfsiso (clumens)
- Blacklist more wireless drivers that can't work
- Make buildarch more predictable (#239897)

* Tue Sep 25 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.34-1
- A few upgrade fixes; look for packages in 
  /var/cache/yum/anaconda-upgrade/packages so that you can predownload them
- Point to the mirror list for the "Additional Fedora Software"
- Font movement (#304271)
- Fix where firmware is looked for

* Mon Sep 24 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.33-1
- Blacklist some modules to try to avoid #299351
- Copy over media.repo if it exists
- Fix for pulling firmware
- Remove a useless progress window (#240459)
- Fix Romanian traceback (#292091)
- Catch an exception on repo setup (#295381)
- Fix network device tool tips
- Fix display of groups being installed vs no (#296581)
- Fix Serbian language/keyboard (msivak, #235709)
- Honor "boot from" dropdown more (msivak, #243556, #243799)
- Make sure people are adequately warned about booting from a drive 
  they're not installing to (msivak, #243799)
- Don't label lvm on live installs either (#297391)

* Wed Sep 19 2007 Jeremy Katz <katzj@redhat.com> 11.3.0.32-1
- spec file cleanups (dcantrell)
- lots of pychecker fixes (clumens)
- revert writing out anaconda-ks.cfg earlier; breaks live installs (clumens)
- Fix upgrade traceback (clumens, #296571)
- Few live install fixes

* Tue Sep 18 2007 Chris Lumens <clumens@redhat.com> 11.3.0.31-1
- Really include new Japanese font (katzj, #279931).
- Use /dev/live-osimg-min if it exists (katzj).
- Copy driver disk contents to /root (#289751).
- Write out /root/anaconda-ks.cfg earlier (#292571).

* Mon Sep 17 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.30-1
- Firewire module names changed again (#292421)
- Some liveinst improvements (Douglas McClendon)
- Create tape devices (dlehman)
- Fix traceback on no more mirrors (dlehman)
- Fix treeinfo path to stage2 (wwoods)
- Remove unused graphics (notting)
- Look at root path for kernels (Douglas McClendon)
- Netlink fixes (pjones)

* Thu Sep 13 2007 Chris Lumens <clumens@redhat.com> 11.3.0.29-1
- On the graphical netconfig screen, only check the gateway address if
  provided (dcantrell).
- Don't show wireless adapters unless explicitly requested (katzj).
- Add user and services commands and scripts to anaconda-ks.cfg
- Fix handling of groups from the kickstart user command.
- Support loading updates from partitioned devices.
- Rework netlink code to support > 10 devices and not get caught in
  an infinite loop (pjones, dcantrell).
- Fix args passed to iscsiadm (k.georgiou AT imperial DOT ac DOT uk,
  #283791).
- Set flags.selinux (katzj, #244691).
- Be more accepting when waiting for an sshd response
  (alanm AT redhat DOT com, #286031).
- Probe USB to make USB network installs work (H.J. Lu, #285491).
- Rework driver package installation to be more generic.
- Turn off swaps we didn't turn on so livecds don't blow up (katzj).
- Add new Chinese and Japanese font packages (katzj, #279931).
- Fix another upgrade GUI traceback (#281031).
- Correctly identify when the VNC server doesn't start.
- Display the correct signal name when loader exits (pjones).
- Change method for determining maximum LV size (msivak, #242508).

* Wed Sep  5 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.28-1
- Make sure we find out about all nics (dcantrell)
- Hard drive install fixing (clumens, #287241)
- Make sure iniparse is in the image (notting, #276941)
- Add the short hostname to the localhost entry (dcantrell, #253979)

* Tue Sep 04 2007 Chris Lumens <clumens@redhat.com> 11.3.0.27-1
- Honor hostname= command line option (dcantrell, #186560).
- Set the hostname if provided by the user or by DHCP (dcantrell, #180451).
- Blacklist floppy and iscsi modules (notting).
- Fix traceback on GUI network config screen (dcantrell).
- Kickstart networking interface fixes (dcantrell, #260621).
- Don't traceback when reading kickstart post scripts (#276851).
- On kickstart installs, output the incoming packages section to
  anaconda-ks.cfg.

* Fri Aug 31 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.26-1
- Some kickstart fixes (clumens, #269721)
- More libraries (clumens)

* Thu Aug 30 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.25-1
- quick and dirty fix for popt to be in stage2

* Thu Aug 30 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.24-1
- Use the right network kickstart object (clumens)
- More firmware fixes (dcantrell, #177452)
- Skip devices without firmware (dcantrell, #251941)
- Attempt to fix out dso depsolving for stage2

* Tue Aug 28 2007 Chris Lumens <clumens@redhat.com> 11.3.0.23-1
- Fix symlink handling in stage2 creation (katzj).
- Make man pages work when chrooted in rescue mode (jgranado, #254014).
- Handle wireless drivers that require firmware (dcantrell).

* Mon Aug 27 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.22-1
- Add an isomd5sum subpackage
- Make sure we pull in all X drivers
- Fix kickstart traceback (clumens)
- Fix zfcp radio button to not be selectable (clumens, #254137)

* Sat Aug 25 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.21-3
- BR popt-devel
- and -static

* Sat Aug 25 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.21-1
- Fix setting additional repo names (clumens)
- Update install-methods doc (msivak, #252407)
- Add an FS label column (msivak, #248436)
- Allow changing/reconfiguring nic in the loader (dcantrell, #242019)
- Fix man pages in rescue mode (jgranado, #243443)
- Setup everything repo (jgranado, #254014)
- Allow using the "rescue" CD as the second stage for all install 
  types (#186641)
- Fix firewire module name
- Display arch more prominently (msivak, #244531)

* Wed Aug 22 2007 Chris Lumens <clumens@redhat.com> 11.3.0.20-1
- Only add one slash to NFS path names (dcantrell, #253539).
- Use dotted quad netmasks if provided (dcantrell, #243250).
- Update system-config-date dependency (#253444).
- Fix timezone screen size for livecd installs (katzj, #251851).
- Check for themes in the installed root instead of host (katzj).
- Add version information to the syslinux screens (katzj, #253632).
- Add tooltips to UI for device names (jgranado, #125312).
- Fix number of created SCSI device nodes (msivak, #241439).
- Simplify upd-instroot (katzj).
- Fix SIGSEGV in loader network config (dcantrell, #252988).
- Network input validation cleanups (hhara AT miraclelinux DOT com).
- Handle multiple module parameters in insmod (hhara AT miraclelinux DOT com).

* Mon Aug 13 2007 Chris Lumens <clumens@redhat.com> 11.3.0.19-1
- Make the version number display more prominent.
- Dynamically figure out the GTK and icon themes (katzj).
- Purge lots of unneeded code that's in yum (katzj).
- Don't check for bootable EFI partitions on RAID (#250353).
- Remove SELinux stuff after policy creation (katzj).

* Thu Aug 09 2007 Chris Lumens <clumens@redhat.com> 11.3.0.18-1
- Fix "noipv6 ip=dhcp" to not ask about v4 vs. v6 (katzj).
- Blacklist the ata_generic module (katzj).
- Don't double add packages to the transaction set (katzj, #249908).
- Use find_lang (katzj, #251444).
- Add newt-python and libuser-python packages (katzj, clumens, #251347).
- Add dosfslabel (katzj, #251217).
- Enable runlevel 5 if kdm is installed (#251194).
- Fix disk selection in text UI (#247997, #251150).
- Don't require a command line option for xfs (katzj).
- Fix syntax error (pjones).
- Rework loader flags (dcantrell, #250895).

* Mon Aug 06 2007 Chris Lumens <clumens@redhat.com> 11.3.0.17-1
- Check the rpmdb of the installed root (katzj).
- Fix mknod calls (hhara AT miraclelinux DOT com).
- Generate module-info at build time (notting).
- Use more specific error messages when copying stage2 fails (#250954).
- Test using zenity for kickstart script progress reports (#147109).

* Fri Aug 03 2007 Chris Lumens <clumens@redhat.com> 11.3.0.16-1
- Remove debug button from exception dialog on livecd installs.
- Don't look at removed devices to find free space (#250148).
- Build fixes.
- Force formatting / on livecd installs (#250301).
- Remove plip support (notting).
- upd-instroot fixes (pjones).
- Fix kickstart updates command.
- Add more information to .treeinfo (wwoods).

* Tue Jul 31 2007 Chris Lumens <clumens@redhat.com> 11.3.0.15-1
- isys cleanups.
- Create device nodes much earlier (#249882).

* Fri Jul 27 2007 Chris Lumens <clumens@redhat.com> 11.3.0.14-1
- Fix ppc keymaps (#249881).

* Fri Jul 27 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.13-1
- fix nfsiso (#249882)

* Thu Jul 26 2007 Bill Nottingham <notting@redhat.com> - 11.3.0.12-1
- fix stage2 generation (jkeating)

* Thu Jul 26 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.11-1
- GPT boot bits (pjones)
- Fix loopback clobbering problem
- Fix tui installs to not hang (dcantrell)
- Fix stage2 generation to use the tree and not configured repos

* Wed Jul 25 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.10-1
- fix media installs (#249371)

* Tue Jul 24 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.9-1
- Rebuild keymaps (clumens, #240087)
- Fix kickstart docs about dhcpclass (clumens, #248910)
- Fix for usb-storage dance (pjones, #247830)
- Fix protected partitions problem (clumens)  
- Improve stage2 generation

* Thu Jul 19 2007 Chris Lumens <clumens@redhat.com> 11.3.0.8-1
- Mark iSCSI root with _netdev mount option (markmc AT redhat DOT com,
  #245725).
- Support multiple bind mounts when reading /etc/fstab (#246424).
- Support ISOs being on the root partition to upgrade (#244002).
- Improve error reporting when mounting swap (#248558).
- Add support for labeling FAT filesystems (pjones).
- Make x86 machines using EFI use /boot/efi and mark as bootable (pjones).
- Lots of partition initialization cleanups (pjones).
- Don't generate two errors for SCSI devices with > 15 partitions (pjones).

* Mon Jul 16 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.7-1
- Don't format rootfs for live installs (#248085)
- Handle --only-use option for drives (clumens, #198526)
- Avoid reserving labels that won't exist after partitioning is 
  complete (clumens, #209291)

* Thu Jul 12 2007 Chris Lumens <clumens@redhat.com> 11.3.0.6-1
- Don't call lvm.pvlist so much (pjones).
- Don't log harmless unmounting errors (dlehman, #223059).
- Handle F12 on the install key dialog (dlehman, #210673).
- Create device nodes and probe for tape drives (dlehman, #218816).
- Fix loader network configuration UI flow (lucasgf AT br DOT ibm DOT com,
  #247807).
- Include yum-fedorakmod plugin (dlehman).
- Don't map Fedora to Fedora Core in the betanag dialog (katzj).
- String fixes (katzj, #246703).
- Fix module path order so updates get used (pjones).
- Install the PAE kernel when applicable (pjones, #207573).
- Fix fsset entry sorting (jhutz AT cmu DOT edu, #242294).
- Don't display garbage in the ksfile location dialog (#245936).

* Thu Jun 28 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.5-1
- Fix traceback opening disks (dcantrell, #245609)
- Fix live installs with /usr/local and /usr as separate partitions (#244913)
- Driver disk reworking (clumens, #213318)
- Write out additional repos in anaconda-ks.cfg (clumens, #206152)
- Fix iscsi error reporting (pjones)
- Add nss/nspr libs to stage2 (clumens)
- Fix code to work with yum 3.2.1 (#245918)
- Preserve owners on live install copy (#243479)

* Fri Jun 22 2007 Chris Lumens <clumens@redhat.com> - 11.3.0.4-1
- Add a firmware loader, remove nash firmware bits (pjones).
- Fix module loading to work for multiple modules.cgz locations (pjones).
- Handle IPv4 CIDR prefixes in iscsi config (hhara AT miraclelinux DOT com).
- Better error handling in iscsi config (dwpang AT redflag-linux DOT com,
  hhara AT miraclelinux DOT com).
- Fix livecd traceback (#244764).
- Copy over entire driver disk directory contents for new layout.

* Mon Jun 18 2007 Chris Lumens <clumens@redhat.com> - 11.3.0.3-1
- Remove obsolete language and loader options (notting).
- Remove unused gzlib implementation (pjones).
- Finish removing split ISO loopback method (#244258).
- libbz2 has changed location (#243566).

* Fri Jun 15 2007 Jeremy Katz <katzj@redhat.com> - 11.3.0.2-1
- fix syntax error (jkeating)
- don't capture passwords from kickstart in exception dumps (clumens)
- don't write out unicode text to install.log (clumens, #243477)

* Fri Jun 15 2007 Chris Lumens  <clumens@redhat.com> - 11.3.0.1-1
- Fix call to mksquashfs in mk-images so we get stage2.img again.
- Other minor image creation fixes.
- Flush drive dict so zFCP devices get device nodes (dcantrell, #236903).

* Tue Jun 12 2007 Chris Lumens  <clumens@redhat.com> - 11.3.0.0-1
- Require libdhcp6client-static.
- Remove loopback mounted split ISO install method.
- Allow locking root and user accounts from kickstart (#240059).
- Don't delete NFS mounts from /etc/fstab on upgrade (#242073).
- Add support for Areca RAID controllers (#238014).
- Use "disc" instead of "CD" in loader dialogs (#242830).
- Don't show the X hatch pattern anymore (#195919).
- Set a default clearpart type.
- Permanently skip task and group selection on livecd (katzj, #242083).
- Sync up repo representation with yum (dlehman).
- Enable building on arm (Lennert Buytenhek).
- Fix iscsi configuration traceback (#242379).
- Enable all ZFCP LUNs (dcantrell, #207097).
- Don't traceback on blank lines in modprobe.conf (#241991).
- Fall back to English release notes (#241975).
- Fix static network configuration (dcantrell, #221660).
- Mount /dev/pts in rescue mode (dlehman, #228714).
- Include dmidecode on ia64 (dlehman, #232947).
- Correctly count SCSI disks (dlehman, #230526).
- Don't traceback if we can't remove a ks script (#241878).
- Preserve authconfig formatting (#241657).
- Fix RAID superblock issues (katzj, #151653).
- Bump early swap RAM limit (katzj, #232862).
- Network configuration fixes (katzj, #240804).
- Define Error to fix a livecd traceback (katzj, #241754).
- Remove extra windows in text network config (notting, #241556).
- Remove telnet mode (dcantrell).
- Fix traceback on kickstart upgrades (#241395, #243159).
- Make sure nics are brought up with DHCP config info (dcantrell).
- Error out on invalid RAID superblocks (pjones, #151653).
- loader UI flow fixes (dcantrell, #239958).
- Fix various tracebacks in the partitioning code (dcantrell).
- Fix network segfault (dcantrell, #240804).
- Log real LVM errors instead of hiding them (katzj).

* Mon May 21 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.61-1
- add esound to upgrade handling
- fix selected group display when adding repos with the same groups (#237708)
- check for Xvnc being executable (dcantrell)
- add keyutils-libs (#240629)

* Wed May 16 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.60-1
- Add yum logger (katzj, #240226).
- Fix up Bulgarian keyboard support (#240087).
- Fix text mode language selection tracebacks.

* Tue May 15 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.59-1
- Set the timezone when language is changed in text mode (#239826).
- Replace pump-stub with dhcpclient-stub (dcantrell, #239427).
- Set preferred color on upgrades (pnasrat, #235757).
- Fix livecd text mode traceback (katzj).
- Kickstart documentation updates (#234187).
- Increase early swap size on 64bit platforms (katzj, #238266).
- Various network fixes (dcantrell).
- Fix syslinux highlighting (katzk).

* Fri May  4 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.58-1
- Set preferred rpm color (pnasrat, #235757)
- Add mk-rescueimage.ia64 (prarit, #236221)
- Be smarter about getting pid of iscsiadm (clumens, #223257)
- Relabel all of /var/log (#236774)
- Fixes for appletouch (#238355)
- Fix homedir labeling (#238277)
- Don't traceback in text mode without disks (#238695)
- Fix vncconnect (clumens, #238827)
- Don't eject too soon in kickstart (clumens, #238711, #239002)
- Fix lvm activation/deactivation (pjones, #224635)

* Mon Apr 30 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.57-1
- fix build

* Mon Apr 30 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.56-1
- Don't write out ipv6 disabling bits (dcantrell, #237642)
- Load pata_pcmcia late (#237674)
- Fix release notes to display nicely with the livecd running at 800x600
- Add support for spufs (pnasrat, #237725)
- Add libidn for ping (#237745)
- Fix selinux context of /root (clumens, #237834) 
- Fix for mirror errors (dlehman)
- Fix splittree (Joel Andres Granados, #233384)
- Fix ppc32 netboot (pnasrat, #237988)
- Fix %packages for media installs (clumens, #231121, #235881)
- Fix rescue mode networking (dcantrell, #238080)
- Adjust for unbreaking the yum API
- Fix rescue mode traceback (#238261)
- Fix for iscsi not being present (#238424)
- Fix for upgrades with LVM (clumens, #234938)
- Give some feedback while erases are being processed (#238256)

* Mon Apr 23 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.55-1
- Fix FTP/HTTP installs booted from disc1/rescueCD
- Ensure kickstart scripts are executed with the right cwd (clumens, #237317)
- Fix net device comparison (dcantrell, #237431)
- Fix multiple repos some more (#231543)

* Fri Apr 20 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.54-1
- Be smarter about detecting network link status (dcantrell, #236483).
- Lots of yum mirror list and retry fixes (dlehman).
- BR libdhcp-static (dcantrell).
- Add Mist theme (katzj).
- Update translation files (katzj, #237263).
- Fix VNC traceback (#237194).
- Fix error message for > 15 partitions per disk (dcantrell, #234686).

* Thu Apr 19 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.53-1
- Add Romanian to language list (#237060)
- Fix selinux context of /etc/modprobe.d
- Move locale-archive.tmpl into the right place (clumens)
- Don't duplicate filesystem entries (clumens, #236477)
- Fix a python warning (dcantrell)
- Fix release notes with live CD

* Wed Apr 18 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.52-1
- More PS3 fixes (dwmw2, #236480, #236508)
- Fix broadcast calculation (dcantrell, #236266)
- Allow anaconda to install debuginfo (#236033)
- Fixes for installs from live image running off of USB key
- Don't nuke locale-archive (clumens, #236978)
- Fix rescue image default (clumens, #236453)
- Try to be smarter about resolution for 480i ps3 (#236510)

* Tue Apr 17 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.51-1
- Some PS3 fixes (dwmw2)
- Try to handle some of the problem cases with the ide -> libata driver 
  changes (clumens, katzj, #229704)
- Fix text mode package descriptions (clumens, #233662)
- Fix netlink buffer size (dcantrell, #234764)
- Fix how we disable ipv6 (dcantrell)
- Add a few more packages to upgrade blacklists
- Warn and try not to blow up with scsi disks with more than
  15 partitions (dcantrell, katzj)

* Fri Apr 13 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.49-1
- Fix SELinux labels on moved files with live install (#236282)
- Add vmmouse driver

* Thu Apr 12 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.48-1
- Don't write out remove lines for packages that don't exist on the
  installation arch (clumens)
- Remove unused code from partedUtils.py (clumens)
- Fix handling of plain text release notes (Elliot Peele)
- Fix RAID minor number allocation in text mode UI (clumens)
- Force /sbin and /usr/sbin in the PATH (katzj)
- Don't copy stage2.img if it is not found (katzj)
- Test given URL for HTTP/FTP install modes when stage2 is loaded from CD

* Mon Apr  9 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.47-1
- Fix build on s390
- Ensure we exit at the end of the install.

* Sun Apr  8 2007 Peter Jones <pjones@redhat.com> - 11.2.0.46-2
- Rebuild because aparently the s390 build produced a corrupt package...

* Thu Apr  5 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.46-1
- Minor live install fixes
- dasd fixes (dcantrell)

* Wed Apr  4 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.45-1
- More live changes to fix installing from the live image running from RAM 
  or a USB stick.  Note: requires a livecd created with livecd-tools >= 006
- Make the end button Close for the live case (#225168)
- Unmount installed filesystems at the end of the live install
- Fix an autopart bug (clumens, #235279)

* Tue Apr  3 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.44-1
- Clean up depsolve callback to work with yum depsolver
- More live CD fixing

* Tue Apr 03 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.43-1
- Correctly detect if there are no more mirrors to try (clumens, #232639)
- Display size and model info per disk in PartitionTypeWindow in textw
- Support fetching kickstart files from HTTP URLs that require login
  information (bnocera@redhat.com, #194247)
- Improve CongratulationWindow.getScreen (katzj)
- Add missing import to livecd.py (katzj)
- Use correct syntax for hal-lock (katzj)
- Don't traceback in cases where there are no drives (katzj, #234697)
- Add fec_mpc52xx, ps3_storage, and gelic_net (#220009)
- Display IP address of the VNC server (#234747)
- Add OSA layer 2 support for System Z (bhinson@redhat.com, #233376)
- Import constants in backend.py (clumens, #234782)
- Add netxen_nic driver (clumens, #230245)

* Fri Mar 30 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.42-1
- LiveCD fixes (katzj, #230945, #224208, #224213, #230943)
- Handle IOErrors if we can't find the kickstart file (clumens)

* Wed Mar 28 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.41-1
- Fix partitioning under kickstart when using clearpart (#232936).
- Add padding on the device stripe graph (#217294).
- Fix probing RAID superblocks (#172648, #208970, #215231).
- Support using hal locking on the live CD (katzj, #231201).
- Fix text install UI flow (dcantrell).
- Add IPv4 address validation for s390 (dcantrell, #234152).
- Don't unnecessarily run DHCP on the add repos screen (dcantrell, #232512).
- Netlink cache cleanups (dcantrell).
- Package installation progress UI cleanups (dcantrell).
- Only probe for network devices with loaded modules (dcantrell, #233507).
- Better error handling on unprintable filesystem labels (#191679).
- Live CD and lowres UI fixes (katzj).
- Exit if the close button is clicked (katzj, #231775).
- Always display an IP address in the VNC info message (#231934).
- Handle dual IP stack manual configuration correctly (dcantrell, #232690).
- zlib has moved (katzj).
- Write out /etc/sysconfig/desktop file if there's a default (katzj, #233472).

* Fri Mar 23 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.40-2
- fix xinit exiting

* Wed Mar 21 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.40-1
- livecd X fixes (katzj).
- Handle mounting errors on the harddrive image method (#124793).
- Fix timezone --isUtc for real.
- More kickstart RAID10 fixes (#230268).
- Fix ip=dhcp command line option (dcantrell, #233152).
- Add cdc_ether module for USB networking (dcantrell, #174229).
- Fix text mode timezone traceback.

* Tue Mar 20 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.39-1
- Document asknetwork (clumens, #233035)
- Fix no drives being selected by default with autopart (clumens)
- Add bits for livecd install desktop file, etc

* Mon Mar 19 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.38-1
- Add new firewire modules (katzj, #231708).
- String fixes (#232778).
- Update for new system-config-date (#232905).
- Fix package selection (#232701).
- Default to no drives selected on the RAID screen (#195636).
- Display a caps lock warning on the password screen (#207894).
- Kickstart documentation updates (#209966).

* Thu Mar 15 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.37-1
- Fix confusing wording in loader (clumens, #163329)
- Don't tell the user to eject the CD at the end (clumens, #137275)
- Remove some unused functions (clumens)
- More intelligent error handling when the number of packages exceeds
  the CD size (clumens, #232104)
- Partitioning UI string fixes (clumens, #203346)
- Name the cciss module 'HP/Compaq Smart Array Controller (#210414)
- More partitioning UI string fixes (#208394)

* Tue Mar 13 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.36-1
- String fixes (#231761).
- Fix yum logging traceback.
- Restore "Save to Remote" button on exception dialog.
- Return NULL when dhcpv4 and dhcpv6 are disabled (dcantrell, #230941).
- Handle configuration of lots of NICs much better (dcantrell, #228512).

* Fri Mar  9 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.35-1
- Fix SIGSEGV for HTTP installs (#231576)
- Some spec file cleanups to adhere to Fedora packaging guidelines

* Thu Mar  8 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.34-1
- Remove duplicate Activate On Boot checkbox in iw netconfig
- Set DHCPv6_DISABLE flag for auto neighbor discovery (#230941, #230949)
- Set loaderData->ip appropriately in STEP_IP (#231290)
- Replace hyphens in BOOTIF= parameter with colons (#209284)
- In strcount() in libisys, return 0 if tmp is NULL (#231290)
- Subclass Raid class in kickstart.py from F7_Raid (clumens)
- Make sure ext2 filesystem module is loaded early (clumens, #230946)

* Thu Mar  8 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.33-1
- Fix translations to build correctly.
- Fix traceback on upgrade due to yum API change.

* Wed Mar  7 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.32-1
- Various buildinstall and splittree fixes to make things work better 
  without an RPMS dir (Jesse Keating)
- Minor package progress API changes
- Minor backend fixes (Elliot Peele)
- Minor translation related fixes

* Tue Mar  6 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.31-1
- Smaller required height for main window for livecd installs (katzj)
- Move utility functions around in isys
- Init loopback in stage 1 using ioctl() rather than netlink (#229670)
- Handle netlink messages for RTM_GETLINK that are larger than 4K (#230525)

* Mon Mar  5 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.30-1
- ext2 is a module now
- add a basic boot drive selector to the graphical autopartitioning screen

* Mon Mar  5 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.29-1
- Fix some typos (clumens, dcantrell, katzj)
- Use depsolving from yum instead of our own stuff now that the yum 
  depsolving doesn't require header downloads
- Misc backend cleanups
- Fix deprecation warnings (#230951)
- Networking fixing (#210370)
- BR newt-static

* Thu Mar 01 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.28-1
- Support multiple %ksappend lines (#222201).
- Set the ksdata after setting the initial timezone values (#230472).
- New progress screen interface that's easier on backends (katzj).
- Handle KickstartError exns better than just dumping a backtrace.
- Add an updates ks command.
- Apply a patch to support RAID10 (Orion Poplawski <orion AT cora.nwra.com>,
  #230268).
- Fix reserve-size option on splittree.py (katzj, #230343).
- Apply a patch to clean up strings (Paul W. Frields <stickster AT gmail.com>,
  #204564).
- Focus the next button when enter is pressed on the password screen (#206568).

* Mon Feb 26 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.27-1
- Clean up partitioning text (katzj, #228198, #221791).
- Write out the fstab after migrating (katzj, #223215).
- More partitioning text fixes (#229959).
- Desensitize drive selection box for custom layouts (#219207).
- Support new kickstart extended group syntax.
- Handle port numbers in the exception scp dialog (#227909).
- Don't attempt to load a module when the device line is wrong (#227510).
- Fix selecting the kernel-xen-devel package (dlehman, #226784).
- Desensitize partition review checkbox when going back (dlehman, #220951).
- Add key handling UI (dlehman).
- Fix writing out /etc/sysconfig/network-scripts/ files (#227250).
- Verify added repos when going back to the tasksel screen (#227762).
- Don't include /usr/share/zonetab/zone.tab for translation (#229729).
- Documentation updates (#189292, #173641).
- Delete /etc/mtab if it exists on upgrade (#213818).
- Add atl1.ko module to loader (#229641).
- Don't traceback when cancel is pressed on iscsi add dialog (#229694).
- Don't relabel disks that contain protected partitions (dlehman, #220331).
- Clear non-protected partitions from disks if initAll is set (dlehman).
- Allow access to regkey screen when going back (dlehman, #219361).

* Wed Feb 21 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.26-1
- Add dpi flag when starting X to fix tiny font size (#224665).
- Set the default timezone for languages we can't display (#227625).
- Add termcap files we were missing to fix b&w console (#228596, #229236).
- Add files from vnc-libs package to fix VNC installs.

* Tue Feb 20 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.25-1
- Add libtinfo to the stage2 images.
- Use new pykickstart organization.
- Change default French layout to latin9 (#229269).
- Add maketreeinfo.py script (Will Woods <wwoods AT redhat.com>).

* Fri Feb 16 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.24-1
- Fix compiler warnings in wlite code
- Remove obsolete code from network_gui.py
- Rebuild to link with new libdhcp6client and new libdhcp

* Wed Feb 14 2007 Peter Jones <pjones@redhat.com> - 11.2.0.23-1
- Get rid of unused X mouse handling (dcantrell)
- Update for newer createrepo (jkeating)
- Update for device-mapper/device-mapper-libs split

* Tue Feb 13 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.22-1
- Load the ext3 module earlier to fix hd installs (#223749, #224534).
- Don't traceback in postconfig if it's not a kickstart install.
- Fix autopart string (dcantrell, #228192).
- Remove references to genheader (dcantrell).
- Rework text network UI to more closely follow graphical (dcantrell).

* Fri Feb 09 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.21-1
- BR device-mapper-devel

* Fri Feb 09 2007 David Cantrell <dcantrell@redhat.com> - 11.2.0.20-1
- Require newest libdhcp
- Remove obsolete findpackageset.py and genheader.py (clumens)
- Update translation files (#227775, clumens)
- BR glib2-static (clumens)
- Add LVM exception handling classes (pjones)
- Wrap lvm command calls with lvmExec() and lvmCapture() (pjones)
- Remove obsolete fbconProbe() and doFbconProbe() (katzj)
- Display 'DHCPv6' rather than 'DHCP' for IPv6/Prefix column 
- Make 'description' a property for correct i18n translations (pjones)
- Add the postscripts step (#227470, clumens)
- Do not try to run post scripts if ksdata is missing (clumens)
- Allow going back to interface selection screen in stage1 (#213787, clumens)
- Sort detailed package listing in text mode (clumens)
- Don't try to second guess provided X resolutions or depths (clumens)
- Preserve X resolution given in kickstart file (#158089, clumens)
- Improve listing selected and deselected packages (#189873, clumens)
- Fix argument passing for windows on kickstart installs (clumens)
- Don't set up default partitions during kickstart installs (clumens)

* Tue Jan 30 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.19-1
- pkgorder cleanup for various tree layouts (jkeating)
- Use $TMPDIR in scripts (Steve Pritchard, #224438)
- Wrap timezone label when it's long (clumens, #225444)
- Map Fedora -> Fedora Core (notting)
- Give a useful error when there's no comps information
- Fix localboot from boot disks (pjones)
- Kickstart fixes (clumens)

* Fri Jan 26 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.18-1
- Fix pkgorder 
- Give indication of city being pointed at for timezone (clumens, #219417)

* Wed Jan 24 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.17-1
- Disable extra repo for now

* Wed Jan 24 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.16-1
- Fix rescue mode
- Fix theming 

* Tue Jan 23 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.15-1
- Remove @everything parsing as promised
- Package requirement fixes
- Fix kickstart traceback (clumens, #223903)
- Add more icons
- Don't be too aggressive remaking device nodes
- Fix rescue mode 

* Mon Jan 22 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.14-1
- Fix shell on tty2 with libncurses in /lib
- Use echo icon theme
- Add anaconda- to VCI (dcantrell, #220082)
- Remove some no-longer-needed imports (clumens)
- Require system-config-keyboard

* Fri Jan 19 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.13-1
- Kickstart and upgrade are no longer installclasses.
- Update x86_64 syslinux config (katzj).
- Support %packages --default (#221305).
- Fix early kickstart UI traceback.
- Remove cruft in x86 images (katzj).
- Fix error handling in loader netconfig screen (dcantrell).
- Add libthai to graphical install (katzj).

* Thu Jan 18 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.12-1
- Fix so that package selection in the yum backend is actually enabled
- UI tweaks so that we work better with a real window manager
- Ensure that file contexts are reset to the right thing after a live CD copy
- Fix another ks.cfg traceback
- Make it easier to do a 32bit build on a 64bit host

* Thu Jan 18 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.11-1
- Add backend for installing from a live CD
- Make backend controllable from the installclass
- Bring up loopback device in ks (clumens, #191424)
- Fix traceback with writing ks.cfg (clumens)
- Add support for new vesamenu bits in syslinux
- Allow for updates.img to be a cpioball (dlehman)
- Fix use of halt in ks.cfg (pjones, #222953)
- Fix traceback in text mode network config (Elliot Peele)

* Tue Jan 16 2007 Chris Lumens <clumens@redhat.com> - 11.2.0.10-1
- Remove deps when going back from package selection (dlehman, #222894).
- Fix UI when going back from package selection (dlehman, #215493).
- Update kickstart code to use new pykickstart API.
- Fix loader test for NULL (yanmin.zhang AT intel.com, #222767).
- Don't display the unsupported lang box in kickstart installs (#222096).
- Error message fixes in package installation (katzj).
- Update DHCP UI (dcantrell).
- Correct behavior of escape key in release notes viewer (dcantrell, #220418).

* Wed Jan 10 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.9-1
- Set NETWORKING_IPV6 based on whether we want ipv6 for 
  any devices or not (dcantrell, katzj, #222147)
- Little fixes so installs work.

* Tue Jan  9 2007 Jeremy Katz <katzj@redhat.com> - 11.2.0.8-1
- Add pata* drivers
- Fix segfault with ks= (clumens, #221904)
- Fix starting sector for sparc (pjones)
- Only ask about vnc if Xvnc is present (dcantrell)
- Put a debug button on custom dialogs with flags.debug (pjones)
- python2.5 fixes
- Fix ftp/http being specified as the url (dcantrell, #220728)
- Use a default dhcpclass (dcantrell, #220082)
- Add --gaugefor checkisomd5 (Ryan Finnie, #220286)
- Don't overly clear the root window text (clumens, #220905)
- Handle crazy large disk sizes (clumens, #219414)
- Try to fix USB  sleeping bits
- Translation fix (#221253)
- Honor dhcpclass (#220057)

* Sun Dec 17 2006 Jeremy Katz <katzj@redhat.com> - 11.2.0.7-1
- Clean up execConsole to work better (clumens, #210481, #16155)
- Fixes due to earlier changes (dcantrell, #219789)
- Build fix for new kernel headers

* Thu Dec 14 2006 Jeremy Katz <katzj@redhat.com> - 11.2.0.6-1
- fix build for no more md START_ARRAY; note that this leaves swraid broken

* Thu Dec 14 2006 Jeremy Katz <katzj@redhat.com> - 11.2.0.5-1
- Fix adding zfcp devices (dcantrell, #210635)
- Fix rescue mode (clumens)
- Do dasdfmt based on initlabel (dcantrell, #218861)
- Adjust for official xvc0 major/minor
- Abstract required media for different backends (Elliot Peele)
- Fix overflow of source CDs (Dawei Pang)
- EDD should work on x86_64 (#218123)
- Better ipv6 config for second stage (dcantrell, #213110, #213112)
- Fix iscsi typo, don't traceback when iscsi isn't present (#218513)
- Unmount CD after install when using local stage2 with http install (clumens)
- Don't set LIBUSER_CONF in %%post scripts (#218213)
- Some python 2.5 updates

* Tue Dec 05 2006 David Cantrell <dcantrell@redhat.com> - 11.2.0.4
- Describe nokill option (clumens, #218412)
- Make sure / is mounted before /boot (clumens, #217292)
- Scan for labels on logical volumes during upgrades (clumens, #217191)
- URL install method traceback fixes (clumens)
- Copy volume group format attribute to new request (clumens, #217585)
- Default new volume group requests to formatted (clumens)
- Bump parted version requirement

* Thu Nov 30 2006 Chris Lumens <clumens@redhat.com> - 11.2.0.3
- Don't look for rhpxl's list of drivers anymore (#217890).
- Init wreq structure before use (dcantrel, #215367).
- Only compute broadcast and netaddr if IPv4 is enabled (dcantrel, #215451).
- Fetch a new release notes file on language change (#217501).
- Add support for Iloko language (katzj, #215644).
- Fix Sinhala timezone (katzj, #217288).

* Mon Nov 27 2006 Chris Lumens <clumens@redhat.com> - 11.2.0.2
- Set the home directory correctly for ks user command (#216681).
- Pull in xinf files from X driver packages on url images.

* Tue Nov 21 2006 Chris Lumens <clumens@redhat.com> - 11.2.0.1
- Use .discinfo files to determine if a CD tree exists instead of a set
  limit (pjones, #214787).
- Allow fixing/retrying when unable to grab a ksfile (#216446).
- Fix typos (pnasrat, #216410, #215232).
- Set the RAID minor number in text installs (#215231).
- Be smarter about detecting if iscsi is available (katzj, #216128).
- Kernel naming fix (katzj, #215746).
- Activate/login/logout of all iscsi devices (pjones).
- Depsolve on optional/non-grouped packages (pnasrat, #214848).
- Update kickstart documentation.
- Don't always write out xconfig and monitor in anaconda-ks.cfg (#211977).
- Follow drive order specified in kickstart file (#214881).
- Unmount source on image installs before %post is run (#214677).
- Check return value of getBiosDisk (pjones, #214653).
- splittree shouldn't fail with non-rpms in the directory (jkeating).
- Order bind mounts correctly on upgrades (#212270).
- Always skip networking on kickstart installs (#214584).
- Handle ipv6= command line option (dcantrell).
- Split up ipv4 and ipv6 options, add radvd support (dcantrell, #213108,
  #213112).
- Log exceptions when activating raid (pjones).
- Update install method documentation (#214159).
- Netconfig UI fixes (katzj, #213356).
- Avoid traceback on unused PReP partitions (#211098).
- Fix no free space traceback (ddearauj AT us.ibm.com, #213616(.
- Fix implantisomd5 output formatting (#214046).
- Remove virt group hacks (katzj).
- Default to text install if a KVM lies to us about the monitor.
- Split media FTP/HTTP loopback mount install fixes (pnasrat, #212014).

* Thu Nov  2 2006 Chris Lumens <clumens@redhat.com> - 11.2
- Add name resolution support for IPv6 AAAA and ip6.arpa records (dcantrell).
- Center anaconda window (#213350).
- Make sure to set a default on the physical extent combo (#212317).
- Fix updates on USB keys under kickstart installs.
- Set language support on text installs (pnasrat, #212511).
- Fix downloading kickstart files from nonstandard port numbers (#212622).
- Add more fonts (katzj, #207428).
- Fix localhost6 line (dcantrell, #211800, #210050).
- Disable keepalive so we don't run out of file handles (#212571).
- Display an error if we try to clear nonexistent hard drives (#212377).
- Fix lang-table typo (#212304).
- Fix file descriptor leak (katzj, #212191).
- Fix ZFCP config, kickstart handling, and module probing (katzj, #210094).
- Fix widget names on netconfig dialog (notting).
- Always bring up the network if specified in kickstart (#191424).
- Add Sinhala and Telugu (katzj, #207426, #207428).
- Fix iutil traceback (pnasrat, #211830).
- Continue if vname or vparm are NULL (dcantrell, #211502).
- Add fonts-telugu (katzj, #207428).
- Fix package installation progress bar size (katzj, #210531, #211526).
- Fix installation with CTC networking (katzj, #210195).
- Force swap formatting on ppc upgrades (pnasrat, #206523).
- Forget partitioning changes when going back in the UI (#211255).
- Don't specify a stdout or stderr for s390 shells (#210481).
- Fix window dragging jerkiness (krh).
- Add --noipv4 and --noipv6 (dcantrell, #208334).
- Correct --onbiosdisk handling (#210705).
- Set runlevel 3 by default on VNC installs (#211318).
- Fix download failures/retries (pnasrat, katzj, #211117).
- Don't use unicode line drawing characters on vt100-nav (katzj, #208374).
- Fix /tmp/netinfo parsing (dcantrell, #207991).
- Use virtualization instead of xen for the group name (katzj).
- Write out iscsi config to kickststart (katzj).
- Add qla2400 and qla2xxx to late sort module list (katzj, #210886).
- Use a better regex for finding ISO loopback mount points (#205133).
- Set up baseUrl correctly when given a list of URLs (#210877).
- Network config screen fixes (dcantrell).
- Tweak min/max swap numbers for low memory (#189490).
- Only run auditDaemon if not in test or rootpath mode (pjones).
- Fixes for supporting medium-less devices (Rez Kabir AT dell.com, #207331).
- yum API fixes (pnasrat).
- System language doesn't have to be in lang-table (#176538).
- Fix UI traceback (#210190).

* Mon Oct  9 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.110-1
- Fix SELinux contexts for iscsi 
- Fix traceback if addrepos isn't shown (#209997)
- Fix traceback looking up hostnames (clumens, #209672)
- Fix split media (pnasrat)
- Fix network to be enabled after install on non-network installs

* Fri Oct  6 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.109-1
- Fix iscsi for toolchain changes and targets with multiple IPs
- Validate ips like 9.1.2.3 (dcantrel, #209654)

* Fri Oct  6 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.108-1
- Fix endless spinning with redhat-lsb depcheck (#209665)
- Fix usefbx (clumens)
- Fix traceback with loopback isos (pnasrat)

* Thu Oct  5 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.107-1
- minor yum api fix

* Wed Oct  4 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.105-1
- Fix details in tui pkgselection (#209310)
- Add Assamese (#207424)
- More network UI sanity checking (dcantrel)
- Disable release notes url clicking (dcantrel)
- Fix traceback going back on upgrade (#205198)
- Try to fix up sr_CS.UTF-8@Latn some more (#182591)

* Tue Oct 03 2006 Chris Lumens <clumens@redhat.com> - 11.1.0.104-1
- More netconfig fixes (dcantrel).
- Reset protected partitions list (#204405).
- Handle more iscsi error cases (katzj, #208671).
- Don't bring down network interfaces after fetching files (dcantrel,
  #201194).

* Mon Oct  2 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.103-1
- More netconfig fixing (dcantrel)
- Fix some translation problems (#206620)
- Don't do netconfig on task toggle (#208562)
- Some mpath/dmraid fixes (pjones, #208423)
- Only set graphical if VNC is enabled in kickstart, not 
  all kickstarts (clumens)
- Ensure RAID levels get sorted (#208478)
- Fix handling of locales we can't display (#208841)
- Fix traceback in partition editing (clumens, #208677)
- Try to fix sr_CS.UTF-8@Latn (#182591)
- Ensure a depcheck on redhat-lsb (#201222)
- Fix pkgorder to order "needed" groups early (#206778)

* Thu Sep 28 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.102-1
- Disable repo writing for now
- Fixup text network config (dcantrel)
- More HTTP response codes (clumens)
- Don't try to use updates disk image by default (clumens)
- Give an error message when netconfig fails
- Don't prompt for non-existent cd
- Fix DNS with dhcp for extras on CD install

* Wed Sep 27 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.101-1
- Give indication of no optional packages (#204242)
- Don't give an error on partition mount errors looking for upgrades (#201805)
- Firewire fix (notting)
- Make initrd.size have 0644 perms (dcantrel, #197773)
- More netconfig tweaks (dcantrel)
- Support loopback URL mounts (pnasrat, #207904)
- Turn off firstboot on s390 (clumens, #207926)
- Set display mode if vnc ks (clumens, #204736)
- Fix partitioning traceback (#208101)
- Fix lowres (clumens)
- xfs tweak (esandeen, #208323)
- Add qla4xxx (#208324) and qla3xxx 

* Thu Sep 21 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.100-1
- Fix a few tracebacks (#207594, #207587)
- Allow only iSCSI disks (#207471)
- Fix bootdisk.img on x86_64

* Wed Sep 20 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.99-1
- Fix CD stage2 + URL installs (clumens, #205571, #206072)
- Remove hostap (clumens, #196334)
- Fix input validation for manual network config (dcantrel, 
  #206148, #206678, #206537)
- More network UI improvements (dcantrel)
- Fix upgrade tracebacks (pnasrat, #206913)
- Improved zfcp code (#204145)
- Format swap on ppc upgrades (pnasrat, #206523)
- Fix network interface bringup (dcantrel, #206192, #200109)
- Allow running anaconda with --target arch for stateless (#206881)
- Improve iscsi and zfcp TUI and kickstart config

* Fri Sep 15 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.98-1
- Fix stage2 creation (prarit, #206638)
- Add ehea driver (pjones)
- Fix rescue mode for the early shell case

* Thu Sep 14 2006 Chris Lumens <clumens@redhat.com> 11.1.0.97-1
- Compile fix (pjones).

* Thu Sep 14 2006 Chris Lumens <clumens@redhat.com> 11.1.0.96-1
- Use -no-fragments to mksquashfs (katzj, #206472).
- Fix scsi and usb module loading (pjones).
- Better testing for driver disk correctness (katzj, #195899).
- Support HTTP redirects in the loader (#188198, #204488).
- Write out repo configuration (pnasrat, #199468).
- Fix installing from additional repos on CD/DVD installs (katzj, #205846).
- Network UI fixes (katzj).
- --vesa -> --xdriver (pjones).
- Fix when group selection should appear in kickstart installs.
- Fix logical volume size checking again (#206039).
- Skip attached devices without media present again (#205465).
- Install fs packages if they're needed for installation (katzj, #205865).
- Only collect network addresses for running interfaces (dcantrel).
- zSeries initrd fixes (dcantrel, #197773).

* Fri Sep  8 2006 Peter Jones <pjones@redhat.com> - 11.1.0.95-1
- Look for repodata where the CDs are mounted, not where they're
  stored (clumens)
- Reverse traceback print order in the UI so most recent call is listed
  first (clumens, #204817)
- Don't install device-mapper-multipath or kpartx except when selected or
  required by install media.

* Thu Sep 07 2006 Chris Lumens <clumens@redhat.com> 11.1.0.94-1
- Allow opening release notes more than once (dcantrel, #203147).
- Fix NFS iso installs.
- More files to restorecon.
- Rework GUI network configuration screen (dcantrel).
- isys network cleanups (dcantrel).
- Fix taking sreenshots (#204480).
- Skip broken repositories in kickstart (#204831).
- Pull in all policy modules in initrd making.
- Fix yum traceback (katzj, #205450).
- Add hptiop module (katzj, #205337).

* Wed Sep  6 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.93-1
- unbreak xen installs
- add hptiop drivers (#205337)
- Fix a traceback (#205450)

* Tue Sep  5 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.92-1
- fix the build some more

* Tue Sep  5 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.91-1
- build fix (pjones)
- traceback fix (dcantrel)

* Tue Sep  5 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.90-1
- Update for newer iscsi code
- Fix with yum API change
- More files to restorecon (clumens)
- Don't crash with duplicate repos (clumens)
- Back to clearlooks (notting)
- dmraid for dmraid, not kpartx (pjones)

* Thu Aug 31 2006 Peter Jones <pjones@redhat.com> - 11.1.0.89-1
- Fix going back to the repo screen (clumens)
- Install correct supplementary packages when using dmraid or multipath

* Wed Aug 30 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.88-1
- Fix a case where images don't exist (#204648)
- More making pkgorder quieter

* Wed Aug 30 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.87-1
- Fix traceback on editing lvm (#204631)
- Fix SELinux context setting
- Don't do file logging in pkgorder

* Tue Aug 29 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.86-1
- Fix ia64 pxeboot dir (#199274)
- Remember manual TCP/IP settings (dcantrel, #202662)
- Clean up extra repo stuff some more (clumens)

* Tue Aug 29 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.85-1
- Sanity check more device names for LVM (notting, #2040387)
- Exception handling fixes (clumens)
- Fix Extras selection (clumens, #204267)
- Setup repos later
- Improved verbage (Paul Frields, #204249)
- Filter out some non-addressable storage from hd dict (pjones)
- Handle xen virtual serial
- Reset file contexts on mountpoints (#202525)
- Ensure programs used by anaconda are installed (clumens, #203216)

* Wed Aug 23 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.84-1
- Run in English for CJKI text installs (clumens, #180417, #202738)
- Don't mistake hard drives for CD drives (clumens, #202714)
- Start to add s390x mpath support (pjones)
- Whiteout scim-libs (clumens, #202543)
- Fix LV size check with growing (clumens, #203095)
- Fix graphical selection of drives (pjones)
- Speed up mke2fs (pjones, #201645)
- Add a simple audit daemon to get rid of audit spam (pjones)
- Some tweaks to repo addition/task selection
- Fix multipath for x86_64 (pjones, #203425)
- Set language to English every time it's unsupported (clumens, #203331)

* Wed Aug 16 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.83-1
- Fix text timezone typo (clumens, #202844)
- Some installclass tweaking
- Fix nfsiso to handle changing repopaths
- Fix x86_64 install traceback (#202660)
- Adjust for new theme

* Tue Aug 15 2006 Chris Lumens <clumens@redhat.com> 11.1.0.82-1
- Make Turkish translation build again.

* Tue Aug 15 2006 Chris Lumens <clumens@redhat.com> 11.1.0.81-1
- Fix serial console shell IO (#201479).
- Don't traceback if URL install path is just "/" (#202368).
- Fix font typo (katzj, #202167).
- SELinux fixups (pjones).
- Handle virtpconsole option again (katzj, #201749, #202450).
- Kickstart install fixes (#202471, #202483).
- Mark strings for translation (#199022).
- Fix ISO install method traceback (#201775).
- Don't enable the back button if there's no screen to show (#197766).
- Don't clobber a working /etc/resolv.conf on VNC installs (#201874).
- Remember user choices on network config (dcantrel, #200986, #200797).
- More greek fixing (katzj, #196980).
- Sync pkgorder with what distill is expecting (katzj, #201923).
- RHEL upgrade tweaks (katzj, #201741).
- Install class detection (katzj, #201745).
- Fix text upgrade traceback (katzj, #201960).
- Add more libraries for s390 (katzj, #200985).
- Add SATA probing (pjones).
- Add registration key options (katzj, #201738).
- Don't automatically set UTC check box on kickstart installs (#181737).
- Patch from Paul Schroder <pschroeder@uplogix.com> for nogr mode.

* Tue Aug 08 2006 Paul Nasrat <pnasrat@redhat.com> 11.1.0.80-1
- Blacklist e2fsprogs.ppc64 on upgrades (#200233)
- Set self.currentMedia to [] (dcantrel, #201722).
- Remove multiple error messages (dcantrel, #201247)
- Revert logMessage calls (clumens, #201707)

* Mon Aug 07 2006 Chris Lumens <clumens@redhat.com> 11.1.0.79-1
- s390 build fix.

* Mon Aug 07 2006 Chris Lumens <clumens@redhat.com> 11.1.0.78-1
- Fix password writing for interactive kickstart installs (#201455).
- Don't check percentage on preexisting LVs (#193341).
- Log added repos (#201212).
- Start adding things for ia64 Xen (katzj).
- Use new raid module name (katzj, #201361).
- Look for ifconfig in the right place during rescue mode (#201372).
- Fix segfault in FTP and HTTP path typos (#197403, #201243, #201367).
- Don't display the askmethod screen on CD installs (#201108).
- Do a better job at updating mkfs percentage bar (pjones).
- Fix finding the release notes (#201232).
- Add libvolume_id for gfs2-utils (katzj).

* Wed Aug 02 2006 Paul Nasrat <pnasrat@redhat.com> 11.1.0.77-1
- Fix pkgorder isdir check
- Reinstate frequent rescanning of devices (clumens)

* Wed Aug 02 2006 Chris Lumens <clumens@redhat.com> 11.1.0.76-1
- Don't raise an exception when someone tries to delete empty space (pjones).
- Fix X ks writing traceback (#201047).
- Add file to describe initrd to fir LPAR installs (katzj, #197773).
- Add libXau for s390 (katzj, #200985).
- Sleep for disks to settle (katzj, #200589).

* Tue Aug  1 2006 Peter Jones <pjones@redhat.com> - 11.1.0.75-1
- Fix iSCSI and MultiPath coexistance
- Don't use mygethostbyname on ipv6 yet (dcantrell)
- Better logging on nfsinstall and kickstart (dcantrell, #195203)
- Remove ddc probing (clumens)

* Mon Jul 31 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.74-1
- Fix method=http vs method=ftp (pjones)
- Various xconfig fixes (clumens, #200755 #200758)
- Fix FTP/HTTP installs by hostname (dcantrel, #200771)
- Fix command-stubs/mknod (#200820)

* Fri Jul 28 2006 Peter Jones <pjones@redhat.com> - 11.1.0.73-1
- Revert DNS changes from yesterday (dcantrel)
- Do the backtrace initialization after analyzing args (katzj)
- Use rhpxl for all X startup tasks (clumens, #199437)
- Create users under the rootpath (patch from Clark Williams)
- Update to use newer dmraid libraries
- Remove /nss usage (dcantrell)

* Thu Jul 27 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.72-1
- Don't allow ipv6-only nfs installs (dcantrel)
- Fix segfault with ksdevice= (pjones, #200451)
- Fix ipv6 ftp installs (dcantrel)
- Ignore options we don't understand to our modprobe to help fix X 
  startup on radeon
- Use rootpath in a few places we had /mnt/sysimage hardcoded
- Fix method=
- Fix translation mismatch

* Thu Jul 27 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.68-1
- And another fix for the RHEL installclass

* Thu Jul 27 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.67-1
- FTP/HTTP ipv6 fixes (dcantrel)
- Better prepboot handling (pnasrat)
- RHEL installclass fixes

* Wed Jul 26 2006 Peter Jones <pjones@redhat.com> - 11.1.0.66-1
- Fix md raid request class
- Check for busybox utilties in /usr/sbin (katzj)
- Be smarter about log files during kickstart (clumens)
- Make multipath and dmraid work
- Add Kannada language (katzj)
- Don't show onboot for rescue mode (katzj)
- Fix AF_INET6 usage when making in6_addr (dcantrell)

* Tue Jul 25 2006 Paul Nasrat <pnasrat@redhat.com> - 11.1.0.65-1
- Fix noipv6 (pjones)
- Fix nodmraid and nompath (katzj)
- Make kickstart inherit from used installclass (katzj)
- Hide rhel installclass by default (katzj)
- Remove gstreamer/gstreamer-tools whiteout (#197139, katzj)

* Mon Jul 24 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.64-1
- Fix build failure (pjones)
- Fix error handling when adding iscsi 
- Make things a bit more flexible based on the install class
- Fix noipv4 (dcantrel)
- Try not to run dmidecode a bazillion times
- Cleanups for various package selection things

* Fri Jul 21 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.63-1
- Fix serial kickstart installs (clumens)
- Add labels for LVM and RAID (clumens)
- Show preexisting labels when they exist (clumens, #149375)
- Fix traceback for no dosFilesystems (pnasrat)
- Clean up to handle packages in $PRODUCTPATH or $PRODUCTPATH/RPMS
- Various iscsi fixups 

* Thu Jul 20 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.62-1
- Fix drivelist sensitivity when adding devices
- Fix text mode package selection (clumens, #186043)
- Make GMT offset timezones available (clumens, #199076)
- Use attr=2 for xfs per sandeen
- Fix labels of stuff created before install starts (#199605)
- Add Malayalam and Oriya (#197783)
- Fix partitioning (#199459)

* Wed Jul 19 2006 Chris Lumens <clumens@redhat.com> 11.1.0.61-1
- Bring down network interface after fetching files (dcantrel).
- Use dejavu fonts instead of vera (katzj).
- Tweak iSCSI, partitioning, and tasksel UI (katzj, #199451).
- Fix busybox symlinks (katzj, #199463).
- Use reboot instead of shutdown (katzj, #199262).
- Fix DHCP error messages (dcantrel, #199452).

* Tue Jul 18 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.60-1
- Fix va_copy() argument ordering in logMessageV() in loader

* Tue Jul 18 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.59-1
- Add rudimentary firmware loading support to the loader (pjones)
- Drop some whiteout (pnasrat, #196733)
- Fix exec'ing of symlinks (clumens)
- Add basic multipath support (pjones)
- Basic support for multiple repo setup in graphical mode
- Add missing files (clumens)

* Mon Jul 17 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.58-1
- Clean up noipv4/noipv6 stuff stuff (clumens)
- Fix exception handling for test mode 
- Lots of iscsi changes
- Create mount points for protected partitions (clumens)
- Add multipath kernel modules (pjones)
- Add dhcp libs needed by isys to stage2

* Thu Jul 13 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.57-1
- Fix unknown error on shadow file (#196705, clumens)
- Removed inet_calcGateway (clumens)
- Don't guess gateway address in text network UI (#197578, clumens)
- Change iutil.copyFile calls to shutil.copyfile (clumens)
- Removed DRI enable/disable code from xsetup (clumens)
- Removed copyFile, getArch, memInstalled, and rmrf from iutil (clumens)
- Don't pass command as first argument to subprocess calls (clumens)
- Added network debugging mode for readNetConfig() in loader
- Removed "BOOTP" string from loader network config UI
- Added new dialog for network device config in stage2 (katzj)
- Write gateway address to correct struct in manualNetConfig
- Removed IP_STRLEN macro since that's moved to libdhcp
- Link and compile libisys with libdhcp
- Added back 'confignetdevice' and 'pumpnetdevice' in iutil
- Removed isys_calcNetmask and isys_calcNS (clumens)
- Added xkeyboard-config to fix VT switching (katzj)

* Tue Jul 11 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.56-1
- Many changes and fixes in the loader2 network configuration, both
  dhcp and manual IP entry
- Fix stdin/stdout on VNC shells (clumens)
- Check all bootloader entries for Windows (clumens)
- Set UTC box in text install based on Windows existing or not (clumens)
- Remove standalone argument for rhpxl call (clumens)
- Remove call to deprecated method in yuminstall (clumens)
- Fix group selection traceback in text mode (katzj, #197858)

* Mon Jul 10 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.55-1
- Fix findExistingRoots (clumens, #197900)
- Add smartctl to rescue image (dcantrel, #198052)
- Allow relative --rootpath (markmc, #197669)
- Try to fix up RAID6 (#197844)
- Fix keymap generation with serial console (Alexander Dupuy, #198310)

* Fri Jul  7 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.54-1
- Loader changes to support enabling/disabling IPv4 & IPv6
- Manual IP configuration changes in loader to better support IPv{4,6}
- Let GFS2 command line option work (katzj)
- Rescue mode shell fixes (clumens, #197315)
- Add filesystem label chooser to rescue mode (clumens, #196345)
- Use configured interface for VNC connections (clumens, #197721)
- Init process cleanups
- Log requiring package as well as require name (pnasrat)

* Wed Jul  5 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.53-1
- fix typo

* Wed Jul  5 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.52-1
- Add Marathi (#194572)
- Try to let UI fit a little better in LVM dialog (#197334)
- Give a message if we fail to make teh device node (markmc, #197514)
- Fix rescue CD
- Fix minstg2 linking error (#197593)
- Log the transaction error
- gfs2 fixes

* Fri Jun 30 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.51-1
- Remove non-existent paths from LD_LIBRARY_PATH (katzj)
- Calculate IPv4 broadcast address for static IP config
- Started adding debugging mode to init
- Return value checking for exec calls in init and loader
- Do not use wait4()
- WIFEXITED and WEXITSTATUS logic fixes
- Remove runroot stuff from buildinstall (katzj)
- Remove --comp argument from upd-instroot (katzj)
- Do not allow /boot on GFS2 (katzj)
- Move second images to images/ subdirectory (katzj)

* Fri Jun 30 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.50-1
- Rebuild against new libdhcp for fixing more loader segfaults
- Pass the debug log level to libdhcp (markmc, #197175)
- Look for the ks.cfg on all cd drives (notting, #197192)
- Add wlite here, use it (pjones, #196099, #186701)
- Add the start of gfs2 support

* Wed Jun 28 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.49-1
- Fix some memory leaks in the loader (pjones)
- Display fs labels next to rescue choices (clumens, #196345)
- Force graphical mode under vnc (clumens, #190099)
- Fix splitting trees with symlinks (pnasrat, #195240)
- Require system-config-date (clumens, #196452)
- Ensure network UI bits end up written out (clumens, #196756)
- Fix memory corruption in CD install (dcantrel)
- Fix double free with ksdevice=macaddr (dcantrel)
- Fix double free with HTTP/FTP installs (dcantrel, #195749)
- Ensure keyboard layout gets set (clumens, #196466)
- Fix text mode traceback for langs not supported in text 
  mode (clumens, #196615)
- Fix up for yum 2.9.2

* Fri Jun 23 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.48-1
- various pychecker inspired cleanups (clumsn)
- don't try to unmount CDs twice (clumens)
- filter devices without media rather than removable devices (clumens)
- add iscsistart to second stage
- fix pkgorder for yum api changes
- fix manual ip entry (#196154)
- fix tyop in zfcp gui
- fix serial console being propagated to installed system (#196375)

* Wed Jun 21 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.47-1
- Fix iscsi-related tracebacks (clumens/katzj)
- Remove some hacks that were added for s390 so that we fix them right
- Set MALLOC_CHECK_ and _MALLOC_PERTURB for the loader to help flush 
  out possible problems
- Fix kernel selection on s390 (#196150)
- Fixes for inet_pton usage (pjones)
- Use a longer timeout for dhcp requests

* Wed Jun 21 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.46-1
- more tweaking of greek lang-table (#193872)
- mark some strings for translation (#194617)
- add back handling of ksdevice=macaddr (dcantrel, #195907) 
- copy libnss_dns* and libnss_files* to stage1 image to try to fix some 
  of the dhcp oddities (dcantrel)
- fix setupPythonUpdates (clumens)
- wait for usb to be stable when reloading (pjones)
- don't pass netlogger output as a format specifier (pjones)
- fix traceback in zfcp_gui (#196097)
- sort drive list more correctly in autopartitioning
- bunch of tweaking to iscsi code
- ensure that xvd devices are sorted as "first" so they're in front 
  of things like iscsi devices

* Fri Jun 16 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.45-1
- setfiles moved.  more fixing of policy
- Give info on when we add packages as deps (#189050)

* Fri Jun 16 2006 Peter Jones <pjones@redhat.com> - 11.1.0.44-1
- require newer libdhcp
- fix rescue mode console setup (clumens and pnasrat)

* Thu Jun 15 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.43-1
- Some s390 fixes
- dmraid fixing (pjones)

* Thu Jun 15 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.42-1
- Ensure all kernel packages end up in pkgorder
- Fix syntax errors in zfcp code
- Fix broadcast address calculation on 64bit machines
- Fix network config on s390
- Some minor iscsi tweaks

* Thu Jun 15 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.41-1
- fix dep problem

* Wed Jun 14 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.40-1
- add some more kernels to the pkgorder fun
- don't try to switch cds if we've already got the right one inserted
- libaudit for s390
- need openssh installed when building s390 trees

* Wed Jun 14 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.39-1
- only select groups which exist

* Wed Jun 14 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.38-1
- and fix ppc boot.iso (pnasrat)

* Wed Jun 14 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.37-1
- Remove the step ordering debug commit
- Fix traceback due to new xen kernel names
- Another attempt at s390
- Include gptsync in install image so that mactels will boot

* Wed Jun 14 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.36-1
- new xen kernel names
- more trying to fix s390

* Tue Jun 13 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.34-1
- Fix logging segfaults in loader on x86_64
- More release notes viewer fixes

* Tue Jun 13 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.33-1
- Fix text mode package selection (clumens)
- Fix IP editing (clumens)
- Fix segfault on x86_64 dhcp (dcantrel)
- Filter out sitX devs (dcantrel)
- More release notes fixes (dcantrel)
- More pkgorder fixage 

* Tue Jun 13 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.32-1
- fix ppc images

* Tue Jun 13 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.31-1
- Fix loader sigsegv (dcantrel, #194882)
- Fix so we don't require yum.conf (clumens, #194987)
- Fix s390 tree
- Fix pkgorder for new yum API
- Fix release notes (dcantrel)
- More api fixing (clumens/nasrat)

* Mon Jun 12 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.30-1
- make loader flags global (dcantrel)
- fixups for yum 2.9, pull in yum-metadata-parser

* Sat Jun 10 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.29-1
- Fix syslinux requires
- Fix autopartitioning on the mactels
- Close leaky fd in reiserfs label reading code so that partitioning 
  succeeds in that case

* Fri Jun  9 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.28-1
- fix dep problem (clumens)
- initial pass at support for the intel-based macs
- more trying to get s390 trees so they work
- more ipv6 (dcantrel)
- simplify error handling and return values in autopart code (clumens)
- fix going back in a few places (clumens)
- enable user_xattrs and acls by default

* Thu Jun 08 2006 Chris Lumens <clumens@redhat.com> 11.1.0.26-1
- Revert anaconda-runtime files fix.

* Thu Jun 08 2006 Chris Lumens <clumens@redhat.com> 11.1.0.25-1
- More IPv6 fixes (dcantrell).
- Add ipv6 kernel module to image (dcantrell).
- Add noipv6 installer flag (dcantrell).
- Add dosfstools to requires (katzj).
- Fix anaconda-runtime spec file segment (#189415, #194237).
- Better partitioning error messages (#181571).
- Warn if non-linux filesystems can't be mounted on upgrade (#185086).
- Simplify IP address widgets for IPv6 support.
- Use libdhcp instead of pump, fix requires (dcantrell).

* Tue Jun  6 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.24-1
- Read from right stdin for kickstart scripts (Hannu Martikka, #192067)
- Fix ip addr getting on 64bit boxes (clumens, #193609)
- Don't specify window position (clumens)
- Handle PE sizes we don't expect in the UI (clumens, #185272)
- Rescue mode fixes (clumens)
- Remove pointless back button (clumens, #187158)
- Add user-agent to loader HTTP requests (clumens, #98617)
- Use IP instead of hostname if needed (clumens, #191561)
- Write out ipv6 localhost (clumens, #44984)
- Add greek (#193872)
- Fix s390x images (#192862)
- Fix rhpxl location (clumens)

* Tue May 30 2006 Chris Lumens <clumens@redhat.com> 11.1.0.23-1
- Require glib2-devel.
- Look for libglib in the right place on 64-bit machines.

* Tue May 30 2006 Chris Lumens <clumens@redhat.com> 11.1.0.22-1
- Fix going back in the UI.
- Don't try to mount protected partitions twice.
- Hook up new netlink code, debugging (dcantrell).
- Package is actually named pyobject2 (katzj).

* Thu May 25 2006 Chris Lumens <clumens@redhat.com> 11.1.0.21-1
- Fix required CD dialog (pnasrat).
- More anaconda class in the interfaces (dcantrel).
- More netlink helper functions (dcantrel).
- Don't allow logical volumes to be smaller than the volume group's PE
  size in interactive installs (#186412).
- Make error handling for missing packages more robust and allow retrying
  (clumens, pnasrat, #183974).
- Fix hard drive installs (#185292, #187941).
- Don't always show partition review dialog in text installs.
- Fix text-mode installs by adding more stuff to minstg2.img (#191991).
- Skip netlink messages with invalid ARP header (dcantrel).
- Add pygobject to install images (katzj).

* Wed May 24 2006 David Cantrell <dcantrell@redhat.com> 11.1.0.20-1
- Added Netlink helper functions to libisys.a
- Do not pop wait window twice in writeBootloader (clumens)
- For kickstart installs only: Do not allow logical volumes to be smaller
  than the volume group's PE size (#186412, clumens)
- initrd fixes to account for glib2 library movement (clumens)

* Tue May 23 2006 Chris Lumens <clumens@redhat.com> 11.1.0.19-1
- Fix unicode stubs (pjones).
- Fix libdir on ppc64 (katzj).

* Tue May 23 2006 Chris Lumens <clumens@redhat.com> 11.1.0.18-1
- Add slang-devel build requirement.

* Tue May 23 2006 Chris Lumens <clumens@redhat.com> 11.1.0.17-1
- Display full package name in log (pnasrat, #189308).
- Add flags for multipath (pjones).
- Allow protected partitions to be mounted (#105722).
- Fix pkgorder traceback.

* Fri May 19 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.16-1
- Added asix driver (pjones)
- Fix i18n build

* Fri May 19 2006 David Cantrell <dcantrell@redhat.com> - 11.1.0.15-1
- Fix indendation error in handleRenderCallback() that caused hang
- Use gobject.threads_init() model
- Remove gtk.threads_enter()/gtk.threads_leave() wrappers
- Disk and filesystem scanning fixes (clumens)

* Thu May 18 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.14-1
- Few more liveCD tweaks
- And clean up the ppc64 tree a little
- Enable ipv6 by default (pnasrat)
- Fix a traceback in finding root part (clumens)

* Wed May 17 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.13-1
- Fix image building typo
- Remove some dead code (clumens, dcantrel)
- More thread fixing (dcantrel)
- Fix rescue mode (clumens)
- Fix upgrades (clumens)
- Don't try to mount protected partitions on hd ugprades (clumens)
- Hook copyExtraModules back up (clumens, #185344)
- Don't modify the main fs for user/password info on --rootpath install
- Fix kickstart bootloader install
- Some fixes for live CD 

* Tue May 16 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.12-1
- Make mousedev loading less verbose for built-in case (#191814) 
- Ellipsize text (roozbeh, #191844)
- Some more threads for release notes (dcantrel)
- Remove lots of help related stuff (clumens)
- Handle empty drive lists better looking for usb-storage and firewire (pjones)
- Try to make ppc64 trees installable
- Lots of cleanup to the scripts dir.

* Mon May 15 2006 Chris Lumens <clumens@redhat.com> 11.1.0.11-1
- Fix anaconda class typos (katzj).
- Unmount media after running post scripts (#191381).
- Fix VNC installs.
- Support --mtu= in kickstart files (#191328).
- Rework release notes viewer (dcantrel).
- Fix upgrade traceback.
- Fix console keymaps (pjones, #190983, #191541).
- Allow USB and firewire installs, with a warning (pjones).

* Mon May 08 2006 Chris Lumens <clumens@redhat.com> 11.1.0.10-1
- s390x build fix.

* Mon May 08 2006 Chris Lumens <clumens@redhat.com> 11.1.0.9-1
- Fix cmdline installs (clumens, pnasrat).
- Enable multirepo support in kickstart (clumens, pnasrat).
- Begin IPv6 preparations (dcantrel).
- More release notes viewer fixes (dcantrel).

* Thu May  4 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.8-1
- and fix the build

* Thu May 04 2006 Paul Nasrat <pnasrat@redhat.com> - 11.1.0.7-1
- class Anaconda (pnasrat, clumens)
- User/service kickstart handlers (clumens)
- Don't include kernel fs headers (katzj)

* Mon May  1 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.6-1
- fix build

* Mon May  1 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.5-1
- Fix loopback mounted url installs (dcantrel, #189097, #183999)
- Different message during upgrade post scripts (clumens, #189312)
- Remove obsolete startx stub (clumens)
- Default UTC box to checked if we don't find a windows partition (clumens)
- Fix manual IP config (clumens)
- Don't change timezone in rootpath mode (Jane Dogalt, #185930)
- Don't symlink things that don't exist 
- Don't change network config in rootpath mode (#185930)
- Warn on lack of space on upgrade (clumens, #189022)
- Emit --useexisting and --noformat in anaconda-ks.cfg (clumens, #189123)
- Handle NFS mount options (Dave Lehman, #168384)
- Do firewall and auth config in rootpath mode
- Make bootloader code handle live cd case

* Tue Apr 18 2006 Chris Lumens <clumens@redhat.com> 11.1.0.4-1
- Pass version to mkstamp for discinfo files (jkeating).
- Fix FTP method handling.
- Don't download RPMs twice on FTP and HTTP methods (pnasrat, #183654).
- Use libuser for setting root password.
- Fix up rescue image script problems (dcantrel, #188011).

* Tue Apr 04 2006 Chris Lumens <clumens@redhat.com> 11.1.0.3-1
- Fix up for rhpxl Modes changes.
- Fix handling of video driver if there's no list of drivers available.
- Add modes files and libuser to images.
- Allow updates to contain entire directories that may be missing.
- Clean up deprecation warnings.

* Tue Mar 28 2006 Chris Lumens <clumens@redhat.com> 11.1.0.2-1
- Remove reference to pythondeps.

* Tue Mar 28 2006 Chris Lumens <clumens@redhat.com> 11.1.0.1-1
- Prompt for reformatting ancient swap partitions (dcantrel, #122101)
- Fix lots of deprecation warnings (dcantrel)
- Check for suspend signatures in swap (dcantrel, #186018)
- Support logging command in kickstart
- Clean up URLs we try to fetch in the loader
- Fix SELinux conditional inclusion (pjones)
- Remove customClass
- Always ignore disks listed in ignoredisks (#186438)
- Fix loader segmentation fault (#186210)
- Reiser fs label avoidance (dcantrel, #183183)
- Remove traceonly mode
- Add rhpl to minstg2.img (#185840)
- Remove lots of unneeded code in isys, iutil, and elsewhere
  (clumens, dcantrel, pnasrat)

* Tue Mar 21 2006 Jeremy Katz <katzj@redhat.com> - 11.1.0.0-1
- Fix text for rescue images
- Fix some file contexts (#182252)
- Update for new xen kernel names
- Don't try to download package being erased (clumens, #184531)
- Don't show group selection on ks upgrade (pnasrat, #184528)
- Ignore conflicts on upgrade (pnasrat, #184461)
- Don't traceback trying to mount auto fs's (clumens, #182730)
- String fixes (clumens, #181916)
- rootpath fix (clumens, #185172) 
- Prompt for missing images on hd installs (clumens, #185274)
- Don't clobber network on upgrades (pnasrat, (#183203)
- Fix some syntax errors (#185275)
- Cap pe size at 128M (#185272)
- Conditionalize selinux (msw)
- Remove some obsolete code (msw, katzj)
- Ensure we don't ask for no longer needed cds if packages are 
  deselected (pnasrat, #185437) 
- Remove amharic and thai since we don't have fonts (clumens)
- Let's try not doing traceonly and see the size difference for minstg2.img
- Fix i5 (pnasrat, #186070)
- Misc cleanups to iutil (clumens)
- Use system-config-date for text-mode timezone too (clumens)

* Mon Mar  6 2006 Jeremy Katz <katzj@redhat.com> - 10.92.17-1
- fix traceback in size check
- disable size check on upgrade (clumens, #184112)
- try to catch more failures to read repo metadata (clumens)
- only do runlevel 5 if graphical install (dcantrel, #184013)
- adjust to new xen kernel package naming
- add 'vesa' flag to force the use of the vesa driver
- more meaningful error messages on conflicts (pnasrat)
- ensure some dirs are labelled correct (#182252)

* Fri Mar  3 2006 Paul Nasrat <pnasrat@redhat.com> - 10.92.16-1
- Support Everything/globs in ks (pnasrat, clumens, #177621)
- Allow changes if not enough disk space (clumens, #183878)
- Set controlling tty in rescue mode (dcantrel,#182222)
- Sort list of languages (dcantrel)

* Fri Mar  3 2006 Jeremy Katz <katzj@redhat.com> - 10.92.15-1
- conditional code is now in yum (pnasrat)
- sort network devices smarter (clumens, #166842)
- select needed fs entries (#183271)
- more serbian fixes (#182591)

* Tue Feb 28 2006 Jeremy Katz <katzj@redhat.com> - 10.92.14-1
- fix traceback in pkgorder
- don't display xen 
- make partitioning type combo wider (dcantrel)
- handle Serbian locales properly (#182591)

* Mon Feb 27 2006 Jeremy Katz <katzj@redhat.com> - 10.92.12-1
- Dependency whiteout to fix ordering (clumens)
- Fix swap on RAID in kickstart (#176537)
- Add keymap overrides
- Fix segfault with USB CD/DVD drives (#182589)

* Fri Feb 24 2006 Jeremy Katz <katzj@redhat.com> - 10.92.11-1
- fix traceback with segv handler (pjones)
- various language fixes (dcantrel)
- be clearer about askmethod (#182535)

* Thu Feb 23 2006 Jeremy Katz <katzj@redhat.com> - 10.92.10-1
- more bogl removal (dcantrel)
- make the exception dumping less braindead about things we don't 
  want dumped (clumens)
- add backtrace handler to anaconda (pjones)
- fix warnings with new yum in pkgorder
- make conditional packages on deps work (pnasrat)
- suppress some warnings (dcantrel)
- text mode language fixes (dcantrel)

* Thu Feb 23 2006 Jeremy Katz <katzj@redhat.com> - 10.92.9-1
- Fix text mode traceback (dcantrel)
- Skip a few more things in traceback dumps
- Attempt to fix pkgorder so that we require less CDs for "normal" installs

* Wed Feb 22 2006 David Cantrell <dcantrell@redhat.com> 10.92.8-1
- Removed obsolete bogl code (katzj)
- Removed unused code in upgrade.py (pnasrat)
- Check version and packages to upgrade (pnasrat)
- Removed old IDE RAID code from isys (katzj)
- Various traceback fixes
- Don't use underline in device names for hotkeys in bootloader gui (pjones)
- Mount /selinux in rescue mode (katzj)

* Tue Feb 21 2006 Chris Lumens <clumens@redhat.com> 10.92.7-1
- Give Language a default display_mode (dcantrel)
- Get languages that need a default from localeInfo (dcantrel)

* Tue Feb 21 2006 Chris Lumens <clumens@redhat.com> 10.92.6-1
- Set a default language on text mode CJK installs (dcantrel, #180417)
- Fix case-sensitive matching of devices (notting, #182231)
- Be smarter about required media (pnasrat)
- Set MTU in the loader (katzj)
- Add dev package to remove blacklist (katzj, #181593)
- Try to mount device as ext3 in hard drive installs (katzj)
- Sanity check unknown package & group names (pnasrat)
- Reboot after writing exception dump (#181745)
- Confirm in interactive kickstart installs (#181741)
- Fix showing kickstart package selection again
- Don't traceback if we find a %%include file that doesn't exist yet (#181760)
- Skip partitioning if logvol or raid is given in ks (#181806)
- Initialize UTC checkbox (#181737)

* Tue Feb 14 2006 Jeremy Katz <katzj@redhat.com> - 10.92.5-1
- Fix traceback in language group selection
- No remote save traceback button if not network (clumens)
- More fixes for minstg2.img (clumens)
- Disable next/back while installing packages (dcantrel)
- Bump minimum amounts for install, graphical and early swap
- Enable Arabic for text mode (notting)

* Tue Feb 14 2006 Jeremy Katz <katzj@redhat.com> - 10.92.4-1
- improve globbing for xen guest kernels
- Don't add a kernel if one is already selected.

* Mon Feb 13 2006 Jeremy Katz <katzj@redhat.com> - 10.92.3-1
- Don't debug log about missing help text (clumens)
- Reduce deps for pkgorder
- Updated kickstart docs (clumens)

* Mon Feb 13 2006 Jeremy Katz <katzj@redhat.com> - 10.92.2-1
- more x86_64 xen guest fixing

* Mon Feb 13 2006 Jeremy Katz <katzj@redhat.com> - 10.92.1-1
- try to fix x86_64 xen guest

* Sun Feb 12 2006 Jeremy Katz <katzj@redhat.com> - 10.92.0-1
- Fix length of package name in text install (dcantrel, #180469)
- Various minor cleanups
- Support conditional packages for langsupport (pnasrat, #178029)

* Thu Feb 09 2006 Chris Lumens <clumens@redhat.com> 10.91.19-1
- Fix loader typo.

* Thu Feb 09 2006 Chris Lumens <clumens@redhat.com> 10.91.18-1
- Add iscsi support (Patrick Mansfield <patmans AT us.ibm.com>)
- Allow retry if CD image isn't found on NFS server (#109051, dcantrel)
- Fix location of video modes data files
- Add x86_64 kernel-xen-guest (katzj)
- Better loader debugging support (katzj)

* Wed Feb 08 2006 Paul Nasrat <pnasrat@redhat.com> - 10.91.17-1
- Handle bind mounts correctly (#160911, dcantrel)
- Upgrade package black list and make upgrades work
- Disable repo conf for now 
- loader debuginfo
- kickstart - suggest fix (#174597, clumens)

* Mon Feb  6 2006 Jeremy Katz <katzj@redhat.com> - 10.91.16-1
- fix writing out instdata for root password, etc (#180310)

* Mon Feb  6 2006 Jeremy Katz <katzj@redhat.com> - 10.91.15-1
- Remove debugging code that broke showing the Xen option on the task screen
- More sqlite files (#171232)
- Fix traceback for new method pirut depends on
- Ensure /dev/root exists (Patrick Mansfield)
- Force buttonbar on main screen active in congrats (dcantrel, #179924)
- Always pass loglevel (dcantrel)
- BR libXt-devel (dcantrel)
- Don't try to make /dev/mapper devs (pjones)
- More consistency in dev naming for dmraid (pjones)
- Start of iscsi patches (Patrick Mansfield)
- Fix pre-existing RAID chunksize reading (#178291)

* Fri Feb  3 2006 Jeremy Katz <katzj@redhat.com> - 10.91.14-1
- Handle reiserfs labels (dcantrel, #125939)
- Skip more steps in root mode (Jasper Hartline)
- Update driver list for current kernels
- Don't put mapper/ in the swap label (pjones)
- Set file contexts on blkid.tab* (pjones)
- Increase logical volume label field to 32 chars (dcantrel, #174661)
- More exception trimming (clumens)
- Fix args to writeConfiguration (clumens, #179928)
- Fix format strings in label device, proper max for swap labels (pjones)
- Make task definition more dynamic
- Add a hack to remove the xen group if we're running on xen (#179387)

* Thu Feb  2 2006 Jeremy Katz <katzj@redhat.com> - 10.91.13-1
- Speed up timezone screen (clumens)
- Make kickstart interactive mode work (clumens)
- Fix package selection screen (clumens)
- Add sqlite to traceonly to help http/ftp memory usage
- Write out repo config (pnasrat)
- Fix colors on boot splashes (#178033)
- Select lang groups before going to the screen (#178673)
- Clean up handling of grub vs no boot loader (#159658)

* Thu Feb  2 2006 Jeremy Katz <katzj@redhat.com> - 10.91.12-1
- improves %%packages section some more (clumens)
- give a better error on kickstart lvm syntax errors (clumens)
- display vncconnect error messages (clumens)
- make swap labels shorter for cciss (dcantrel, #176074)
- Make /dev/root for mkinitrd (#171662)
- Use pirut stuff for graphical group selection

* Tue Jan 31 2006 Paul Nasrat <pnasrat@redhat.com> - 10.91.11-1
- Factor some yum stuff into yum
- Text Clarification (#178105)
- Don't use install only pkgs (#179381)
- Various dmraid and bootloader fixes (pjones)

* Tue Jan 31 2006 Peter Jones <pjones@redhat.com> - 10.91.10-1
- add dmraid device renaming support for kickstart (pjones)
- fix paths for expat (clumens)
- remove unused functions (clumens)

* Mon Jan 30 2006 Jeremy Katz <katzj@redhat.com> - 10.91.9-1
- Skip partition and bootloader screens if requested for textmode 
  (dcantrel, #178739)
- Don't create /etc/X11/X symlink (dcantrel, #179321)
- Add ethiopic fonts
- Fix traceback in upgrade examine (clumens)
- Free up depsolving storage (pnasrat)
- Fix group selection screen that I mistakenly removed (oops)
- Remove some dead pieces (pnasrat, katzj)

* Thu Jan 26 2006 Jeremy Katz <katzj@redhat.com> - 10.91.8-1
- Remove rpm whiteout (clumens, #178540)
- Fix text in upgrade continue button (dcantrel, #178096)
- Make %%packages in anaconda-ks.cfg shorter (pnasrat)
- Fix text-mode drawing (clumens, #178386)
- Release notes viewer fixes (dcantrel)
- Reset -> reboot (dcantrel, #178566)
- Create ia64 images again (prarit, #175632)
- Make sure boot loader screen gets skipped (clumens, #178815)
- Don't ask about VNC in kickstart
- Don't ask for keyboard under Xen if it fails
- Add more basic "task" selection screen
- Text mode group selection is better now
- Remove some dead code
- Require squashfs-tools  (clumens)
- Fix rescue mode (dcantrel)
- Don't have devices disappear out from under us (Patrick Mansfield)

* Fri Jan 20 2006 David Cantrell <dcantrell@redhat.com> - 10.91.7-1
- Save state when moving back to "upgrade or install" window (#178095).
- Eject CD when in kickstart and given --eject parameter (clumens, #177554).
- Translate combo box and comments (clumens, #178250).
- Disable backend debugging mode for writeKS().
- Added a PYTHONSTARTUP file to autoload readline, etc. (pjones).
- Write %%packages section in template kickstart file (clumens, pnasrat).

* Wed Jan 18 2006 David Cantrell <dcantrell@redhat.com> - 10.91.6-1
- i18n fixes (katzj)

* Wed Jan 18 2006 David Cantrell <dcantrell@redhat.com> - 10.91.5-1
- i386 and ppc rescue image script fixes (jkeating)
- fix kickstart package deselection (clumens, #177530)
- fix header download issues (pnasrat, #177596)
- interface improvements on scp exception dialog (clumens, #177738)
- rescue image additions (pjones, dcantrell, #155399)
- misc kickstart fixes (clumens, #178041, #177519)
- fix fetching repo data on http installs (clumens, #178001)
- add gdk-pixbuf handler for XPM images (#177994)
- timezone screen fixes (clumens, #178140)
- add LSI mptsas driver to module-info (#178130)
- dmraid fixes for kickstart installs (pjones)
- add sr@Latn to lang-table (katzj, #175611)

* Wed Jan 11 2006 Jeremy Katz <katzj@redhat.com> - 10.91.4-1
- Add xen kernels

* Wed Jan 11 2006 Jeremy Katz <katzj@redhat.com> - 10.91.3-1
- remove some unneeded bits from the ppc boot.iso to make it smaller
- fix some text display (notting, #177537)
- Misc kickstart fixes (clumens)

* Tue Jan 10 2006 Jeremy Katz <katzj@redhat.com> - 10.91.2-1
- fix hard drive installs (pjones)

* Tue Jan 10 2006 Jeremy Katz <katzj@redhat.com> - 10.91.1-1
- more ppc rescue image (jkeating)
- actually commit the dmraid fix (pjones)

* Mon Jan  9 2006 Jeremy Katz <katzj@redhat.com> - 10.91.0-1
- tweaked selection stuff a little to be the same code as pirut
- tweak exception window to have an image and be better sized (dcantrell)
- write out RAID device name (clumens)
- scroll group list properly (dcantrell)
- fix ppc rescue image (jkeating)
- dmraid detection fix (pjones)

* Fri Jan  6 2006 Jeremy Katz <katzj@redhat.com> - 10.90.25-1
- no sr@Latn yet since the po files haven't been added

* Fri Jan  6 2006 Jeremy Katz <katzj@redhat.com> - 10.90.24-1
- move a11y stuff earlier
- fix the text mode progress bar (pnasrat, #176367)
- fix ppc drive unreadable warnings (#176024)
- add serbian locales (#175611)
- preserve review checkbox between combo box selections (dcantrell, #176212)
- quote ethtool args (#176918)
- various spacing cleanups (dcantrell)
- a few fixes to the group selector (dcantrell)
- don't try to make the timezone widget bigger than screen (clumens, #176025)
- fix rescue mode traceback (clumens)
- fix message wording on package retry (clumens, #155884)
- quiet debug spew in anaconda.log (clumens, #171663)
- add ppc rescue script from jkeating (#177003)

* Tue Dec 20 2005 Jeremy Katz <katzj@redhat.com> - 10.90.23-1
- more pkgorder fixes (pnasrat)
- fix some debug spew (notting)
- segfaults in the loader should at least give us a stacktrace to work from
- fix some padding on the network screen

* Mon Dec 19 2005 Jeremy Katz <katzj@redhat.com> - 10.90.22-1
- add more encoding modules to traceonly (clumens, #175853)
- Fix text installs (pnasrat, #175773)
- Fix for yum API changes (pnasrat)
- Don't install the smp kernel even if NX is available
- Adjust to be more dynamic about colors with syslinux-splash's
- Use the selected language for default keyboard layout (clumens, #172266)
- Better naming for psuedo-filesystems in /etc/fstab (dcantrel, #176149)
- Clean up image handling for new graphics
- Don't do the splashscreen stuff anymore.  If the window is too slow to 
  appear, we should fix that instead

* Thu Dec 15 2005 Jeremy Katz <katzj@redhat.com> - 10.90.21-1
- fix pkgorder for new group code
- fix ub vs usb-storage
- remove some redundant code (clumens)

* Thu Dec 15 2005 Jeremy Katz <katzj@redhat.com> - 10.90.20-1
- Fixes for new timezone stuff (pnasrat)
- Fix transaction sorting (pnasrat)
- Enable dmraid by default

* Wed Dec 14 2005 Chris Lumens <clumens@redhat.com> 10.90.19-1
- Use system-config-date for timezone selection UI (#155271).
- Work on vnc+shell spawning (dcantrell).
- Whiteout fixes (pnasrat, katzj).
- Progress bar fixes (katzj).
- Depsolving speedups (katzj).

* Mon Dec 12 2005 Jeremy Katz <katzj@redhat.com> - 10.90.18-1
- Handle monitor configuration in kickstart via "monitor" keyword instead of 
  "xconfig" consistently (clumens)
- Fix joe as nano (#175479)
- Try to get hard drive installs working again
- First steps towards using ub
- Fix depcheck progress bar to actually give progress.  

* Sun Dec 11 2005 Peter Jones <pjones@redhat.com> - 10.90.17-1
- Full dmraid support.  (still disabled by default)

* Sat Dec 10 2005 Jeremy Katz <katzj@redhat.com> - 10.90.16-1
- Ensure upgrades to depsolve and remove db locks (pnasrat)
- Tweak for improved and sortable groups/categories
- Put back basic text-mode package selection (#175443)

* Thu Dec  8 2005 Jeremy Katz <katzj@redhat.com> - 10.90.15-1
- Fix various typos in the new group selection code (clumens)
- Support bytesPerInode on RAID (Curtis Doty, #175288)
- Stub some more for the loader to fix line-drawing chars again
- Handle file read failures better (pnasrat)
- Initial support for upgrades again (pnasrat)
- Minor padding tweaks to the UI

* Thu Dec  8 2005 Jeremy Katz <katzj@redhat.com> - 10.90.14-1
- Fix up for moved x locale data
- Remove vnc hack now that VNC knows where to look for fonts
- Don't go to text mode for no mouse (notting)
- Update to work with yum 2.5.0 cvs snap
- New package selection code
- Add new chinese font back now that we're using squashfs (#172163)
- The return of locale-archive usage

* Mon Dec 05 2005 Chris Lumens <clumens@redhat.com> 10.90.13-1
- Reword media check dialog (dcantrell, #174530).
- gcc41 compile fixes (pjones).
- Add genhomedircon, setfiles, and /etc/shells for selinux.

* Thu Dec  1 2005 Jeremy Katz <katzj@redhat.com> - 10.90.12-1
- some release notes viewer fixing (dcantrell)
- allow %%pre scripts in an %%include (clumens, #166100)
- fix the squashfs stuff to actually work
- hack around slang not initializing utf8 mode so that we have line 
  drawing chars (#174761) 

* Thu Dec  1 2005 Jeremy Katz <katzj@redhat.com> - 10.90.11-1
- reworded media check prompt (dcantrell, #174472)
- let's try squashfs... 

* Wed Nov 30 2005 Jeremy Katz <katzj@redhat.com> - 10.90.10-1
- Don't split transactions on not split install types (pnasrat, #174033)
- Fix None vs "" for vncpasswd in test mode (Patrick Mansfield)
- Make release notes viewer as large as the screen (dcantrell)
- Allow system-logos instead of fedora-logos for the package name
- Try to build SELinux policy so that things work with selinux 
  2.x policy (#174563)

* Tue Nov 29 2005 Chris Lumens <clumens@redhat.com> 10.90.9-1
- Another stab at including email.Utils everywhere (#173169).
- Remove unneeded isys.sync calls (pjones).
- Fix /dd.ig in initrd (Dan Carpenter).
- Report no DNS servers if a hostname used (pnasrat, #168957).
- Fix ppc32 from CD (katzj, #174135).
- Don't look for hdlist when booting CD1 and using FTP/HTTP (katzj).
- Fullscreen release notes viewer (dcantrell).

* Mon Nov 21 2005 Jeremy Katz <katzj@redhat.com> - 10.90.8-1
- don't load pcspkr on ppc to avoid crashes on the g5

* Sun Nov 20 2005 Jeremy Katz <katzj@redhat.com> - 10.90.7-1
- fix backwards whiteout handling (#173738)
- fix bug in depsolver which would bring in a package for an already 
  satisfied dep

* Sat Nov 19 2005 Jeremy Katz <katzj@redhat.com> - 10.90.6-1
- fix removal of packages to not traceback
- fix anaconda.dmraid logging (clumens)

* Fri Nov 18 2005 Paul Nasrat <pnasrat@redhat.com> - 10.90.5-1
- Disable sqlite cache for pkgorder
- Fix for new selinux context types (katzj)
- vnc parameter handling (clumens)
- Add ellipsis (notting)

* Thu Nov 17 2005 Jeremy Katz <katzj@redhat.com> - 10.90.4-1
- don't traceback on unresolvable deps (#173508)
- fix pkg.arch for %%packages
- another hack for vnc
- debug prints to log.debug (#173533)

* Thu Nov 17 2005 Paul Nasrat <pnasrat@redhat.com> - 10.90.3-1
- Add group processing to buildinstall
- Add createrepo requires

* Thu Nov 17 2005 Jeremy Katz <katzj@redhat.com> - 10.90.2-1
- more pkgorder fixing (clumens)
- fix cd installs to not fall into the "not a real install method" case :)

* Thu Nov 17 2005 Jeremy Katz <katzj@redhat.com> - 10.90.1-1
- add handling for dmraid/nodmraid
- fix removals of packages which have already been removed
- turn off dmraid by default
- fix pkgorder (clumens)

* Thu Nov 17 2005 Jeremy Katz <katzj@redhat.com> - 10.90.0
- more tree build fixes
- fix group removal 
- non iso install fixes (clumens)
- pkgorder fixing (clumens)
- dmraid support (pjones)
- crude language support group hack

* Wed Nov 16 2005 Chris Lumens <clumens@redhat.com> 10.89.20.1-1
- Fix indentation.

* Wed Nov 16 2005 Paul Nasrat <pnasrat@redhat.com> - 10.89.20-1
- Restore YumSorter for pkgorder
- Single anaconda installer yum class
- Switching CD method 

* Wed Nov 16 2005 Jeremy Katz <katzj@redhat.com> - 10.89.19.1-1
- be explict about pango-devel being needed

* Wed Nov 16 2005 Jeremy Katz <katzj@redhat.com> - 10.89.19-1
- Fix vt switching with modular X
- Lots of CD install fixes (clumens, pnasrat)
- Clean up exception dump stuff
- Some more steps towards dm-raid support (pjones)
- Log info messages

* Wed Nov 16 2005 Jeremy Katz <katzj@redhat.com> - 10.89.18-1
- remove new chinese font since its too big for cramfs (#172163)
- Fix typo in trimpciids (notting)
- Don't build locale-archive for now since its too big for cramfs

* Tue Nov 15 2005 Jeremy Katz <katzj@redhat.com> - 10.89.17-1
- missed an x lib somehow

* Tue Nov 15 2005 Jeremy Katz <katzj@redhat.com> - 10.89.16-1
- lots of updates for modular X
- allow a shell on tty1 if using vnc
- various fixes for cd/install method stuff (pnasrat, clumens, katzj)
- install smp kernel if NX present (#172345)
- work with multiple videoaliases files (notting)

* Tue Nov 15 2005 Jeremy Katz <katzj@redhat.com> - 10.89.15-1
- fix up for new selinux policy

* Mon Nov 14 2005 Paul Nasrat <pnasrat@redhat.com> 10.89.14-1
- Move sorter for CD/pkgorder into yuminstall
- Add support for ub devices (katzj)

* Mon Nov 14 2005 Paul Nasrat <pnasrat@redhat.com> 10.89.13-1
- Reinstate image based install methods (excluding hd for now)
- Clean up install method classes
- device-mapper support (pjones)
- Log warning on no network link (katzj)
- Clean up error handling for pkgorder (clumens)

* Fri Nov 11 2005 Chris Lumens <clumens@redhat.com> 10.89.12-1
- Add buildreq for yum (katzj)
- Fix loader log levels (katzj)
- Add more libraries for dogtail (katzj)

* Thu Nov 10 2005 Jeremy Katz <katzj@redhat.com> - 10.89.11-1
- Fix stdout logging to print stuff (clumens)
- Start of some sorting/splitting stuff for CDs (pnasrat) 
- Make missing modules lower priority
- Look for xen devices
- Add some of the necessary requirements to try to get dogtail working (#172891)

* Thu Nov 10 2005 Chris Lumens <clumens@redhat.com> 10.89.10-1
- Add e2fsprogs-libs to the install images.

* Wed Nov  9 2005 Jeremy Katz <katzj@redhat.com> - 10.89.9-1
- Create interface earlier to prevent kickstart traceback (clumens)
- Logging fixes, everything should be in the logfile (clumens)
- Get rid of help which is irrelevant
- Clean up loader log levels

* Tue Nov  8 2005 Jeremy Katz <katzj@redhat.com> - 10.89.8-1
- Fix backwards message on upgrade (#172030)
- New chinese fonts (#172163)
- Don't try to update a progress window that's already popped (clumens, #172232)
- Fix snack deprecation warnings (clumens, #172232)
- Get rid of some cruft in traceback dumps (clumens)
- Add a method to check for "real" consoles, add xen console to the list 
  of weird stuff
- Basic support for transaction errors other than tracebacks...
- Fix a kickstart traceback for authconfig
- Add xenblk and xennet to module-info

* Mon Nov  7 2005 Jeremy Katz <katzj@redhat.com> - 10.89.7-1
- More detailed error logging (pnasrat)
- Add bnx2 driver (pjones)
- Various kickstart fixes (clumens, #172356)
- Fix shadow password convert (clumens)

* Fri Oct 28 2005 Jeremy Katz <katzj@redhat.com> - 10.89.6-1
- Make char devices slightly later to avoid tracebacks during tree compose
- Extract kernel-xen-guest for vmlinuz and initrd in images/xen
- Kickstart fix (clumens)
- Add some support for xen xvd blockdevs
- Select kernel-xen-guest as appropriate
- Ensure proper arch of glibc is selected (#171997)
- Select all proper multilib parts of a package (#171026) 

* Thu Oct 27 2005 Jeremy Katz <katzj@redhat.com> - 10.89.5-1
- Another fix for kickstart + help hiding
- Fix finding of kernel type
- Make synaptics device nodes before X starts (clumens)
- Use nofb by default
- Add pycairo stuff (clumens)
- Set minimum displayed log level to WARNING, everything is still in 
  the logfiles (clumens)
- Try to clean up syslog (clumens)
- Allow installation of hypervisor + xen host kernel by booing with 'xen0' on 
  the installer command line
- Fix x86_64 traceback

* Mon Oct 24 2005 Jeremy Katz <katzj@redhat.com> - 10.89.4-1
- changed the wrong field in lang-table

* Mon Oct 24 2005 Jeremy Katz <katzj@redhat.com> - 10.89.3-1
- don't do xsetroot anymore
- allow retrieving updates.img with 
  updates=(http|ftp)://host/path/to.img (clumens)
- some upd-instroot fixes (clumens)
- only get yum filelists when needed (pnasrat)
- clean up exception scp'ing (clumens)
- don't write empty authconfig line (clumens, #171558)
- make kickstart errors report line number of error (clumens)
- select most appropriate kernel (kernel-smp, etc)
- ensure we get a boot loader package installed
- minor fix for ia64 image creation
- tweaks to backend setup 
- don't have help as visible in the glade file so we don't have the pane 
  appear when doing a kickstart install
- use pl2 keymap for Polish (3171583)
- allow passing product information with env vars to help live cd

* Thu Oct 20 2005 Jeremy Katz <katzj@redhat.com> - 10.89.2-1
- fix references to second stage module stuff that caused breakage

* Thu Oct 20 2005 Jeremy Katz <katzj@redhat.com> - 10.89.1-1
- fix for mkcramfs -> mkfs.cramfs
- Use minstg2.img instead of netstg2.img/hdstg2.img in the loader

* Thu Oct 20 2005 Jeremy Katz <katzj@redhat.com> - 10.89.0-1
- Fix SELinux policy loading (clumens)
- Fix translation import for kickstart (laroche)
- Add yumcache (pnasrat)
- Upgrade blacklisting (pnasrat)
- Clean up exception copying (clumens)
- Improve text mode exception dialog too (clumens)
- Don't allow bootable partitions on XFS
- Some speed improvements, progress bars, etc for package stuff (pnasrat)
- Clean up image creation, move all modules to initrd.img.  

* Fri Oct 14 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.32-1
- fix typo causing traceback (pnasrat)
- Create character device nodes to fix synaptics (clumens)

* Wed Oct 12 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.31-1
- Handle missing metadata (pnasrat)
- Give indication of kickstarts scriptlets running (#170017)
- Fix a traceback with RAID (#170189)
- Fix an FTP install traceback (#170428)
- Clean up floppy stuff (clumens)
- Clean up some warnings (clumens)
- Make IDE device node creation cleaner
- Change location of modes data files

* Mon Oct 10 2005 Chris Lumens <clumens@redhat.com> 10.3.0.30-1
- Fix requirements for s390, s390x, ppc64.
- Fix typo in scripts/upd-instroot.

* Fri Oct 07 2005 Chris Lumens <clumens@redhat.com> 10.3.0.29-1
- Deal with new load_policy. (katzj)
- Create an SELinux config. (katzj)
- Use rhpxl instead of rhpl for X configuration.
- Use pykickstart.

* Wed Oct 05 2005 Chris Lumens <clumens@redhat.com> 10.3.0.28-1
- Add yuminstall (katzj, #169228)
- Skip bootloader screen unless modifying partitions (katzj, #169817)
- Don't skip manual partitioning on custom (katzj, #169001)
- Partitioning UI fixes (katzj)
- Don't overwrite empty strings in ksdata with None.
- Move kickstart file handling into pykickstart package.
- Kickstart LVM and RAID partitioning fixes.

* Fri Sep 30 2005 Chris Lumens <clumens@redhat.com> 10.3.0.27-1
- More kickstart script fixes.

* Tue Sep 27 2005 Chris Lumens <clumens@redhat.com> 10.3.0.26-1
- kickstart script fixes

* Sat Sep 24 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.25-1
- single ppc boot images stuff from dwmw2 (pnasrat, #166625)
- ppc netboot stuff from dwmw2 (pnasrat, #165239)
- fix some of the yum backend for yum changes
- Add a button to the traceback dialog to allow saving via scp (clumens)
- Don't load the parallel port module (#169135)
- Fix group deselection to not remove everything
- Move repo setup and group selection earlier (pnasrat)

* Tue Sep 20 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.24-1
- Some kickstart %packages fixes (clumens)
- Don't copy null bytes into syslog (clumens)
- New exception dialog (clumens)
- Fix a traceback (pnasrat)
- FTP/HTTP installation might now work (pnasrat)
- Very basic group selection in the UI

* Mon Sep 19 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.23-1
- fix a silly typo that would cause tracebacks
- Look for help in /tmp/updates too (#168155)
- Add skge driver (#168590)
- Some fixes to hopefully get x86_64 trees working

* Fri Sep 16 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.22-1
- Fix segfaults with nfs mounting
- Start of url install methods (pnasrat)
- Basic package/group selection is back in kickstart
- Macro magic fixups
- Use onboot by default for network devices in kickstart

* Thu Sep 15 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.21-1
- Run pre scripts for kickstart (clumens)
- Another tree fix
- Handle NULL for device->driver from kudzu (notting)
- Clean up internal mount stuff to be more extend-able 

* Wed Sep 14 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.20-1
- Fix runlevel setting (pnasrat)
- More dead stuff fixing.

* Tue Sep 13 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.19-1
- Fix pcmcia import traceback
- Some more kickstart fixing (clumens)
- Make SELinux/firewall defaults be done by the objects, not in the UI
  - This fixes booting with selinux=0, policy load failure, etc
- Allow sparse updates.img with yum, urlgrabber and rpmUtils too
- Some dead code removal
- PCMCIA for the loader again (notting)
- install.log tweaking

* Mon Sep 12 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.18-1
- Add back genhdlist to try to fix multiarch composes (pnasrat)
- Really fix disabling of upgrades
- Some typo fixes for X configuration and post-install config
- Remove some dead code related to boot disks, using fdisk/fdasd, X 
  configuration, pcmcia
- Move ppc X stuff to rhpl (clumens)
- Fix some kickstart stuff (clumens)
- Fix RPM logging output -> the log file
- Use gtkhtml2 for release notes

* Fri Sep  9 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.17-1
- more X fixage
- build against new kudzu that doesn't segfault :)

* Fri Sep  9 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.16-1
- More typo fixes (notting)
- Fix rhpl requires

* Fri Sep  9 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.15-1
- Fix typo that broke image building.
- Start of getting post-install stuff working (pnasrat)

* Fri Sep 09 2005 Chris Lumens <clumens@redhat.com> 10.3.0.14-1
- logging fix when running in test mode

* Fri Sep 09 2005 Bill Nottingham <notting@redhat.com> 10.3.0.13-1
- adapt to new X driver model in kudzu and associated rhpl changes
- pcitable/modules.pcimap/modules.usbmap are no longer used in probing;
  remove support for them and add modules.alias usage
- Turn off help (katzj)
- Kickstart fixes (clumens)

* Wed Sep 07 2005 Paul Nasrat <pnasrat@redhat.com> 10.3.0.12-1
- yum backend selinux file_context 
- Start using new kickstart code (clumens)
- Error handling and messages for kickstart (clumens)
- Partitioning kickstart fixups (clumens)

* Thu Sep 01 2005 Paul Nasrat <pnasrat@redhat.com> 10.3.0.11-1
- Yum backend work (macro support, whitelist)
- qla2100 (katzj, #167065)
- Kickstart Parser (clumens)
- authconfig handling changes (clumens)
- Autopartitiong Traceback fix (katzj)

* Fri Aug 26 2005 Jeremy Katz <katzj@redhat.com>
- More work from pnasrat on getting the yum backend working
- Don't set some irrelevant network TYPE= (#136188, #157193)
- New and improved autopartitioning screen

* Fri Aug 19 2005 Paul Nasrat <pnasrat@redhat.com> 10.3.0.10-1
- Working towards new backend architecture

* Thu Aug 18 2005 Chris Lumens <clumens@redhat.com> 10.3.0.9-1
- Rebuild for new cairo.
- Add support for ksdevice=bootif (Alex Kiernan, #166135).
- Fix /dev/tty3 logging problems.
- Add support for Pegasos machines (dwmw2, #166103).
- Switch to Sazanami font (#166045).
- Fix for autopart not in lvm (msw).

* Mon Aug 15 2005 Chris Lumens <clumens@redhat.com> 10.3.0.8-1
- Remove dead --ignoredeps code (katzj, #165224).
- New logging system with log levels and remote logging capabilities.
- Fix typo in network code (pnasrat, #165934).
- Fix buffer overrun in md5sum code (Dustin Kirkland).
- Add mptspi and mptfc drivers (katzj).
- Timestamp fixes (dgregor, #163875).

* Thu Jul 21 2005 Chris Lumens <clumens@redhat.com> 10.3.0.7-1
- Remove firewall configuration screen.  Open SSH by default and set
  SELinux to enforced.

* Wed Jul 20 2005 Paul Nasrat <pnasrat@redhat.com> 10.3.0.6-1
- Ensure boot flag only on correct partition on pmac (#157245)
- Plug in yum for nfs:/ by default
- Include sungem_phy for pmac

* Wed Jul 13 2005 Chris Lumens <clumens@redhat.com> 10.3.0.5-1
- Fix pygtk bug on progress bars.
- Bump ia64 boot.img size (katzj, #162801).
- Fix for clearpart --none (katzj, #162445).
- yum dependancy fixes (pnasrat).
- name.arch fix for kickstart (pnasrat).
- Fix multiple NICs in kickstart config files (#158556).

* Thu Jul 07 2005 Paul Nasrat <pnasrat@redhat.com> 10.3.0.4-1
- Select kernel-devel (katzj #160533)
- Fixups for ia64 images from prarit (katzj #162072)
- Include yum libraries in stage2
- Remove gzread.py (clumens)

* Wed Jun 29 2005 Chris Lumens <clumens@redhat.com> 10.3.0.3-1
- Mount "auto" filesystems on upgrade (#160986).
- Add cairo for new pango/gtk (katzj).
- Delete labels on swap and ext3 partitions before formatting.
- Remove langsupport keyword from kickstart.

* Mon Jun 20 2005 Bill Nottingham <notting@redhat.com> - 10.3.0.2-1
- fix genhdlist

* Fri Jun 17 2005 Jeremy Katz <katzj@redhat.com> - 10.3.0.1-1
- Fix release notes for ftp installs (#160262)
- Fix fd leak in edd support (Jon Burgess, #160693)
- Fix typo breaking pseries console (pnasrat, #160573)
- Allow ignoring packages without specifying the arch (clumens, #160209)
- Add gpart (clumens, #55532)
- Some warning fixes.
- Use full bterm font if available (#159505)
- Fix quoting of pvs in anaconda-ks.cfg (#159193)
- Fix segfault on upgrades
- String tweaks (clumens, #159044, #156408)
- Don't traceback on preexisting RAID (clumens, #159079, #159182)
- Fix display size of PVs (clumens, #158696)
- Don't consider drives without free space for partitions (pjones)
- Langsupport fixes (clumens, #154572, #158389)
- Hack around usb-storage slowness at finding devices that leads to the 
  reload not occurring
- Handle FC3 swap label format and convert to right format (#158195)
- Only set things up to change the default kernel if we're booting us (#158195)
- Fix deps on upgrades (#157754)
- Try to keep install screen from moving with length of strings
- Fix autopart problem leaving some freespace the size of where you 
  started your partition growing
- Allow excluding name.arch in kickstart (Dave Lehman, #158370)
- Don't spew an error if essid or wepkey isn't set (#158223)
- Add megaraid and other new drivers (#157420) 
- Left pad RAID uuid (clumens, #136051)
- synaptics tweak (pnasrat)
- Fix telnetd to use devpts instead of legacy ptys (#124248)

* Thu May 19 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.64-1
- Handle longer arch strings (notting)
- Fix traceback in network screen (#158134)
- Include synaptics for X config (pnasrat)
- Magic boot for mac vs mac64 on disc1/dvd (pnasrat)
- Bump point at which we use graphical stage2 for http/ftp (#157274)
- Use uuid in mdadm.conf, stop using copy of md.h (#136051)
- Support deletion of bootloader entries in text mode (#125358)
- Support RAID /boot on pSeries along with handling of multiple PReP 
  partitions (Dustin Kirkland)

* Tue May 17 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.63-1
- add arch to buildstamp (notting, #151927)
- Fix am.po format strings

* Tue May 17 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.62-1
- Fix execcon used for anaconda (pjones)
- Fix traceback on tui netstg2.img install (#157709)
- Fix various splittree bugs (clumens, #157722, #157721, #157723)
- Blacklist perl.i386 on x86_64 to be removed on upgrade (pnasrat, #156658)
- Fix drive sorting (clumens)
- Remove %%installclass support for kickstart since it's never worked (#149690)
- Fix name.arch in packages (pnasrat)
- Remove bogus pre-existing RAID info on kickstart installs (clumens, #88359)
- Pretend to have nano in the rescue environment
- Don't load stage2.img into RAM for rescue mode if booted 
  with 'linux text' (#155398)

* Thu May  5 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.61-1
- and fix pkgorder for the gfs stuff

* Thu May  5 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.60-1
- Better handling of the langsupport group (clumens)
- Don't install the gfs stuff for all kernel variants, that brings in 
  kernel-smp on an everything install (#156849)
- Don't grow a partition beyond the largest freespace on a drive
- HFS+ support
- Pull in more selinux policy files to try to get /home labeled right
- Fix typo causing segfault (pnasrat)

* Tue May  3 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.59-1
- Try to use the fb res on pmac
- Always reset terminal attrs on ppc (notting, #156411)
- Remove bogus preexisting LVM info when doing kickstart 
  installs (clumens, #156283)

* Mon May  2 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.58-1
- Beep on CD insertion, not after
- Fix language support selection (clumens)
- Fix nfsiso (clumens)
- Misc X config fixes for ppc.  Boot with "usefbx" to use fbdev 
  instead again (#149188)

* Thu Apr 28 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.57-1
- Fix bind mounts (clumens, #151458)
- Fix hard drive installs (clumens)
- Re-add bluecurve icons
- Attempt to fix Chinese

* Wed Apr 28 2005 Peter Jones <pjones@redhat.com> - 10.2.0.56-1
- Fix mediacheck calls from cdinstall.c, and make mediacheck.c include
  its own header so typechecking works.

* Wed Apr 27 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.55-1
- Don't spam about package downloads in cmdline mode (#155250)
- Apply jnovy's patch to fix space calculations for > 2 TB devices (#155709)
- Set default font for CJK better (clumens, #156052)
- Add --label for part in kickstart (clumens, #79832)
- Ensure decimal IP addrs (#156088)
- Apply patch from Joe Pruett for rpmarch= fixes (#101971)
- Don't set SUPPORTED unnecessarily (#115847)
- Give more room for cyl #s (#119767)
- Bump size of diskboot.img
- Add back button for required media message (#114770)
- Fix lvs showing up with a mountpoint of 0 (#153965)
- Nuke some debug code
- Don't try to unmount (tmpfs) /dev
- Write a minimal mtab to avoid fsck/mount complaints (pjones)

* Wed Apr 27 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.54-1
- Only select kernel-smp that matches the arch of kernel (#149618)
- Apply the read of Dustin Kirkland's checkpoint fragment sum patch
- Fix order of retry/reboot (#155884)
- Probe macio (pnasrat, #154846)

* Tue Apr 26 2005 Chris Lumens <clumens@redhat.com> 10.2.0.53-1
- Beep at CD prompt and on install completion (katzj, #109264, #116681).
- Add kernel-smp-devel and kernel-hugemem-devel to exclude list (katzj).
- Fix buffer overflow when CD/DVD images are several directories deep
  (#154715).
- Fix media check (pjones).
- Set language on CD and no pass installs (#149688).
- Fix disappearing button bar (#151837).
- Upgrade PReP on iSeries (pnasrat).

* Thu Apr 21 2005 Chris Lumens <clumens@redhat.com> 10.2.0.52-1
- Allow mediacheck in kickstart (katzj, #116429)
- Check for a drive being selected in autopart (katzj, #124296)
- Fix traceback in language selection screen (#155103)
- Mark "Downloading" for translation (katzj, #155214)
- Applied Dustin Kirkland's checkpoint fragment sum patch for mediacheck.
- Make anaconda-ks.cfg ro (pnasrat)
- Ensure there are <= 27 RAID members (katzj, #155509)
- Fix fsoptions for preexisting partitions in kickstart (#97560).

* Fri Apr 15 2005 Chris Lumens <clumens@redhat.com> 10.2.0.51-1
- Decode source URL for writing to anaconda-ks.cfg (#154149).
- Add kernel-xen?-devel to the exclude list (katzj, #154819).
- Fix text wrapping (#153071, #154786).
- Various UI fixes.
- Select language packages for all selected languages (#153748, #154181).

* Wed Apr 13 2005 Peter Jones <pjones@redhat.com> - 10.2.0.50-1
- revert last week's nptl hack in upd-instroot

* Wed Apr 13 2005 Peter Jones <pjones@redhat.com> - 10.2.0.49-1
- Cut summaries off to avoid layout problems (katzj, #154459)
- Add script to update loader in initrd (katzj)
- Typo fixes in upgrade.py (katzj, #154522)
- Fix rescue mode network enabling (katz, #153961)
- Add libaudit to the graphical stage2 file list, for Xorg
- Various language fixes (clumens, #152404)

* Mon Apr 11 2005 Peter Jones <pjones@redhat.com> - 10.2.0.48-1
- Typo fixes in gui.py (menthos, #154324)
- Don't try to do early swap in test mode, and use yesno not okcancel (msw)
- If the install language is an unknown locale, use en_US.UTF_8
- Fix upgrade to make devices available in the changeroot

* Thu Apr  7 2005 Peter Jones <pjones@redhat.com> - 10.2.0.47-1
- put ncurses in the net images, too.
- (notting) put redhat-artwork in the GR images.

* Thu Apr  7 2005 Peter Jones <pjones@redhat.com> - 10.2.0.46-1
- put readline in the net images
- fix linxuthreads warnings in upd-instroot
- (clumens) fix build-locale-archive

* Wed Apr  6 2005 Elliot Lee <sopwith@redhat.com> - 10.2.0.45-1
- Deal with GUI-mode language traceback

* Wed Apr  6 2005 Elliot Lee <sopwith@redhat.com> - 10.2.0.44-1
- Deal with text-mode language traceback
- (clumens) Don't set SYSFONTACM 

* Wed Apr 06 2005 Peter Jones <pjones@redhat.com> - 10.2.0.43-1
- Don't remove libraries in stage2 that don't match the one from linuxthreads/

* Tue Apr 05 2005 Peter Jones <pjones@redhat.com> - 10.2.0.42-1
- Use linuxthreads libraries even if they're not the default, unless
  explicitly told to use nptl

* Tue Apr 05 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.41-1
- Make sure $LANG is set right for the second stage.
- Fix kickstart traceback trying to skip a nonexistant step.
- Import encodings.idna (sopwith, #153754).
- Fix image building problems.
- Fix kickstart traceback when using shortened forms of language names
  (#153656).

* Mon Apr 04 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.40-1
- Add locale information for 'C' to fix RPM building.

* Sat Apr  2 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.39-1
- fix makefile deps to fix build

* Fri Apr 01 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.38-1
- Set default language for /etc/sysconfig/i18n (#149688).
- Make sure hostname option isn't greyed out if using static IP (#149116).
- Remove unused packages, python library bits, and locale info (katzj).
- Add missing Indic font packages (katzj).
- Various language fixups.

* Wed Mar 30 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.37-1
- try not using maxcpus=1 for arches which still had it
- don't use the reserved variable name str (sopwith)
- various language fixups (clumens)

* Tue Mar 29 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.36-1
- tree build fix

* Tue Mar 29 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.35-1
- dead files can't really be installed (aka, fix the build)

* Tue Mar 29 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.34-1
- Adjust pcmcia module loading for new in-kernel ds (pjones, #151235)
- Make the rescue images identify which arch they're for (pjones, #151501)
- Delete LV snapshots before the parent LV (pjones, #151524)
- Check various forms of a language nick.
- Allow setting MTU on the command line (katzj, #151789)
- Remove dead code in config file handling and sparc booting (katzj)
- Product name and path simplification (katzj)
- Fixes for lang-table format change (katzj, clumens)

* Fri Mar 25 2005 Bill Nottingham <notting@redhat.com> - 10.2.0.33-1
- fix typo in partedUtils.py

* Thu Mar 24 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.32-1
- Switch theme to clearlooks
- Add new Solaris partition id
- Mark some more strings for translation
- Fix xfs fs creation (Lars Hamann, #151378)

* Wed Mar 23 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.31-1
- Add libgcc for images.
- Rewrite language handling.
- Fix readImageFromFile deprecation warning (katzj).
- Don't hide groups which just have metapkgs (katzj, #149182).
- Load SELinux booleans (katzj, #151896).

* Tue Mar 22 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.30-1
- Try harder on the libstdc++ include.
- Fix /etc/resolv.conf fir interactive kickstart installs (#151472).

* Mon Mar 21 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.29-1
- Fix beta nag translation
- Fix button growing (clumens, #151208)
- Add libstdc++ for images (clumens)
- Clean up congrats screen (clumens, #149526)
- Fix CD ejecting in loader (pnasrat, #151232)
- Exclude Xen kernels from everything install (#151490)
- Add reserve_size for ppc to leave room on disc1 (#151234)
- Add some more locales 

* Mon Mar 14 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.28-1
- fix swap detection on upgrade (pjones)
- don't use os.read to make a buffer of '\x00' (pjones)
- move availRaidLevels to raid.py from fsset.py (pjones)
- fix Xvnc parameters (clumens, #150498)
- unmount loopback-mounted ISO images to free loop0 (clumens, #150887)
- fix warnings about gtk.TRUE and gtk.FALSE, partly based on a patch
  from Colin Charles. (pjones)
- sqlite3->sqlite (pnasrat)
- support longer package names in hdlist (pnasrat, #146820)
- Fix handling of --debug (Ingo Pakleppa, #150920, #150925)
- Fix for font location changes (#150889)
- More cjk text shuffling (#149039)

* Mon Mar  7 2005 Peter Jones <pjones@redhat.com> - 10.2.0.27-1
- supress lvm fd warning messages
- fewer log messages when growing partitions
- clamp LVs to pesize during grow

* Mon Mar  7 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.26-1
- urlgrabber stuff is in its own package now

* Sun Mar  6 2005 Peter Jones <pjones@redhat.com> - 10.2.0.25-1
- Empty blacklist in upgrade.py (notting, #142893)
- Add new font package names (katzj)
- Yet another fix of autopart with lvm (pjones)

* Tue Mar  1 2005 Peter Jones <pjones@redhat.com> - 10.2.0.24-1
- gcc4 fixes (clumens, pjones)
- build C files with -D_FORTIFY_SOURCE=2 (pjones)

* Mon Feb 28 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.23-1 
- Don't write out filesystems to fstab we haven't mounted (katzj, #149091).
- Deal with multiple Apple Bootstrap partitions (pnasrat).
- Set hostname sensitivity UI bug.
- Eject CD when failing (pnasrat, #147272).
- Better handling of Apple Bootstrap throughout (pjones).
- Do ethtool setup everywhere (pnasrat, #145522).
- Fix "debug" command line arg (pjones).
- Import new libkrb5support library (#149856).
- Add -once to ensure Xvnc exits (katzj, #137337).

* Sun Feb 20 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.22-1
- revert some of the ppc changes so that lvm is used (nasrat)
- Try to fix bogl stuff some more (#149039)
- x86_64 install fixes (#149040)

* Sun Feb 20 2005 Peter Jones <pjones@redhat.com> - 10.2.0.21-1
- get rid of lilo
- make grub work with raid1 /boot and /root

* Sat Feb 19 2005 Paul Nasrat <pnasrat@redhat.com> - 10.2.0.20-1
- Pull in translations
- s390 linuxrc silence nonexistant group warnings (karsten)
- ppc mac autopartitioning and G5 boot.iso (#121266) and (#149081)

* Sat Feb 12 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.19-1
- fix x86_64 installs for bad urlgrabber import
- Fix traceback with no %post (clumens)
- Put hostname in the text entry (clumens, #132826)

* Tue Feb  8 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.18-1
- Remove some old cruft
- Fix-up for new module naming in gnome-python2-canvas 2.9.x 
- Add needed requirements for rpm 4.4
- Fix segfault when rpm tries to write to non-existent fd during 
  transaction ordering
- Support --erroronfail as an option for %pre/%post (clumens, #124386)

* Tue Feb  8 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.17-1
- Use rhpl.archscore to fix iseries upgrades (pnasrat, #146915)
- Only configure ksdevice if no --device (pnasrat, #138852)
- Don't redraw help if disasbled on next button click (clumens, #145691)
- Fix exception in exception handler (msw)
- Rebuild for new librpm

* Fri Feb  4 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.16-1
- Support setting fs options in kickstart via --fsoptions  (#97560)
- Fix tracebacks

* Wed Feb  2 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.15-1
- Fix some bugs in the reduce-font changes
- Fix urlgrabber import
- Remove langsupport screen, base additional language support off of groups 
  selected

* Wed Feb  2 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.14-1
- Fix deprecation warnings for pygtk 2.5 (clumens)
- Fix bootloader --location=none (clumens, #146448)
- Use urlgrabber (clumens)
- Create reduced bogl font at upd-instroot time to include more 
  characters (#92146, #140208)
- Allow passing --src-discs=0 to get no srpm discs from splittree 
  (based on patch from Armijn Hemel, #119070)
- Mount pseudo-fs's with a more descriptive device name (#136820)
- Minor tweaks to completion message (#138688)

* Tue Jan 25 2005 Peter Jones <pjones@redhat.com> - 10.2.0.13-1
- Hopefully fix LVM size bug (#145183)
- Support multiple iso sets in the same directory (#146053)

* Wed Jan 19 2005 Chris Lumens <clumens@redhat.com> - 10.2.0.12-1 
- Fix partitioning bugs (#101432, #137119)
- Support --bytes-per-inode on a per-partition basis (#57550)

* Thu Jan 13 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.11-1
- Fix some tracebacks with the new glade code
- Use busybox ash instead of ash for netstg2.img/hdstg2.img
- Initialize terminals to avoid color palette change from 
  bterm (pjones, #137849)

* Thu Jan 13 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.10-1
- Handle /sbin/lvm not existing anymore
- Allow installclasses to turn off showing the upgrade option
- Ensure that Core exists in your comps file (#143930)
- Don't fall back to text mode if we fail to start graphics in test mode
- Display better error messages for HTTP/FTP errors (clumens, #144546)
- Switch main UI to use glade, set up infrastructure for use of glade
- Remove some old code
- Add buildprereq for intltool (fixed for b.g.o 163981)

* Wed Jan  5 2005 Jeremy Katz <katzj@redhat.com> - 10.2.0.9-1
- Fix some typos (#143257, #144006)
- Fix from Matthew Miller for multiple dns servers (#84409)
- Fix formatting of fcp disks (#144199)
- Include a README for x86_64 images (clumens, #143366)
- Make an x86_64 rescue image (clumens, #143366)
- Add libXfixes for new gtk2

* Thu Dec 23 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.8-1
- Use tmpfs not ramfs for /dev
- Blacklist "root" as a VG name (#142785)
- Better error message if swap can't be mounted (clumens, #143000)
- Some fixes to the new /dev handling in init
- Make more certain hwaddr gets written out (#143535)
- Handle new swap label format (#143447)
- Let the user know they're in rescue mode earlier (clumens, #136171)

* Mon Dec 20 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.7-1
- Better error handling on device creation (#142273)
- Reset package selection to defaults if selected (#142415)
- LVM on RAID1 fix (nasrat, #141781)
- Add support for biosdev in driverdisk from Rez Kabir (#142738)
- Some more SX8 fixes
- Create /dev as a tmpfs (#141570)
- Remove some old code
- Improve quoting of fstype in anaconda-ks.cfg (Danen Brücker)

* Wed Dec  8 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.6-1
- Write out wepkey better (#140645)
- Try to skip source isos with nfsiso (#106017)
- Don't traceback for bad/missing / in fstab (nasrat, #141174)
- Include pesize in generated ks.cfg (#141370)
- Loop less on shutdown
- Better handling of partial volume groups (#139058)

* Tue Nov 30 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.5-1
- CTCPROT fix (karsten, #133088)
- Fix LVM partitions becoming negative sized (nasrat, #141268)
- Fix removal/editing of zfcp devices in gui (#140559)
- Fix segfault (#140541, #140876)
- Fix handling of pre-existing parts on disks that we then ignore (#131333)

* Tue Nov 23 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.4-1
- Update python version in urllib hack
- /init in initramfs instead of /linuxrc
- Improved ppc console detection (nasrat, #134397)
- Better handling of going back when out of space (#133773)
- Better handling of LVM failures (#134263)
- Set a default when boot loader to upgrade is indeterminate (#139603)
- No more diet on i386

* Tue Nov 16 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.3-1
- Create initramfs images instead of initrds for boot media
- Remove some old code in a few places
- Allow passing --notksdevice in network lines of a ks.cfg to avoid 
  confusion with multiple network lines and a ksdevice= (#136903)
- Allow going back to change the network device if ksdevice= is 
  passed and isn't correct (#136903)
- Fix for console= to automatically imply serial as needed (#137971)

* Mon Nov 15 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.2-1
- Do some more unmounts if we run out of space (#133773)
- Fix for obsoletes E being long (nasrat, #138485)
- Make serial imply nofb (#134167)
- Set fstype to vfat if user selected /boot/efi in the 
  mountpoint dropdown (#138580)
- Copy the X log to the installed system
- Add fix from HJ Lu to fix hang with no bootloader install (#138932)
- Fix splittree error msg (nasrat, #139391)
- Ignore IBM *STMF disks (#137920)

* Mon Nov  8 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.1-1
- whrandom is deprecated in python 2.4, use random instead
- fix some syntax errors
- fallback to English for languages that can't do text-mode (#138308)
- More CTCPROT/PORTNAME tweaks (karsten)

* Sun Nov  7 2004 Jeremy Katz <katzj@redhat.com> - 10.2.0.0-1
- Switch to python 2.4
- Clean up warning on network screen from pygtk
- Parse pxelinux IPAPPEND for loader network info, patch 
  from Bastien Nocera (#134054)
- Clean up handling of binaries busybox should override
- Do misc package selection earlier so we know all the CDs needed 
  when confirming the install (#122017)
- Mark some strings for translation (#137197)
- Don't reference boot disks in boot loader screen (#135851)
- Add hardware address information to network screen (#131814)
- Fix exception handling in label reading

* Thu Nov  4 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.4-1
- Fix traceback with CJK upgrades (#137345)
- Allow 128 bit WEP keys (#137447)
- Fix race condition with X client startup (krh, #108777)
- Fix segfault in hd kickstart install (twaugh, #137533)
- Better handling of errors reading labels (#137846)
- Try harder to find LCS interface names (karsten)
- Improve CTCPROT handling (karsten)
- Fix traceback going back in rescue mode network config (#137844)
- Don't use busybox shutdown, poweroff, reboot (#137948)
- Set permissions on anaconda logs
- Make autopartioning better with native storage on legacy iSeries
- Sync onboot behavior of gui/text network screens (#138011)
- Load some drivers later to try to avoid having FC disks be sda
- Sizes in ks.cfg need to be an integer (#138109)

* Tue Oct 26 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.3-1
- Pull in firefox on upgrade if mozilla/netscape were installed (#137244)
- Fix s390 tracebacks (#130123, #137239)

* Tue Oct 26 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.2-1
- Handle our LVM autopart lines slightly better (#137120)
- Use busybox sleep for s390 since sleep requires librt again (#131167)
- Handle onboot in ks.cfg properly in the loader (#136903)
- Punjabi shouldn't try to do text mode (#137030)
- Add sgiioc4 driver for Altix CD installs (#136730)
- pci.ids trimming (notting)

* Wed Oct 20 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.1-1
- Create a netboot.img again for ppc64 (#125129)

* Wed Oct 20 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.0-1
- Lowercase OSA addresses from the parm file too (karsten)

* Tue Oct 19 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.21-1
- Lowercase OSA addresses to make the kernel happy (#133190)
- Don't hard code the VG name used for auto-partitioning to avoid 
  colliding with existing ones
- Make sure that we don't do runlevel 5 if people don't have X, etc 
  installed (#135895)
- Update for new Indic font filenames

* Mon Oct 18 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.20-1
- Fix traceback with %post logging (Gijs Hollestelle, #136154)
- When using a local stage2.img for FTP/HTTP install, give an error earlier 
  if you point at an invalid tree (#135603, #117155, #120101)
- Add a trailing newline to /etc/sysconfig/kernel
- Try to fix the icon theme
- Rebuild against new dietlibc, hopefully fixes CJK text installs

* Sun Oct 17 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.19-1
- Fix font size to fit on disk display better (#135731)
- Write out part lines for autopart lvm correctly (#135714)
- Remove empty row in drive order for boot loader (#135944)
- Replace % in URLs to avoid format string weirdness (#135929)
- Bind mount /dev for rescue mode (#135860)
- Fix Dutch and Danish keyboard defaults (#135839)
- add s2io 10GbE driver

* Thu Oct 14 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.18-1
- Add fonts for ta, gu, bn, hi, pa (#119283)
- Re-enable bterm for testing (#113910)
- Fix segfault when using biospart with a ks hdinstall.  Patch from 
  Rez Kabir (#135609)
- Write out /etc/sysconfig/kernel for use with new-kernel-pkg changes (#135161)
- Fix telnet logins for s390 (karsten)
- Hardcode LCS as eth instead of tr (karsten)

* Tue Oct 12 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.17-1
- Only use "our" LVM partitions with auto-partitioning (#135440)
- Remove localboot option from syslinux.cfg for diskboot.img (#135263)
- Handle the great input method switch on upgrade (#129218)
- Don't save the hwaddr for qeth (#135023)
- Add rhgb boot loader arguments in postinstall (msw)
- Reverse Norwegian blacklisting (#129453) (notting)
- Add sata_nv, sata_sx4, ixgb, ahci, sx8 modules to the initrd (notting)

* Thu Oct  7 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.16-1
- s390/s390x: Fix traceback with unpartitioned disks (karsten)
- improve fit of bengali network screen (#134762)
- don't allow formatting of a pre-existing partition without also 
  mounting it (#134865)
- Don't show "0" as a mountpoint for an LV that's not being mounted (#134867)
- Add prelink config bits (#117867)
- Sort packages in text package group details (#123437)
- Don't traceback on upgrade if /dev/mapper/control exists (#124092)

* Tue Oct  5 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.15-1
- Fix creation of scsi device nodes (#134709)
- Fix multiple kickstart scriptlets with different interpreters (#134707)

* Mon Oct  4 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.14-1
- Some zfcp fixes
- Don't traceback if we have a %%include inside a scriptlet (#120252)
- Fix SELinux for text-mode ftp/http installs (#134549)

* Mon Oct  4 2004 Mike McLean <mikem@redhat.com> - 10.0.3.12-1
- add command line options to pkgorder (mikem)

* Mon Oct  4 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.11-1
- Handle 32 raid devs (#134438)
- Fix LCS PORTNAME (#134487)
- Add logging of kickstart scripts with --log to %post/%pre
- Copy /tmp/anaconda.log and /tmp/syslog to /var/log/anaconda.log 
  and /var/log/anaconda.syslog respectively (#124370)
- Fix Polish (#134554)
- Add arch-specific package removal (#133396)
- Include PPC PReP Boot partition in anaconda-ks.cfg (#133934)
- Fix changing of VG name going through to boot loader setup (#132213)
- Add support for > 128 SCSI disks (#134575)

* Fri Oct  1 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.10-1
- add kickstart zfcp configuration (#133288, #130070)
- Use NFSv3 for NFS installs.  Fixes NFSISO installs from DVD (#122032)
- Fix megaraid_mbox module name (#134369)
- Another uninitialized fix (#133996)
- Add the zh_CN font (#133330)

* Thu Sep 30 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.9-1
- translation updates
- Install compat-arch-support by default (#133514)
- Warn if an older version is chosen for upgrading if product is RHEL (#134523)
- Fix traceback on upgrade with possible lvm1 (#134258)
- Make changing the DNS server work (#122554)
- More fixes from pnasrat for arch handling on upgrade

* Thu Sep 30 2004 Paul Nasrat <pnasrat@redhat.com> - 10.0.3.8-1
- Fix missing rpm.ts (#133045)

* Wed Sep 29 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.7-1
- Don't ask about mouse type on remote X display (#133902)
- Label swap filesystems (#127892)
- Fix possible crash on hd kickstart installs (#133996)
- Improve multiarch upgrade (#133045)
- Avoid changing the default language when selecting additional 
  language support (#134040)
- Remove spurious blank option in upgrade combo (#134058)
- Fix driver disk hang (#131112, #122952)
- Fix detection of unformatted dasd (#130123)

* Mon Sep 27 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.6-1
- Fix traceback from auto-partitioning if you don't have enough space (#131325)
- Update FCP config for adding SCSI LUNs (#133290)

* Mon Sep 27 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.5-1
- Fix driver disk segfault when using a partition (#133036)
- Let driver disk images on ext2 partitions work
- Fix nonet/nostorage
- Allow name.arch syntax in ks.cfg (#124456)
- Fix traceback unselecting last language (#133164)
- Skip version 0 swap (#122101)
- Handle /dev being present in device names of ks.cfg (#121486)
- Use no instead of no-latin1 for Norwegian keyboard (#133757)
- include other dm modules (#132001)

* Fri Sep 24 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.4-1
- fix megaraid module name (notting)
- don't prompt for a driver disk on pSeries boxes with just 
  virtual devices (#135292)
- don't use PROBE_LOADED for cd probe (#131033)
- i2o devices don't use a "p" separator (#133379)
- switch back zh_CN font to default (#133330)
- add 3w-9xxx to modules.cgz (#133525)
- fix showing of freespace (#133425)

* Wed Sep 22 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.3-1
- fix going back unmount of /dev/pts (#133301)
- fix SRPMs disc (#122737)
- add localboot option to isolinux.cfg (#120687)
- fix tree build on ia64 and x86_64
- fix a syntax error for text mode selinux config 

* Tue Sep 21 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.2-1
- some fixes for Arabic (#122228)
- support using ksdevice=macaddr (#130605)
- add an images/pxeboot directory on ia64

* Tue Sep 21 2004 Jeremy Katz <katzj@redhat.com> - 10.0.3.1-1
- improve handling of non-physical consoles on some ppc and ia64 machines
- add Bengali(India) and Gujarati to the lang-table (#126108)
- add support for setting the CTC protocol on s/390 (#132324, #132325)
- don't offer to do vnc if we don't have active nwtorking (#132833)
- various typo/grammar fixes
- add support for 'nostorage' and 'nonet' command line options to avoid 
  auto-loading just network or storage devices
- fix editing of pre-existing lvm (#132217)
- fix going back from the partitions list on a driver disk (#132096)
- don't show login error if silent errors (#132673)

* Thu Jun  3 2004 Jeremy Katz <katzj@redhat.com>
- require system-logos and anaconda-help, obsolete anaconda-images

* Fri Apr 30 2004 Jeremy Katz <katzj@redhat.com>
- Update description, remove prereq on stuff that was only needed 
  for reconfig mode 

* Tue Feb 24 2004 Jeremy Katz <katzj@redhat.com>
- buildrequire libselinux-devel

* Thu Nov  6 2003 Jeremy Katz <katzj@redhat.com>
- require booty (#109272)

* Tue Oct  8 2002 Jeremy Katz <katzj@redhat.com>
- back to mainstream rpm instead of rpm404

* Mon Sep  9 2002 Jeremy Katz <katzj@redhat.com>
- can't buildrequire dietlibc and kernel-pcmcia-cs since they don't always
  exist

* Wed Aug 21 2002 Jeremy Katz <katzj@redhat.com>
- added URL

* Thu May 23 2002 Jeremy Katz <katzj@redhat.com>
- add require and buildrequire on rhpl

* Tue Apr 02 2002 Michael Fulbright <msf@redhat.com>
- added some more docs

* Fri Feb 22 2002 Jeremy Katz <katzj@redhat.com>
- buildrequire kernel-pcmcia-cs as we've sucked the libs the loader needs 
  to there now

* Thu Feb 07 2002 Michael Fulbright <msf@redhat.com>
- goodbye reconfig

* Thu Jan 31 2002 Jeremy Katz <katzj@redhat.com>
- update the BuildRequires a bit

* Fri Jan  4 2002 Jeremy Katz <katzj@redhat.com>
- ddcprobe is now done from kudzu

* Wed Jul 18 2001 Jeremy Katz <katzj@redhat.com>
- own /usr/lib/anaconda and /usr/share/anaconda

* Fri Jan 12 2001 Matt Wilson <msw@redhat.com>
- sync text with specspo

* Thu Aug 10 2000 Matt Wilson <msw@redhat.com>
- build on alpha again now that I've fixed the stubs

* Wed Aug  9 2000 Michael Fulbright <drmike@redhat.com>
- new build

* Fri Aug  4 2000 Florian La Roche <Florian.LaRoche@redhat.com>
- allow also subvendorid and subdeviceid in trimpcitable

* Fri Jul 14 2000 Matt Wilson <msw@redhat.com>
- moved init script for reconfig mode to /etc/init.d/reconfig
- move the initscript back to /etc/rc.d/init.d
- Prereq: /etc/init.d

* Thu Feb 03 2000 Michael Fulbright <drmike@redhat.com>
- strip files
- add lang-table to file list

* Wed Jan 05 2000 Michael Fulbright <drmike@redhat.com>
- added requirement for rpm-python

* Mon Dec 06 1999 Michael Fulbright <drmike@redhat.com>
- rename to 'anaconda' instead of 'anaconda-reconfig'

* Fri Dec 03 1999 Michael Fulbright <drmike@redhat.com>
- remove ddcprobe since we don't do X configuration in reconfig now

* Tue Nov 30 1999 Michael Fulbright <drmike@redhat.com>
- first try at packaging reconfiguration tool

