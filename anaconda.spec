ExcludeArch: ppc64
Name: anaconda
Version: 10.1.1.104
Release: 1
License: GPL
Summary: Graphical system installer
Group: Applications/System
Source: anaconda-%{PACKAGE_VERSION}.tar.bz2
BuildPreReq: pump-devel >= 0.8.20, kudzu-devel >= 1.1.95.26, pciutils-devel, bzip2-devel, e2fsprogs-devel, python-devel gtk2-devel rpm-python >= 4.2-0.61, newt-devel, rpm-devel, gettext >= 0.11, rhpl, booty, libxml2-python, zlib-devel, bogl-devel >= 0:0.1.9-17, bogl-bterm >= 0:0.1.9-17, elfutils-devel, beecrypt-devel, libselinux-devel >= 1.6, xorg-x11-devel
%ifarch i386
BuildRequires: dietlibc
%endif
Requires: rpm-python >= 4.2-0.61, rhpl > 0.63, parted >= 1.6.19-23, booty, kudzu
Requires: pyparted, libxml2-python, dosfstools >= 2.8-17
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

rm -f $RPM_BUILD_ROOT/usr/lib/anaconda-runtime/keymaps-override-s390x
rm -f $RPM_BUILD_ROOT/usr/lib/anaconda-runtime/keymaps-override-s390

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%doc COPYING
%doc docs/command-line.txt
%doc docs/install-methods.txt
%doc docs/kickstart-docs.txt
%doc docs/kickstart-docs.html
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
* Tue Oct 26 2010 David Cantrell <dcantrell@redhat.com> - 10.1.1.104-1
- Initialize __libc_setlocale_lock (dcantrell)
  Related: rhbz#523380

* Tue Mar 31 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.103-1
- libwrap is now located in /LIBDIR/libwrap (msivak).
  Resolves: rhbz:#493005

* Thu Mar 26 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.102-1
- Fix the size of the vmlinuz images for i386 and ia64 (msivak).
  Resolves: rhbz:#492331

* Wed Mar 25 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.101-1
- Add the qla2500 to the table of known modules (msivak).
  Resolves: rhbz:#491982

* Wed Mar 11 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.100-1
- Fix clamping of VG size in case when it is not sufficient for lvm metadata (rvykydal).
  Resolves: rhbz:#489549

* Wed Mar 4 2009 Joel Granados <jgranados@redhat.com> - 10.1.1.99-1
- We have to first refresh the devices and _then_ set the protected list (msivak).
  Resolves: rhbz:#461855

* Thu Feb 26 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.98-1
- LVM VG size is not same as the device where PV is (jgranado).
  Patch in partRequest.py instead of autopart.py.
  Resolves: rhbz:#480793

* Mon Feb 23 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.97-1
- LVM VG size is not same as the device where PV is (jgranado).
  Resolves: rhbz:#480793

* Wed Feb 4 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.96-1
- Don't show the root password dialog, make patch work better (msivak).
  Resolves: rhbz:#481597
- Clamp the lv size on LV device creation (jgranados).
  Resolves: rhbz:#480793

* Fri Jan 30 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.95-1
- Avoid devices where the lvm metadata is not present (jgranado).
  Resolves: rhbz:#481698
- Don't show the root password dialog, password was provided by ks file (msivak).
  Resolves: rhbz:#481597

* Tue Jan 27 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.94-1
- Remove missing PVs before removing obsolete VG (jgranado).
  Resolves: rhbz:#481698

* Mon Jan 26 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.93-1
- Correct backport from RHEL5 (jgranados).
  Resolves: rhbz:#480793

* Thu Jan 15 2009 Joel Granados <jgranado@redhat.com> - 10.1.1.92-1
- Flush the drive dict first so CD-ROM device nodes get made (clumens).
  Resolves: rhbz:#435926
- Protect installation source partition from deletion (msivak).
  Resolves: rhbz:#461855
- Allow bootloader on mbr when /boot is dmraid1 (hdegoede).
  Resolves: rhbz:#217176
- Allow empty DNS variable in s390 CMS conf file (dcantrell).
  Resolves: rhbz:#465175
- Write /etc/resolv.conf and /etc/hosts in stage1 on s390 (dcantrell).
  Resolves: rhbz:#459730
- docs update for driveorder ks command (msivak).
  Resolves: rhbz:#430476
- Fix detection of xen environment for kbd setting (rvykydal).
  Resolves: rhbz:#459785
- Fix clamping of size of lvm physical volumes (backport) (rvykydal).
  Resolves: rhbz:#233050
- Add virtio support (clalance).
  Related: rhbz:#479134,446215
- Do a check in lvm grow to catch negative sizes (jgranado).
  Related: rhbz:#144676

* Tue Jul 08 2008 Peter Jones <pjones@redhat.com> - 10.1.1.91-1
- Add initrd.size to the generic.ins files on s390.  (I think this should
  solve #454492 , and indicates that the verification of #449617 was an error.)
  Related: rhbz#454492

* Wed Jun 25 2008 Peter Jones <pjones@redhat.com> - 10.1.1.90-1
- Add support for automatically determining the initramfs size on s390x
  Resolves: rhbz#449617

* Mon May 05 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.89-1
- Fix field separator spec in awk commands in linuxrc.s390 (jgranado)
  Resolves: rhbz#444674
- Fix IPv6 address verification functions in linuxrc.s390 (jgranado)
  Resolves: rhbz#362411
- Revert previous change to notify NFS server when we finish install (jgranado)
  Related: rhbz#208103

* Thu Apr 24 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.88-1
- Increase ia64 initrd image size (jgranado)
  Resolves: rhbz#443373
- Specify mode when running mdadm
  Resolves: rhbz#443844

* Tue Apr 22 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.87-1
- Fix traceback trying to access non-existent anaconda instance
  Resolves: rhbz#443412

* Fri Apr 18 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.86-1
- Fix dispatch traceback (msivak)
  Resolves: rhbz#442750
- Fix loader crash from freeing static bufer (clumens)
  Resolves: rhbz#442863

* Tue Apr 15 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.85-1
- Fix detection of xen para-virt environment (msivak)
  Resolves: rhbz#441729
- Add bnx2x driver
  Resolves: rhbz#442563
- Add myri10ge driver
  Resolves: rhbz#442545

* Mon Apr 14 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.84-1
- Tell the nfs server when we unmount the nfs mountpoints (jgranado)
  Resolves: rhbz#208103
- Fix logic in patch for protecting hard drive install source (msivak)
  Related: rhbz#220161
- Remove defunct VG before creating a new one of the same name
  Resolves: rhbz#257161
- Use the search path when running mdadm
  Related: rhbz#185674
- Support SHA256/SHA512 password encoding from kickstart
  Resolves: rhbz#427384

* Fri Mar 28 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.83-1
- Fix a typo in the dhcptimeout patch
  Related: rhbz#246483
- Fix various problems with the no-duplicate-hostadapters patch
  Related: rhbz#248619

* Thu Mar 27 2008 Dave Lehman <dlehman@redhat.com> - 10.1.1.82-1
- Add dhcptimeout parameter to loader (msivak)
  Resolves: rhbz#246483
- Fix swap size recommendation to match manuals (msivak)
  Resolves: rhbz#339001
- Add ixgbe module
  Resolves: rhbz#350921
- Fix segfault with driver disk image in initrd
  Resolves: rhbz#249241
- Avoid duplicate scsi_hostadapter lines in modprobe.conf
  Resolves: rhbz#248619
- Prevent modification to partitions containing harddrive install media (msivak)
  Resolves: rhbz#220161
- Use mdadm to generate mdadm.conf (jgranado)
  Resolves: rhbz#185674
- Add IP address validation routines for s390 (jgranado)
  Resolves: rhbz#362411
- Close RAID devices after collecting device labels (jgranado)
  Resolves: rhbz#434949

* Tue Oct 30 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.81-1
- Copy loaderData->macaddr in to cfg->macaddr
  Related: rhbz#233357

* Mon Oct 29 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.80-1
- Copy in usr/sbin/ip for the s390 & s390x initrd.img files
  Related: rhbz#233357

* Fri Oct 26 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.79-1
- Make e100e description in module-info unique (pjones)
  Related: rhbz#253791

* Tue Oct 23 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.78-1
- Add sbin/ip to KEEPFILE list on s390 & s390x
  Related: rhbz#233357

* Wed Oct 10 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.77-1
- Add /sbin/ip command to the initrd.img file on s390 & s390x
  Related: rhbz#233357

* Wed Oct 10 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.76-1
- ChangeLog corrections caught by rpmdiff
  Related: rhbz#234134

* Tue Oct 09 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.75-1
- use /sbin/ip in init to set the MAC address on s390/s390x (bhinson)
  Resolves: rhbz#233357

* Tue Oct 09 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.74-1
- add qla4xxx driver
  Resolves: rhbz#234134

* Tue Sep 25 2007 Dave Lehman <dlehman@redhat.com> - 10.1.1.73-1
- look for labels on all fstypes
  Resolves: rhbz#251579
- add e1000e driver (pjones)
  Resolves: rhbz#253791

* Mon Sep 17 2007 Dave Lehman <dlehman@redhat.com> - 10.1.1.72-1
- fix handling of MACADDR when configuring OSA layer2 networking (dcantrell)
- Related: rhbz#233357

* Tue Sep 11 2007 Peter Jones <pjones@redhat.com> - 10.1.1.71-2
- rebuild with COLLECTION=dist-4E-U6-candidate to pick up newer kudzu.

* Thu Sep 06 2007 Chris Lumens <clumens@redhat.com> - 10.1.1.71-1
- Fix raid --useexisting.
  Resolves: rhbz#207541.

* Mon Sep 04 2007 Dave Lehman <dlehman@redhat.com> - 10.1.1.70-1
- Increase the size of x86_64 diskboot.img so everything fits (pjones)
  Resolves: rhbz#240561
- Fix MAC address specification with OSA layer2 networking, based on patch 
  from Brad Hinson (dcantrell)
  Resolves: rhbz#252021
- Fix biosdisk install problems on certain hardware (dcantrell)
  Resolves: rhbz#247303
- Enable igb network devices (dcantrell)
  Resolves: rhbz#253711

* Mon Aug 13 2007 Peter Jones <pjones@redhat.com> - 10.1.1.69-1
- Fix py-compile failure introduced in .68-1 .

* Fri Aug 10 2007 Peter Jones <pjones@redhat.com> - 10.1.1.68-1
- Add missing pata_* and sata_* HBA drivers
  Resolves: rhbz#251718
- Fix UI for drive selection for partitioning (clumens)
  Resolves: rhbz#251150

* Thu Aug 02 2007 David Cantrell <dcantrell@redhat.com> - 10.1.1.67-1
- Handle return value from waitLinkSleep() correctly (pjones)
  Related: rhbz#207546
- Only show >15 partitions message if there is a user interface (dlehman)
  Related: rhbz#238708

* Fri Jul 13 2007 Chris Lumens <clumens@redhat.com> - 10.1.1.66-1
- Don't read filesystem labels from drives we cleared with clearpart.
  Resolves: #209291
- Don't display an error if mount fails when searching for a root (dlehman).
  Resolves: #214008
- Check for SCSI disks containing more than 15 partitions (dlehman).
  Resoles: #238708
- Fix PATH assignment in linuxrc.s390 (dlehman).
  Resolves: #190215
- Add netxen_nic support (dlehman).
  Resolves: #233639
- Add ignoredisk --only-use option.
  Resolves: #198526
- Document nfsmountopts command line option.
  Resolves: #234185

* Wed Jun 20 2007 Chris Lumens <clumens@redhat.com> - 10.1.1.65-1
- Support FTP and HTTP URLs with auth info (dcantrell).
  Resolves: #194247
- Increase DHCP timeout to 45 seconds and retries to 10 (dcantrell).
  Resolves: #207546
- Remove invalid preexisting RAID requests.
  Resolves: #233308
- Don't traceback on keeping preexisting partitions and logical volumes.
  Resolves: #182943
- Fix probing for RAID superblocks.
  Resolves: #172648
- Document the nicdelay command line option.
  Resolves: #232721
- Change the cciss module description.
  Resolves: #210414
- Add support for qla3xxx and the Areca RAID adapter.
  Resolves: #233672, #242113
- Support OSA Layer 2 networking (bhinson).
  Resolves: #233357
- Merge in the following changelog entries from devel-cvs spec file:
- Ignore disks listed in ignoredisks, even if we have clearpart --all (pjones)
  Resolves: #186438
- Label fat filesystems on ia64 during upgrade (pjones)
  Resolves: #234815

* Wed Apr 14 2007 Dave Lehman <dlehman@redhat.com> - 10.1.1.64-1
- Fix rescue mode selinuxfs mount
- Add stex driver to module-info
- Add OSA layer 2 network support for zSeries (dcantrell)
  Resolves: #233357
- Add size and model info to text mode drive selection (dcantrell)
  Resolves: #233606
- Honor nicdelay when ksdevice=link is used (dcantrell)
  Resolves: #207546
- Actually create the /bin/echo symlink on all arches
- Detect FBA storage devices on zSeries

* Fri Apr 13 2007 Peter Jones <pjones@redhat.com> - 10.1.1.63-4
- Ignore disks listed in ignoredisks, even if we have clearpart --all
  Resolves: #186438

* Mon Apr 09 2007 Peter Jones <pjones@redhat.com> - 10.1.1.63-3
- Label fat filesystems on ia64 during upgrade
  Resolves: #234815

* Wed Apr 04 2007 Dave Lehman <dlehman@redhat.com> - 10.1.1.63-2
- Fix rescue mode selinuxfs mount (#234137)
- Add stex driver to module-info (#230214)

* Tue Mar 06 2007 Dave Lehman <dlehman@redhat.com> - 10.1.1.63-1
- Allow graphical xen installs to proceed with no mouse
  Resolves: #229588
- Add qla2400 to the list of drivers that get loaded later than ipr
  Resolves: #230644
- Add support for IBM HEA devices
  Resolves: #225451

* Fri Feb 16 2007 Peter Jones <pjones@redhat.com> - 10.1.1.62-1
- Update the keymaps in our cache from ones generated on recent installs,
  so they won't be missing anything.
  Resolves: #229030

* Thu Feb 15 2007 Peter Jones <pjones@redhat.com> - 10.1.1.61-1
- Put the keymap for ppc with all the other keymaps, so it actually gets
  pulled in correctly.
  Related: #182325

* Fri Feb 13 2007 Peter Jones <pjones@redhat.com> - 10.1.1.60-1
- Don't use the bootLoaderInfo drivelist to determine bootloader choices
  on zFCP-only zSeries machines (dcantrell)
  Resolves: #165098

* Fri Feb  9 2007 Peter Jones <pjones@redhat.com> - 10.1.1.59-1
- Handle the kernel's new representation of unformatted DASD devices (dlehman)
  Resolves: #227546

* Tue Feb  6 2007 Peter Jones <pjones@redhat.com> - 10.1.1.58-1
- Fix installation of cached keymaps so we actually use them during
  buildinstall runs
  Resolves: #182325

* Fri Feb  2 2007 Dave Lehman <dlehman@redhat.com> - 10.1.1.57-1
- Fix handling of requests w/o drives in new usb-storage code
  Resolves: #227045

* Wed Jan 31 2007 Peter Jones <pjones@redhat.com> - 10.1.1.56-1
- Add usb-storage support for the root filesystem
  Resolves: #180550

* Tue Jan 30 2007 Peter Jones <pjones@redhat.com> - 10.1.1.55-1
- Close xvc in the loader so graphical xen works (katzj)
  Resolves: #224405
- Don't load fb modules like xencons in the loader (katzj)
  Resolves: #224200
- Make the fonts for bogl when building the instroot
  Resolves: #180113
- Fix zfcp usage in kickstart (dlehman)
  Resolves: #188610

* Tue Jan  9 2007 Peter Jones <pjones@redhat.com> - 10.1.1.54-1
- Check all CD-Roms for ks.cfg (dlehman, #203344)
- Save result from upgrade vs install UI page across forward->back movement
  (dlehman, #208053)

* Tue Nov 28 2006 Jeremy Katz <katzj@redhat.com> - 10.1.1.53-1
- Ensure we only install kernel-xenU on paravirt xen

* Mon Nov 20 2006 Jeremy Katz <katzj@redhat.com> - 10.1.1.52-1
- Fix /bin/echo symlink (dlehman, #178781)
- Add audit-libs (dlehman, #203391)
- Improve handling of local stage2 with URL installs (dlehman, #189262)
- xen fix

* Mon Oct 23 2006 Jeremy Katz <katzj@redhat.com> - 10.1.1.50-1
- fix build

* Thu Oct 19 2006 Jeremy Katz <katzj@redhat.com> - 10.1.1.48-1
- Start to support installation of paravirt Xen guests (#201613)

* Wed Oct 04 2006 David Cantrell <dcantrell@redhat.com> - 10.1.1.47-1
- ia64 detection fixes (#201397, pnasrat)
- Include lapic_status on ia64 images (#201397, pnasrat)
- VNC override text on kickstart installs (190099, clumens)
- Get stdin from the correct file descriptor (#192067, clumens)
- Mount /selinux under the chrooted system environment (#189489, clumens)
- Blacklist by arch support backport (#198545, pnasrat)
- Blacklist x86_64 multilib packages (#181742, pnasrat)
- Only try to init uninitialized zfcp devices (#200333, jwhiter)

* Wed Jun 28 2006 Peter Jones <pjones@redhat.com> - 10.1.1.46-1
- Add Marvell SATA driver to module-info (#181852)

* Tue Jun 27 2006 Peter Jones <pjones@redhat.com> - 10.1.1.45-1
- Revert bogus translation changes (#194153)
- Backport new runShell code from HEAD so rescue mode works (#193285)

* Mon Jun  5 2006 Peter Jones <pjones@redhat.com> - 10.1.1.44-2
- Don't traceback if /proc/lapics is missing (#192818)
- Fix another weird cpu counting issue on i386 HT Xeons (#193816)
- Add more mpt drivers (#194036)

* Thu May 25 2006 Peter Jones <pjones@redhat.com> - 10.1.1.43-1
- Add adp94xx to module whitelist (#193083)

* Wed May 24 2006 Peter Jones <pjones@redhat.com> - 10.1.1.42-1
- Fix lapic_status import issues (#171930)
- Fix console corruption from fprintf in #168384 .

* Tue May 23 2006 Peter Jones <pjones@redhat.com> - 10.1.1.41-1
- Fix circular import issue (#192819)

* Fri May 19 2006 Paul Nasrat <pnasrat@redhat.com> - 10.1.1.40-1
- Create lock file dir (#192383)

* Mon May  8 2006 Peter Jones <pjones@redhat.com> - 10.1.1.39-1
- Only probe ACPI on x86_64, not i386 (#171930)
- Use /proc/lapics for ACPI probing (#171930)
- Add support for nfs mount options on boot command line (#168384)
- Handle tty1 mode for rescue mode shell correctly (#126620)
- Don't put removable drives in the isys hard drive list (#147504)
- Check for missing vg declaration earlier so the error message 
  makes sense (#176989)
- Quote ethtool opts properly (#176918)
- Add selinux to kickstart doics (#175868)
- Add qla2xxx to module-info (#174993)
- Always reset terminal attributes in loader on ppc (#166302)
- Eliminate dupe vnc entries in command line docs (#175368)
- Fix RAID error messages to be more clear (#184246)

* Thu Mar  2 2006 Peter Jones <pjones@redhat.com> - 10.1.1.38-1
- Make the ACPI probe happen when isys is imported, and return cached
  data from there on out.

* Mon Feb 20 2006 Peter Jones <pjones@redhat.com> - 10.1.1.37-1
- Fix ACPI probing on amd64 (reported by pjones)
- Fix cpuid fn 0x80000008 (cores-per-package) probe on amd64 (reported by katzj)
- Fix return value reset across multiple isys.acpicpus() calls (#181612)
- Fix variable name in smp acpi test (#181612)
- Don't count disabled cpus (empty socket or disabled in bios) towards largesmp
  detection (#181612)

* Fri Feb 17 2006 Peter Jones <pjones@redhat.com> - 10.1.1.36-1
- Use ACPI for cpu probing where an MADT is available.

* Thu Feb 16 2006 Peter Jones <pjones@redhat.com> - 10.1.1.35-1
- probe threads per core and device threads per cpu by that to get a 
  real number

* Thu Jan 26 2006 Peter Jones <pjones@redhat.com> - 10.1.1.34-1
- Change minimum cpu count for largesmp kernel selection on ppc 
  to 64.  (pjones, #179027)

* Wed Dec 21 2005 Peter Jones <pjones@redhat.com> - 10.1.1.33-2
- rebuild for fixed gcc

* Wed Dec 14 2005 Peter Jones <pjones@redhat.com> - 10.1.1.33-1
- put sk98lin back, and change description for sky2

* Wed Dec 14 2005 Peter Jones <pjones@redhat.com> - 10.1.1.32-1
- add sky2 driver to the list

* Mon Dec 12 2005 Peter Jones <pjones@redhat.com> - 10.1.1.31-1
- add -largesmp to grub config and "everything" install exclude list
  (katzj, #175548)
- handle ia32e as an arch, not just x86_64 (pjones, #175548)

* Wed Dec  7 2005 Peter Jones <pjones@redhat.com> - 10.1.1.30-1
- use the right numbers to test for largesmp
- Avoid the rpmlib segfault with ts.order (workaround for #174621)

* Tue Dec  6 2005 Peter Jones <pjones@redhat.com> - 10.1.1.29-1
- add smp/ht detection for ia64
- fix boot.img creation for ia64

* Mon Dec  5 2005 Peter Jones <pjones@redhat.com> - 10.1.1.28-1
- fix a typo that prevents smp installs
- revamp x86 HT detection to be much simpler

* Fri Dec  2 2005 Peter Jones <pjones@redhat.com> - 10.1.1.27-1
- Fix largesmp detection on x86_64 and powerpc

* Fri Dec  2 2005 Peter Jones <pjones@redhat.com> - 10.1.1.26-1
- Fix verious problems with LVM support (#145183, #161652)
- Add modules for storage devices (#167065)
- Fix NFS mounting when DNS is not in use (#168957)
- Fix s390x installation with no DASD devices (#165098)
- Fix various dialog boxes and installer text (#172030, #172588)
- Add support for ksdevice=bootif (#170713)
- Fix argument handling for kickstart sections (#170331)
- Fix handling of "noparport" option (#170333)

* Thu Sep 22 2005 Peter Jones <pjones@redhat.com> - 10.1.1.25-1
- Fix all the lvm calls similar to vg size fix, including pe size
  in vglist. (#165141)

* Tue Aug 16 2005 Peter Jones <pjones@redhat.com> - 10.1.1.24-1
- Fix the lvm call for vglist so it doesn't truncate a character
  from the vg size. (#165141)

* Mon Aug  1 2005 Jeremy Katz <katzj@redhat.com> - 10.1.1.23-1
- Get pesize for preexisting LVM (#162408)

* Fri Jul 22 2005 Paul Nasrat <pnasrat@redhat.com> - 10.1.1.22-1
- Fix text installation traceback (#163722)

* Thu Jul 21 2005 Paul Nasrat <pnasrat@redhat.com> - 10.1.1.21-1
- Include audit libraries in stage1 (#162821)

* Wed Jul 13 2005 Peter Jones <pjones@redhat.com> - 10.1.1.20-1
- Fix file descriptor leak (#160720)
- Prefer kernel-devel over kernel-smp devel (#160533, #162581)
- Support for setting MTU on command line (#155414)
- Support booting off of software raid on ppc (#159902)
- Write resolv.conf correctly when using kickstart and dhcp (#151472)
- Include audit libraries (#162821)

* Tue May 10 2005 Paul Nasrat <pnasrat@redhat.com> - 10.1.1.19-1
- Quieten package downloads in cmdline mode (#155250)
- name.arch logic error 
- Ensure kernel written to PReP on iSeries upgrades (#146915)

* Tue Apr 12 2005 Paul Nasrat <pnasrat@redhat.com> - 10.1.1.18-1
- Don't free needed string (clumens, #149871, #150844, #153072)
- Correct name.arch (#133396, #154407)
- hostname option isn't greyed out when using static IP (#149116)

* Wed Mar 23 2005 Jeremy Katz <katzj@redhat.com> - 10.1.1.17-1
- Load SElinux booleans file if it exists (#151896)

* Mon Mar 14 2005 Chris Lumens <clumens@redhat.com> - 10.1.1.16-1
- Fix typo in Xvnc parameters (#150498).

* Wed Mar  2 2005 Jeremy Katz <katzj@redhat.com> - 10.1.1.15-1
- Ensure Xvnc exits when the last client goes away (#137337)
- Allow logical partitions to go all the way to the end of an 
  extended (clumens, #101432)
- Don't install a bootloader if --location=none (clumens, #146448)

* Thu Feb 24 2005 Jeremy Katz <katzj@redhat.com> - 10.1.1.14-1
- Fix multiple DNS servers being specified on the command line.  Patch 
  from mattdm (#84409)
- Fix dhcpclass specification on the command-line (#144006)
- Fix formatting of new fcp disks (#144199)
- Support parsing pxelinux IPAPPEND (bnocera, #134054)
- Reset package selection to defaults when selected (#142415)
- More tree sanity checking instead of traceback'ing (#143930)
- Fix some partitioning corner cases (clumens, #137119, #145145)
- Fix iSeries upgrades (pnasrat, #146915)
- Fix hostname display (clumens, #132826, #149116)
- Fix mtab writing in rescue mode (#149091)
- Use ethtool settings in more places (pnasrat, #145422)

* Thu Dec 30 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.13-1
- fix typo with kernel*devel (#143257)

* Thu Dec 23 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.12-1
- improved handling for kernel*devel (#143257)
- make images look better (#143276)
- make sure hwaddr gets written (#143535)
- handle newer swap label format (#143447)

* Thu Dec 16 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.11-1
- more powerpc console fixing (nasrat, #134397)

* Tue Dec 14 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.10-1
- Add support for specifying biosdisk in the driverdisk kickstart 
  directive, patch from Rez Kabir (#142738)
- Fix LVM on RAID1 (nasrat, #141781)
- Better error handling of a few cases (#142273)
- Fixes for bits of SX8 handling

* Wed Dec  8 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.9-1
- Fix traceback with partial volume groups (#142304)

* Fri Dec  3 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.8-1
- Kill pygtk warning
- Fix writing out of wep keys (#140645)
- Skip ISOs which don't have an RPMs dir to avoid problems with src ISOs in 
  the same dir (#106017)
- Include pesize in the ks.cfg (#141370)
- Loop less on shutdown
- Improved handling of VGs that aren't completely present (#139058)
- Disable read-ahead for the last meg of the CD to try to fix mediacheck 
  problems.  Disable this behavior with "nocdhack" on the boot 
  command line. (#131051, ...)
- Turn off beta nag

* Tue Nov 30 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.7-1
- More iiimf upgrade fun (#129218)
- Disable the linuxconf removal stuff.  Has caused sporadic problems and 
  won't trigger on RHEL3 -> RHEL4 upgrades
- CTCPROT fix (karsten, #133088)
- Fix removal and editing of zfcp devices in GUI (#140559)
- Fix LVM size becoming negative (nasrat, #141268)
- Fix segfault better (#140876, #140541)
- Fix traceback with pre-existing partitions on drives which don't have a 
  partition type we let you use (#131333)

* Mon Nov 22 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.6-1
- Fix serial console magic to work with console= and not just 
  explicit serial again (#137971)
- Allow going back and manually changing the network device used even 
  if ksdevice= is passed (#136903)
- Allow passing --notksdevice on the network line to avoid using it as 
  the install dev (#136903)
- Be less aggressive about disabling LVM (#134263)
- Set a default when we can't determine boot loader (#139603)
- More fixes for going back when out of space (#133773)
- Fix ia64 loader segfault (#140093)
- Improved ppc console detection (nasrat, #134397)

* Mon Nov 15 2004 Jeremy Katz <katzj@redhat.com> - 10.1.1.5-1
- Fix exception handling reading jfs, xfs and swap labels
- Don't ask for input if PORTNAME is set (from karsten)
- Fallback to English on langs that can't do text-mode (#138308)
- Better handling of out of space (#133773)
- Fix for obsoletes E being long (nasrat, #138485)
- serial should imply nofb (#134167)
- Set fstype to vfat if user selected /boot/efi in the mountpoint dropdown (#138580)
- Copy X logs to the installed system
- Add patch from HJ Lu to fix hang if no boot loader being installed (#138932)
- Ignore IBM *STMF disks (#137920)

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

