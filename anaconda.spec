Name: anaconda
Version: 10.2.0.29
Release: 1
License: GPL
Summary: Graphical system installer
Group: Applications/System
Source: anaconda-%{PACKAGE_VERSION}.tar.bz2
BuildPreReq: pump-devel >= 0.8.20, kudzu-devel >= 1.1.52, pciutils-devel, bzip2-devel, e2fsprogs-devel, python-devel gtk2-devel rpm-python >= 4.2-0.61, newt-devel, rpm-devel, gettext >= 0.11, rhpl, booty, libxml2-python, zlib-devel, bogl-devel >= 0:0.1.9-17, bogl-bterm >= 0:0.1.9-17, elfutils-devel, beecrypt-devel, libselinux-devel >= 1.6, xorg-x11-devel, intltool >= 0.31.2-3, python-urlgrabber
Requires: rpm-python >= 4.2-0.61, rhpl > 0.63, parted >= 1.6.3-7, booty, kudzu
Requires: pyparted, libxml2-python, python-urlgrabber
Requires: anaconda-help, system-logos
Obsoletes: anaconda-images <= 10
Url: http://fedora.redhat.com/projects/anaconda-installer/

BuildRoot: %{_tmppath}/anaconda-%{PACKAGE_VERSION}

%description
The anaconda package contains the program which was used to install your 
system.  These files are of little use on an already installed system.

%package runtime
Summary: Graphical system installer portions needed only for fresh installs.
Group: Applications/System
AutoReqProv: false
Requires: libxml2-python, python, rpm-python >= 4.2-0.61

%description runtime
The anaconda-runtime package contains parts of the installation system which 
are needed for installing new systems.  These files are used to build media 
sets, but are not meant for use on already installed systems.

%prep

%setup -q

%build
make depend
make RPM_OPT_FLAGS="$RPM_OPT_FLAGS"

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install
#strip $RPM_BUILD_ROOT/usr/sbin/ddcprobe

strip $RPM_BUILD_ROOT/usr/lib/anaconda/*.so

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%doc COPYING
%doc docs/command-line.txt
%doc docs/install-methods.txt
%doc docs/kickstart-docs.txt
%doc docs/mediacheck.txt
%doc docs/anaconda-release-notes.txt
/usr/bin/mini-wm
/usr/sbin/anaconda
/usr/share/anaconda
/usr/share/locale/*/*/*
/usr/lib/anaconda

%files runtime
%defattr(-,root,root)
/usr/lib/anaconda-runtime

%triggerun -- anaconda < 8.0-1
/sbin/chkconfig --del reconfig >/dev/null 2>&1 || :

%changelog
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

* Wed Jan 19 2005 Chris Lumens <clumens@redhat.com> 10.2.0.12-1 
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

