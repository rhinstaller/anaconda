Name: anaconda
Version: 11.1.2.224
Release: 1
License: GPL
Summary: Graphical system installer
Group: Applications/System
Source: anaconda-%{version}.tar.bz2
BuildPreReq: kudzu-devel >= 1.2.57.1.26-1, pciutils-devel >= 3.1.7-3
BuildPreReq: bzip2-devel, e2fsprogs-devel, python-devel, gtk2-devel
BuildPreReq: rpm-python >= 4.2-0.61, newt-devel, rpm-devel, gettext >= 0.11
BuildPreReq: rhpl, booty, libxml2-python, zlib-devel, elfutils-devel
BuildPreReq: beecrypt-devel, libselinux-devel >= 1.6, libX11-devel
BuildPreReq: libXxf86misc-devel, intltool >= 0.31.2-3, python-urlgrabber
BuildPreReq: pykickstart >= 0.43.8, yum >= 2.9.2, device-mapper >= 1.01.05-3, 
BuildPreReq: libsepol-devel
BuildPreReq: pango-devel, pirut, libXt-devel, slang-devel >= 2.0.6-2
BuildPreReq: libdhcp-devel >= 1.20-10, mkinitrd-devel >= 5.1.2-1
BuildPreReq: audit-libs-devel, libnl-devel >= 1.0-0.10.pre5.5
BuildPreReq: libdhcp6client >= 1.0.10-17
%ifnarch s390 s390x
BuildPreReq: iscsi-initiator-utils >= 6.2.0.871-0.0
%endif
Requires: rpm-python >= 4.2-0.61, rhpl >= 0.170, booty
Requires: parted >= 1.7.1, pyparted >= 1.7.2
Requires: kudzu >= 1.2.57.1.26-1, yum >= 2.9.2, pirut >= 1.1.0
Requires: libxml2-python, python-urlgrabber
Requires: system-logos, pykickstart, system-config-date
Requires: device-mapper >= 1.01.05-3
Requires: dosfstools >= 2.11-6.2 e2fsprogs
Requires: e4fsprogs
Requires: python-pyblock >= 0.26-1
Requires: libbdevid >= 5.1.2-1, libbdevid-python
Requires: audit-libs
%ifnarch s390 s390x ppc64
Requires: rhpxl >= 0.25
%endif
Obsoletes: anaconda-images <= 10
Url: http://fedoraproject.org/wiki/Anaconda

BuildRoot: %{_tmppath}/anaconda-%{PACKAGE_VERSION}

%description
The anaconda package contains the program which was used to install your 
system.  These files are of little use on an already installed system.

%package runtime
Summary: Graphical system installer portions needed only for fresh installs.
Group: Applications/System
AutoReqProv: false
Requires: libxml2-python, python, rpm-python >= 4.2-0.61
Requires: anaconda = %{version}-%{release}
Requires: createrepo >= 0.4.3-3.1, squashfs-tools, mkisofs
%ifarch %{ix86} x86_64
Requires: syslinux
%endif
%ifarch s390 s390x
Requires: openssh
%endif
Requires: /usr/bin/strip, xorg-x11-font-utils, netpbm-progs
Requires: xml-common
Requires: libxml2
Requires(post): /usr/bin/xmlcatalog
Requires(postun): /usr/bin/xmlcatalog

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

%post runtime
CATALOG=/etc/xml/catalog
/usr/bin/xmlcatalog --noout --add "rewriteSystem" \
    "comps.dtd" \
    "/usr/share/xml/comps/1.0/comps.dtd" $CATALOG || :
/usr/bin/xmlcatalog --noout --add "rewriteURI" \
    "comps.dtd" \
    "/usr/share/xml/comps/1.0/comps.dtd" $CATALOG || :

%postun runtime
if [ $1 = 0 ]; then
    CATALOG=/etc/xml/catalog
    /usr/bin/xmlcatalog --noout --del \
        "/usr/share/xml/comps/1.0/comps.dtd" $CATALOG || :
fi

%files
%defattr(-,root,root)
%doc COPYING
%doc ChangeLog
%doc docs/command-line.txt
%doc docs/install-methods.txt
%doc docs/kickstart-docs.txt
%doc docs/mediacheck.txt
%doc docs/anaconda-release-notes.txt
/usr/bin/mini-wm
/usr/sbin/anaconda
%ifarch i386
/usr/sbin/gptsync
%endif
/usr/share/anaconda
/usr/share/locale/*/*/*
/usr/lib/anaconda

%files runtime
%defattr(-,root,root)
/usr/lib/anaconda-runtime
/usr/share/xml/comps

%triggerun -- anaconda < 8.0-1
/sbin/chkconfig --del reconfig >/dev/null 2>&1 || :

%changelog
* Mon Dec 20 2010 Radek Vykydal <dcantrell@redhat.com> 11.1.2.224-1
- noeject overrides kickstart eject (bcl)
  Related: rhbz#477887
- Pass --noeject to anaconda (bcl)
  Related: rhbz#477887

* Thu Dec 16 2010 David Cantrell <dcantrell@redhat.com> 11.1.2.223-1
- Rebuild for latest kudzu and pciutils (pciutils ABI change)
  Related: rhbz#663395

* Thu Dec 13 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.222-1
- Japanese translations were completed (transifex)
  Resolves: rhbz#661199

* Thu Dec 9 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.221-1
- Japanese translations were updated (transifex)
  Resolves: rhbz#661199

* Mon Dec 6 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.220-1
- Gtk package %post script has changed (rvykydal)
  Resolves: rhbz#659309

* Tue Nov 30 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.219-1
- Generate correct initrd.addrsize file for System z (dcantrell)
  Related: rhbz#647827

* Tue Nov 16 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.218-1
- Append to modprobe.conf rather than overwrite it (dcantrell)
  Related: rhbz#537887

* Thu Nov 11 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.217-1
- Fix generic.ins for s390 LPAR installations (dcantrell)
  Resolves: rhbz#647827
- Fix gateway ping test for layer3 vswitch users (dcantrell)
  Resolves: rhbz#643961
- Disable IPv6 modules for 'noipv6' in /etc/modprobe.conf (dcantrell)
  Resolves: rhbz#537887
- Document noeject (bcl)
  Resolves: rhbz#647232

* Tue Sep 28 2010 David Cantrell <dcantrell@redhat.com> 11.1.2.216-1
- Don't immediately retry on downloading a package. (clumens)
  Resolves: rhbz#544323
- Make sure we can go back to a previous step before doing so (clumens)
  Resolves: rhbz#537889
- Check for and complain about package scriptlet errors (clumens)
  Resolves: rhbz#531599

* Mon Sep 20 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.215-1
- Add python-libs package, python package has been split (rvykydal)
  Resolves: rhbz#634827

* Wed Sep 8 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.214-1
- Add noeject support to cdrom eject handling (bcl)
  Resolves: rhbz#477887
- Add noeject support to loader2 (bcl)
  Related: rhbz#477887
- Resolve kernel dependencies in pkgorder (mgracik)
  Resolves: rhbz#491136

* Fri Aug 20 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.213-1
- Do not check size of swap partition(s) on s390 (dcantrell)
  Resolves: rhbz#475358
- Make parent directories for ks scriptlet log files (dcantrell)
  Resolves: rhbz#568861
- Add dlabel confirmation dialog to interactive installs (msivak)
  Resolves: rhbz#570053
- Add xts module to initrd (msivak)
  Resolves: rhbz#553411
- Add support for LSI 3ware 97xx SAS/SATA RAID Controller (msivak)
  Resolves: rhbz#572341
- Add support for QLogic Corp cLOM8214 1/10GbE Controller (msivak)
  Resolves: rhbz#571895
- Support for Brocade FCoE/CEE to PCIe CNAs (msivak)
  Resolves: rhbz#549677
- Disable ipv6 kernel modules if user disables IPv6 (dcantrell)
  Resolves: rhbz#537887

* Mon Aug 16 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.212-1
- Mount /proc/bus/usb under /mnt/sysimage (hdegoede)
  Resolves: rhbz#532397
- Update kickstart-docs iscsi commands information (hdegoede)
  Resolves: rhbz#525136

* Wed Aug 11 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.211-1
- Clean up sanityCheckHostname() in network.py (dcantrell)
  Resolves: rhbz#559626
- Support long 'option domain-name' values in loader (dcantrell)
  Resolves: rhbz#578110
- Prevent SIGSEGV in ipCallback and cidrCallback (dcantrell)
  Resolves: rhbz#440498

* Wed Aug 04 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.210-1
- Add Chelsio T4 10Gb driver to install (bcl)
  Resolves: rhbz#562913
- Fix traceback on headless installs with xconfig --startxonboot (clumens)
  Resolves: rhbz#517051
- Install the right arch of anaconda's required packages (clumens)
  Resolves: rhbz#541323
- Document options of nfs boot parameter (akozumpl)
  Resolves: rhbz#559200
- Document ignoredisk --only-use kickstart option (clumens)
  Resolves: rhbz#586576

* Mon Mar 22 2010 Martin Sivak <msivak@redhat.com> 11.1.2.209-1
- Add a missing patch to make dlabel work again
  Related: rhbz#485060

* Sun Mar 21 2010 David Cantrell <dcantrell@redhat.com> 11.1.2.208-1
- Revert patch for #521189 (dcantrell)
  Resolves: rhbz#575129

* Sun Mar 21 2010 David Cantrell <dcantrell@redhat.com> 11.1.2.207-1
- Fix driver disk loading from partitionless media (dcantrell)
  Resolves: rhbz#575129

* Tue Mar 09 2010 Martin Sivak <msivak@redhat.com> 11.1.2.206-1
- Use /sys/block instead of /proc/partitions for device nodes (msivak)
  Related: rhbz#485060
- Wait a bit longer for network on s390 (Brad Hinson)
  Resolves: rhbz#506742

* Tue Mar 2 2010 Ales Kozumplik <akozumpl@redhat.com> 11.1.2.205
- Do not leave the initial slash in path in getHostandPath() (akozumpl)
  Resolves: rhbz#568691

* Tue Feb 23 2010 David Cantrell <dcantrell@redhat.com> 11.1.2.204
- Update anaconda xorg driver list (dcantrell)
  Resolves: rhbz#567666

* Tue Feb 23 2010 Radek Vykydal <rvykydal@redhat.com> 11.1.2.203
- Cut the size of the boot.img for ia64 in half (akozumpl)
  Resolves: rhbz#556976

* Fri Jan 29 2010 Martin Sivak <msivak@redhat.com> 11.1.2.202-4
- Rebuild anaconda to get the newest Kudzu
  Resolves: rhbz#555188

* Fri Jan 29 2010 Martin Sivak <msivak@redhat.com> 11.1.2.202-3
- Rebuild anaconda to get the newest Kudzu
  Resolves: rhbz#555188

* Wed Jan 27 2010 Chris Lumens <clumens@redhat.com> 11.1.2.202-2
- Add anaconda support for group removal syntax.
  Resolves: rhbz#558516

* Thu Jan 21 2010 Martin Sivak <msivak@redhat.com> 11.1.2.201-2
- Rebuild anaconda to get the newest Kudzu
  Related: rhbz#555188

* Fri Jan 15 2010 David Cantrell <dcantrell@redhat.com> 11.1.2.201-1
- os.exists -> os.path.exists (clumens)
  Resolves: rhbz#554853
- reIPL support for s390 (hamzy)
  Resolves: rhbz#512195
- Include 'mpath' in generic.prm file for s390 and s390x (dcantrell)
  Resolves: rhbz#538129

* Fri Jan 08 2010 Martin Sivak <msivak@redhat.com> 11.1.2.200-1
- Provide CMS script for IPL under z/VM
  Resolves: rhbz#475343
- Force interface up before checking link status
  Resolves: rhbz#549751
- Document new bootloader --hvargs kickstart option
  Related: rhbz#501438

* Tue Dec 22 2009 Martin Sivak <msivak@redhat.com> 11.1.2.199-1
- Support for the pmcraid driver
  Resolves: rhbz#532777
- Always return correct network config from kickstartNetworkUp
  Resolves: rhbz#495042
- Actually use the ftp login&password parse code
  Related: rhbz#505424
- Fix clearpart of PVs that are part of multidrive VGs
  Resolves: rhbz#545869
- Add support for Brocade Fibre Channel to PCIe Host Bus Adapters
  Resolves: rhbz#475707
- Fix EDD BIOS information parsing
  Resolves: rhbz#540637

* Fri Dec 11 2009 Martin Sivak <msivak@redhat.com> 11.1.2.198-3
- Fix the build for s390
  Related: rhbz#517768

* Fri Dec 11 2009 Martin Sivak <msivak@redhat.com> 11.1.2.198-2
- Fix the build, we were missing one include in loader.c
  Related: rhbz#517768

* Fri Dec 11 2009 Martin Sivak <msivak@redhat.com> 11.1.2.198-1
- Various improvements to kickstart scriptlet reporting
  Resolves: rhbz#510636
- Fix parsing of optional portnr in iscsi target IP
  Resolves: rhbz#525054
- "ip=ibft" is not needed any more if ibft configuration is available
  Resolves: rhbz#517768
- Revert the badEDID check
  Resolves: rhbz#445486
- Remove #!/usr/bin/env python calls
  Resolves: rhbz#521337
- Do not reinstall packages of the same NAEVR in upgrade
  Resolves: rhbz#495796
- Add be2iscsi driver support
  Resolves: rhbz#529442
- Reset partitioning when going back to parttype screen
  Resolves: rhbz#516715
- Find LVs specified by label in /etc/fstab
  Resolves: rhbz#502178
- Ensure the ghostscript-fonts get installed with ghostscript
  Resolves: rhbz#530548

* Fri Nov 20 2009 Martin Sivak <msivak@redhat.com> 11.1.2.197
- Added N-Port-ID (NPIV) install support for Linux on Power
  Resolves: rhbz#512237
- Ignore comments when looking for %ksappend lines
  Resolves: rhbz#525676
- Add kickstart support for xen hypervisor arguments in grub.
  Resolves: rhbz#501438
- Fix kickstarts without a pw
  Resolves: rhbz#538412

* Fri Nov 13 2009 Martin Sivak <msivak@redhat.com> 11.1.2.196-2
- Write HOTPLUG=no to ifcfg file is ONBOOT=no
  Resolves: rhbz#498086
- Honor the --label option to the kickstart "part" command
  Resolves: rhbs#498856
- Add "Hipersockets" to qeth NETTYPE description
  Resolves: rhbz#511962
- Honor existing RUNKS conf file variable on s390
  Resolves: rhbz#513951
- kickstart option to make mpath0 point to arbitrary LUN
  Resolves: rhbz#502768
- Sleep if the kickstart file read fails
  Related: rhbz#460566
- If the device disappeared during DD selection, do not crash
  Resolves: rhbz#521189

* Tue Nov 10 2009 Martin Sivak <msivak@redhat.com> 11.1.2.196-1
- Adds interactive install support for NFS options
  Resolves: rhbz#493052
- KS can reside on password protected FTP servers
  Resolves: rhbz#505424
- Detect oemdrv DDs on cdrom devices too
  Resolves: rhbz#485060
- Prepare dev nodes for block devices too for blkid
  Resolves: rhbz#515437

* Wed Aug 05 2009 Martin Sivak <msivak@redhat.com> 11.1.2.195-1
- Update the loader with support code for Mellanox cards
  Resolves: rhbz#514971

* Mon Aug 03 2009 Martin Sivak <msivak@redhat.com> 11.1.2.194-1
- comps changed. replaced "virtualization" with "xen" (jgranados)
  Resolves: rhbz#514885
- Add support for Melanox ConnectX mt26448 10Gb/s Infiniband, Ethernet, and FC (msivak)
  Resolves: rhbz#514971

* Thu Jul 23 2009 Joel Granados <jgranado@redhat.com>  11.1.2.193-1
- Make sure we include libdrm.so files in the image.
  Related: rhbz#510397

* Wed Jul 22 2009 Chris Lumens <clumens@redhat.com> 11.1.2.192-1
- Fix compile errors in the previous patch.
  Related: rhbz#471883

* Wed Jul 22 2009 Chris Lumens <clumens@redhat.com> 11.1.2.191-1
- Ignore block devices set to read-only.
  Related: rhbz#471883

* Tue Jul 21 2009 Martin Sivak <msivak@redhat.com> 11.1.2.190-1
- Correct a message presented to the user.
  Related: rhbz#473747
- Remove ext4dev
  Resolves: rhbz#510634

* Thu Jul 16 2009 Radek Vykydal <rvykydal@redhat.com> 11.1.2.189-1
- Make buildinstall error out if mount of loop device fails (rvykydal).
  Resolves: rhbz#472552

* Tue Jul 11 2009 Joel Granados <jgranado@redhat.com> 11.1.2.188-1
- Require libdhcp6client for the build (jgranado).
  Related: rhbz#506722

* Mon Jul 10 2009 Joel Granados <jgranado@redhat.com> 11.1.2.187-1
- Add support for the qlge driver (jgranado)
  Resolves: rhbz#504034

* Mon Jul 10 2009 Joel Granados <jgranado@redhat.com> 11.1.2.186-1
- update support for ext4 in anaconda (jbastian)
  Resolves: rhbz#510634

* Wed Jul 08 2009 Chris Lumens <clumens@redhat.com> 11.1.2.185-1
- Save bootfile, if we have it, from DHCP response (dcantrell).
  Resolves: rhbz#448006

* Wed Jul 1 2009 Martin Sivak <msivak@redhat.com> 11.1.2.184-1
- Fix handling of parted exceptions in text mode (rvykydal)
  Resolves: rhbz#506725

* Thu Jun 4 2009 Joel Granados <jgranado@redhat.com> 11.1.2.183-1
- Create efirtc device node on ia64 to access hw clock (rvykydal).
  Resolves: rhbz#485200
- Reserve enough space for lvm metadata when computing PV size usable for LVs (rvykydal).
  Resolves: rhbz#500431

* Mon Jun 1 2009 Joel Granados <jgranado@redhat.com> 11.1.2.182-1
- Add support for IGB VF device (jgranado).
  Resolves: rhbz#502875
- Fix the error caused by change in fipscheck (again..) (msivak).
  Resolves: rhbz#498992

* Thu May 28 2009 Joel Granados <jgranado@redhat.com> 11.1.2.181-1
- Look for ipcalc in the right place (jgranado).
  Resolves: rhbz#502249

* Thu May 28 2009 Joel Granados <jgranado@redhat.com> 11.1.2.180-1
- Look for ipcalc in the right place (jgranado).
  Resolves: rhbz#502249

* Wed May 27 2009 Joel Granados <jgranado@redhat.com> 11.1.2.179-1
- Look for ipcalc in the right place (jgranado).
  Resolves: rhbz#502249

* Tue May 26 2009 Joel Granados <jgranado@redhat.com> 11.1.2.178-1
- Fix specification of zoneinfo files to be included in stage2 (rvykydal).
  Resolves: rhbz#481617
- Fix the location of libfipscheck in initrd too (msivak).
  Resolves: rhbz#498992
- cryptsetup status reversed its exit codes (dcantrell).
  Resolves: rhbz#499824
- Require latest libdhcp (jgranado).
  Resolves: rhbz#444919
- Do not include removed physical volumes in pvlist (rvykydal).
  Resolves: rhbz#502438

* Thu May 21 2009 Joel Granados <jgranado@redhat.com> 11.1.2.177-1
- Do not load storage drivers before loading DUD over network (rvykydal).
  Resolves: rhbz#454478

* Thu May 21 2009 Joel Granados <jgranado@redhat.com> 11.1.2.176-1
- Remove LVM metadata when doing clearpart (rvykydal).
  Resolves: rhbz#462615
- Put lspci in the minstg2.img so inVmware doesn't traceback (clumens).
  Resolves: rhbz#476476

* Mon May 18 2009 Joel Granados <jgranado@redhat.com> 11.1.2.175-1
- Change the description of be2net (msivak).
  Resolves: rhbz#496875
- Revert to libdhcp from rhel5.3 (dcantrell).
  Related: rhbz#500775

* Wed May 13 2009 Joel Granados <jgranado@redhat.com> 11.1.2.174-1
- Include valid timezones in stage 2 (rvykydal).
  Resolves: rhbz#481617
- Fix traceback in timezone setting (kickstart interactive text mode) (rvykydal).
  Resolves: rhbz#481617
- Compute size of modules buffer in loader (dcantrell).
  Resolves: rhbz#484092
- Include /sbin/ipcalc for IP address validation (dcantrell).
  Resolves: rhbz#460579
- Require latest libdhcp (dcantrell).
  Resolves rhbz#444919
- Make buildinstall error out if mount of loop device fails (rvykydal).
  Resolves: rhbz#472552
- Update Anaconda with new description for Emulex lpfc driver (msivak).
  Resolves: rhbz#498511
- Get the libfipscheck from correct location (library was rebased) (msivak)
  Resolves: rhbz#498992
- Add support for LSI MPT Fusion SAS 2.0 Device Driver (msivak).
  Resolves: rhbz#475671
- IBM improvements to linuxrc.s390 (dcantrell).
  Resolves: rhbz#475350

* Wed May 6 2009 Joel Granados <jgranado@redhat.com> 11.1.2.173-1
- Allow bootloader on mbr when /boot is mdraid1 (hansg).
  Resolves: rhbz#475973
- Don't traceback on read only (write protected) disks (hansg).
  Resolves: rhbz#471883
- most noticably it fixes chap / reverse chap in combination with ibft (hansg).
  Resolves: rhbz#497438
- Recognize mpath iscsi setups as using iscsi (hansg).
  Resolves: rhbz#466614

* Tue May 5 2009 Joel Granados <jgranado@redhat.com> 11.1.2.172-1
- The lambda function in run() is not needed (jgranado).
  Resolves: rhbz#498935
- Increase max NIC identification duration to 5 minutes (dcantrell).
  Resolves: rhbz#473747
- Correct a spelling error (dcantrell).
  Resolves: rhbz#489997
- Remove noise from isys/nl.c (dcantrell).
  Resolves: rhbz#490735

* Thu Apr 30 2009 Chris Lumens <clumens@redhat.com> 11.1.2.171-1
- Remove umask temporarily so device permissions are correct (wmealing).
  Resolves: rhbz#383531

* Tue Apr 28 2009 Chris Lumens <clumens@redhat.com> 11.1.2.170-1
- No longer set cachedir since the rebased yum won't let us.
  Resolves: rhbz#497288
- Support a dashed format of MAC in kickstarts (msivak).
  Resolves: rhbz#480309
- Fix a typo in the parted exception ignoring patch
  Related: rhbz#455465
- Add support for Marvell RAID bus controller MV64460/64461/64462 (msivak).
  Resolves: rhbz#493179
- Add support for the "Emulex OneConnect 10GbE NIC" (msivak).
  Resolves: rhbz#496875

* Thu Apr 23 2009 Martin Sivak <msivak@redhat.com> 11.1.2.169-1
-  Activate ipv6 nics when an ipv6 ip is defined (jgranado).
   Resolves: rhbz#445394
-  Check for DNS validity (jgranado).
   Resolves: rhbz#465174
-  Do not crash when more than 32 tape devices are present (rvykydal)
   Resolves: rhbz#476186
-  Ignore a subset of parted errors that are not critical (clumens)
   Resolves: rhbz#455465
-  The FTP USER command does not need to be followed by a PASS (msivak)
   Resolves: rhbz#477536
-  patch to skip accounts screen if using autostep and encrypted root password (msivak)
   Resolves: rhbz#471122
-  rhel5 fix for cmdline being overridden by text when graphical install is detected as unworkable (msivak)
   Resolves: rhbz#456325
-  Rewrote parts of pkgorder script to improve it's speed. (mgracik)
   Resolves: rhbz#451083
-  Fix for traceback in Partitions.doMetaDeletes.addSnap() (dcantrell)
   Resolves: rhbz#433824
-  More robust filtering of physical volumes in autopartitioning (rvykydal)
   Resolves: rhbz#475271
-  Fix user --groups kickstart option (rvykydal)
   Resolves: rhbz#454418
-  Let LCS devices come online after s390 installation (dcantrell)
   Resolves: rhbz#471101
-  Added support for mdadm raid10 installs (mgracik)
   Resolves: rhbz#467996
-  Updated the project URL (mgracik)
   Resolves: rhbz#482781

* Thu Dec 18 2008 Joel Granados <jgranado@redhat.com> 11.1.2.168-1
-  Make anaconda work with new API change in YUM (jgranado)
   Resolves: rhbz:#476957

* Wed Dec 17 2008 Joel Granados <jgranado@redhat.com> 11.1.2.167-1
- Fix anaconda build (hdegoede).
  Related: rhbz:#476739

* Tue Dec 16 2008 Joel Granados <jgranado@redhat.com> 11.1.2.166-1
- Load the raid45 modules at init time (jgranado).
  Related: rhbz#475385
- Make sure the raid45 modules are in the images (jgranado).
  Related: rhbz#475385

* Mon Dec 15 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.165-1
- Final translations for instnum text (clumens)
  Related: rhbz#474375

* Fri Dec 12 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.164-1
- Fix non-CHAP iBFT install cases (hdegoede)
  Resolves: rhbz#432819
- More translations for the instnum text (clumens)
  Related: rhbz#474375

* Wed Dec 10 2008 Chris Lumens <clumens@redhat.com> 11.1.2.163-1
- Mark some new translations as fuzzy to fix the build.
  Related: rhbz#474375

* Wed Dec 10 2008 Chris Lumens <clumens@redhat.com> 11.1.2.162-1
- Update translation files for the instnum text change.
  Related: rhbz#474375

* Wed Dec 3 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.161-1
- Include the libwrap in the initrd image
  Resolves: rhbz#473955

* Mon Dec 1 2008 Joel Granados <jgranado@redhat.com> 11.1.2.160-1
- Allow ssh and telnet to the install (jgranado).
  Resolves: rhbz:#473955

* Mon Dec 1 2008 Joel Granados <jgranado@redhat.com> 11.1.2.159-1
- The LV size is smaller than the totall sum of the partitions that make it up (jgranado).
  Resolves: rhbz:#468944

* Tue Nov 25 2008 Chris Lumens <clumens@redhat.com> 11.1.2.158-1
- Fix up ibft use cases (pjones).
- Partition requests can be None when populating the tree (dlehman).
  Resolves: rhbz#472788
- Remove the name check on driver disk packages.
  Resolves: rhbz#472951
- Remove missing PVs before removing obsolete VG (rvykydal).
  Resolves: rhbz#468431
- Make the driverdisc label uppercase (msivak).
  Related: rhbz#316481

* Wed Nov 19 2008 Chris Lumens <clumens@redhat.com> 11.1.2.157-1
- Include ide-cs module into initrd (msivak).
  Related: rhbz#448009

* Wed Nov 12 2008 Chris Lumens <clumens@redhat.com> 11.1.2.156-1
- Fix a variety of pychecker errors (clumens, dcantrell, dlehman, rvykydal).
  Resolves: rhbz#469734
- Remove defunct VG before creating new one of the same name (rvykydal).
  Resolves: rhbz#469700
- Fix detection of ext4 on raid in rescue and upgrade (rvykydal).
  Resolves: rhbz#470221

* Tue Nov 11 2008 Joel Granados <jgranado@redhat.com> 11.1.2.155-1
- Enable the DD repository if the DD autodetection feature was used (msivak).
  Related: rhbz:#316631
- Call insmod in linuxrc.s390, not insert_module (dcantrell).
  Related: rhbz:#184648
- Load FCP modules early for CD/DVD install (dcantrell).
  Related: rhbz:#184648
- Update mk-s390-cdboot.c to work with large kernel images (dcantrell).
  Related: rhbz:#184648
- Fix all trivial (1 liner fixes) errors found by pychecker (hdegoede).
  Related: rhbz:#469730

* Wed Nov 05 2008 Chris Lumens <clumens@redhat.com> 11.1.2.154-1
- Include the new fnic driver (jgranado).
  Related: rhbz#462387
- Run the busProbe after we have all driver disks loaded (msivak).
  Related: rhbz#316481

* Wed Nov 5 2008 Joel Granados <jgranado@redhat.com> 11.1.2.153-1
- Use struct audit_reply instead of struct auditd_reply_list (hdegoede).
  Resolves: rhbz:#469873
- The Encryption button was missing in one migrate case (msivak).
  Resolves:#469849
- kickstart expects --dhcpclass instead of --class (clumens).
  Resolves: rhbz:#468972
- Fix the mounting procedure for autodetected driverdiscs (msivak).
  Resolves: rhbz:#316481

* Fri Oct 31 2008 Joel Granados <jgranado@redhat.com> 11.1.2.152-1
- Prepare environemnt so the AutoDD is properly detected (msivak).
  Resolves: rhbz:#316481
- Don't write luks passphrases to anaconda-ks.cfg (dlehman).
  Resolves: rhbz:#468907
- Write zeros to remove metadata before running luksFormat (dlehman).
  Resolves: rhbz:#469177

* Wed Oct 29 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.151-1
- Write correct OPTIONS line to ifcfg files on s390 for layer2 (dcantrell)
  Resolves: rhbz#468755

* Wed Oct 29 2008 Joel Granados <jgranado@redhat.com> 11.1.2.150-1
- Call createrepo in buildinstall only if --pkgorder is present (rvykydal).
  Resolves: rhbz:#467341

* Tue Oct 28 2008 Joel Granados <jgranado@redhat.com> 11.1.2.149-1
- Actually use the stderr parameter instead of duping to stdout (dlehman).
  Resolves: rhbz:#467289
- Revert "Specify a default cio_ignore parameter for s390x (#253075)" (dcantrell).
  Related: rhbz:#253075
- Revert "Enable CCW devices used for installation (#253075)" (dcantrell).
  Related: rhbz:#253075
- Revert "Correctly enable ignored CCW devices in linuxrc.s390 (#253075)" (dcantrell).
  Related: rhbz:#253075

* Fri Oct 24 2008 Joel Granados <jgranado@redhat.com> 11.1.2.148-1
- Probe the devices to populate cache for DD routines (msivak).
  Resolves: rhbz:#316481

* Thu Oct 23 2008 Joel Granados <jgranado@redhat.com>  11.1.2.147-1
- Dont execute the extra information message for all the devices (jgranado).
  Resolves: rhbz:#466291

* Tue Oct 21 2008 David Cantrell <dcnatrell@redhat.com> 11.1.2.146-1
- Fix up CCW device enabling on s390x (dcantrell)
  Resolves: rhbz#253075

* Mon Oct 20 2008 Dave Lehman <dlehman@redhat.com> 11.1.2.145-1
- Handle device names containing "/" in LUKS name fixup
  Related: rhbz#464769

* Thu Oct 16 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.144-1
- Enable CCW devices used for installation (dcantrell)
  Resolves: rhbz#253075

* Wed Oct 15 2008 Joel Granados <jgranado@redhat.com>  11.1.2.143-1
- Change order when calling dasdFmt to avoid race condition while formating dasd drives (jgranado).
  Resolves: rhbz:#466474

* Tue Oct 14 2008 Joel Granados <jgranado@redhat.com> 11.1.2.142-1
- Add the enic driver (jgranado).
  Resolves: rhbz:#462387
- Get the right list elements for the iscsi text interface (clumens).
  Resolves: rhbz:#466902
- Fix detection of ext4/ext4dev root partitions in rescue (rvykydal).
  Resolves: rhbz:#466868

* Mon Oct 13 2008 Joel Granados <jgranado@redhat.com> 11.1.2.141-1
- Prevent creation of encrypted swraid partitions (dlehman).
  Resolves: rhbz:#456283
- Enable the iBFT by default and set the fallbacks to mimic the w/o iBFT behaviour (msivak).
  Resolves: rhbz:#445721

* Fri Oct 10 2008 Peter Jones <pjones@redhat.com> - 11.1.2.140-1
- Don't display errors from nl_set_device_mtu() (dcantrell)
  Resolves: rhbz#466305
- Use a correct path for addnote, since the one in the original patch
  wasn't what the kernel group thought they were telling me.
  Related: rhbz#462663

* Thu Oct 09 2008 Chris Lumens <clumens@redhat.com> 11.1.2.139-1
- Handle None in luks device name rectification (pjones).
  Resolves: rhbz#466348

* Wed Oct 08 2008 Peter Jones <pjones@redhat.com> - 11.1.2.138-2
- Start the iBFT configured drives during iSCSI startup (msivak)
  Resolves: rhbz#445721

* Wed Oct 08 2008 Peter Jones <pjones@redhat.com> - 11.1.2.138-1
- Add note to bootable kernel image on ppc64 (dhowells)
  Related: rhbz#462663

* Mon Oct 06 2008 Chris Lumens <clumens@redhat.com> 11.1.2.137-2
- Better error checking when retrieveing info from iBFT (msivak).
  Related: rhbz#445721
- Fix a typo in the anaconda-runtime %post scriptlets.
  Resolves: rhbz#465441

* Fri Oct 3 2008 Joel Granados <jgranado@redhat.com> 11.1.2.136-2
- Fix build.
  Related: rhbz:#445721

* Fri Oct 3 2008 Joel Granados <jgranado@redhat.com> 11.1.2.136-1
- Rebuild to make brew happy.
  Related: rhbz:#445721

* Fri Oct 3 2008 Joel Granados <jgranado@redhat.com> 11.1.2.135-1
- iBFT has MAC addresses with wrong case, use strcasecmp to compare them (msivak).
  Resolves: rhbz:#445721
- Look up correct luks name before trying to decide on our boot device (pjones).
  Resolves: rhbz:#464769
- Add new LUKS devices to partitions.encryptedDevices (dlehman).
  Resolves: rhbz:#464769
- Add a workaround for lvm-on-raid size miscomputation (clumens).
  Resolves: rhbz:#463431
- Do not use labels to specifiy LUKS devices in /etc/fstab (dlehman).
  Resolves: rhbz:#461702

* Thu Oct 2 2008 Joel Granados <jgranado@redhat.com> 11.1.2.134-1
- Fix traceback when using kickstart and device encryption (pjones).
  Resolves: rhbz:#461700
- Fix traceback when using encryption with kickstart (pjones).
  Resolves: rhbz:#461700
- Fix ext4/ext4dev detection on existing partitions (rvykydal).
  Resolves: rhbz:#465248

* Tue Sep 30 2008 Joel Granados <jgranado@redhat.com> 11.1.2.133-1
- Set a label on /etc/sysconfig/keyboard (clumens).
  Resolves: rhbz:#463785
- Add comps.dtd to anaconda-runtime package (dcantrell).
  Resolves: rhbz:#442138
- Make sure /etc/xml/catalog is updated on package removal (dcantrell).
  Resolves: rhbz:#442138
- Fix a logging traceback in the encryption code (clumens).
  Resolves: rhbz:#464771
- Fix lvm partitioning in gui that was broken (rvykydal).
  Resolves: rhbz:#415871
- Fix computing of lvm partition sizes wrt physical extent size in gui (rvykydal).
  Resolves: rhbz:463780
- Add pointer initialization (rvykydal).
  Resolves: rhbz#439461

* Fri Sep 26 2008 Joel Granados <jgranado@redhat.com> 11.1.2.132-1
- When we use kickstart with specified UI mode, do not prompt for VNC (msivak).
  Resolves: rhbz##453551

* Thu Sep 25 2008 Chris Lumens <clumens@redhat.com> 11.1.2.131-1
- Fix rescue mode typo.
  Resolves: rhbz#463920
- Fix traceback accessing obsolete data member (dlehman).
  Resolves: rhbz#463778

* Tue Sep 23 2008 Chris Lumens <clumens@redhat.com> 11.1.2.130-1
- Fix the test for if we should remove the Virt group.
  Resolves: rhbz#462907.

* Mon Sep 22 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.129-1
- Fix mk-s390-cdboot so it doesn't SIGSEGV when generating images (dcantrell)
  Related: rhbz#184648
- Add libfipscheck to initrd for sshd on s390x (clumens)
  Resolves: rhbz#463273

* Fri Sep 19 2008 Chris Lumens <clumens@redhat.com> 11.1.2.128-1
- Include the correct version of the spec file in the source archive.
  Related: rhbz#461700

* Fri Sep 19 2008 Chris Lumens <clumens@redhat.com> 11.1.2.127-1
- Support for system-wide passphrase for encrypted block devices (dlehman).
  Resolves: rhbz#461700

* Wed Sep 17 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.126-1
- Add a stub to cmdline UI for getLuksPassphrase (dlehman)
  Resolves: rhbz#462491
- Don't add a LUKSDevice to autopart PVs unless we're encrypting (dlehman)
  Resolves: rhbz#462640
- Support upgrade of systems that use encrypted block devices (dlehman)
  Resolves: rhbz#461696
- Disallow use or creation of encrypted software RAID partitions (dlehman)
  Resolves: rhbz#456283
- Use UUIDs instead of device nodes in crypttab (dlehman)
  Resolves: rhbz#461702
- Add support for OSA Express 2 ports per CHPID (rvykydal)
  Resolves: rhbz#439461
- Fix kickstart timezone value checking (rvykydal)
  Resolves: rhbz#462595
  Resolves: rhbz#404321

* Tue Sep 16 2008 Chris Lumens <clumens@redhat.com> 11.1.2.125-1
- Include the programs needed to manage ext4 filesystems (clumens).
  Resolves: rhbz#462476
- Fix a reference to a variable before it exists in network.py (clumens).
  Resolves: rhbz#462480

* Mon Sep 15 2008 Chris Lumens <clumens@redhat.com> 11.1.2.124-1
- Fix blkid_dev_next return value checking (rvykydal).
  Resolves: rhbz#462175
- Add the reverse chap bits for kickstart as well (pjones).
  Related: rhbz#432819
- Make iBFT reading explicit from a higher level (pjones).
- Fix device nodes creating for more than 8 cciss devices (rvykydal).
  Resolves: rhbz#445765
- Disable iBFT support for s390 and s390x (dcantrell).

* Thu Sep 11 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.123-1
- Disable iBFT support on s390 and s390x (dcantrell)
  Related: rhbz#445721

* Thu Sep 11 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.122-1
- Add full CHAP support to iSCSI (pjones)
  Resolves: rhbz#432819
- Don't set iscsi devices to autostart (pjones)
  Resolves: rhbz#437891
- Support iSCSI CHAP and Reverse CHAP authentication (pjones)
  Resolves: rhbz#402431
  Resolves: rhbz#432819
- Partitions growing fixed (rvykydal)
  Resolves: rhbz#442628
- Do not traceback when no root partitions are found in upgrade (rvykydal)
  Resolves: rhbz#444527
- Add support for ext4dev/ext4 filesystem (rvykydal)
  Resolves: rhbz#444527
- Add support for reading NIC setup from the iBFT table (msivak)
  Resolves: rhbz#445721
- Add 802.1q driver (rvykydal)
  Resolves: rhbz#431915
- Add libfipscheck to the images (clumens)
  Resolves: rhbz#461923
- Display drive model and size in MB in partitioning UI (dcantrell)
  Resolves: rhbz#460697

* Wed Sep 03 2008 Chris Lumens <clumens@redhat.com> 11.1.2.121-1
- Enable the dlabel=on for RHEL by default (msivak).
  Related: rhbz#316481.

* Thu Aug 28 2008 Chris Lumens <clumens@redhat.com> 11.1.2.120-2
- libuuid is provided by e2fsprogs-devel.
  Related: rhbz#316481.

* Thu Aug 28 2008 Chris Lumens <clumens@redhat.com> 11.1.2.120-1
- Include the nss libraries that the new RPM is linked against.
  Resolves: rhbz#460375.
- Add automatic driver disk detection (msivak).
  Resolves: rhbz#316481.

* Wed Aug 6 2008 Joel Granados <jgranado@redhat.com> 11.1.2.119-1
- Support VDSK devices on s390x (dcantrell).
  Resolves: rhbz#264061

* Wed Jul 30 2008 Joel Granados <jgranado@redhat.com> 11.1.2.118-1
- Use fedorakmod.py plugin from yum-utils package, don't pack it in anaconda (rvykydal).
  Resolves: rhbz#434804
- Make sure bootproto=query settings carry over to stage2 (clumens).
  Resolves: rhbz#453863
- Probe BUS_VIRTIO again after probing BUS_PCI (markmc).
  Resolves: rhbz#446232
- Add virtio drives to multipath blacklist (markmc).
  Resolves: rhbz#446232
- Add virtio max partition count (markmc).
  Resolves: rhbz#446232
- Sort virtio devices first (markmc).
  Resolves: rhbz#446232
- Probe on BUS_VIRTIO for devices (markmc).
  Resolves: rhbz#446232
- Explicitly include virtio_pci in the initrd (markmc).
  Resolves: rhbz#446232
- Add virtio to module-info (markmc).
  Resolves: rhbz#446232
- Add virtio support to devMakeInode() (markmc).
  Resolves: rhbz#446232
- Offer physical NIC identification in stage 1 (dcantrell).
  Resolves: rhbz:#261101
- Suspend the curses interface before calling scripts and resume afterwards (msivak).
  Resolves: rhbz#435314

* Wed Jul 23 2008 Joel Granados <jgranado@redhat.com> 11.1.2.117-1
- Fix the build.
- Change the Makefile so it doesn't replace tags.

* Wed Jul 23 2008 Joel Granados <jgranado@redhat.com> 11.1.2.116-1
- Specify a default cio_ignore parameter for s390x (dcantrell).
  Resolves: rhbz#253075
- Call dhcpNetDevice() instead of removed pumpNetDevice() (rvykydal).
  Resolves: rhbz#452664
- Add support for the --only-use argument to RHEL5 (rvykydal).
  Resolves: rhbz#318351
- Log a message informing about the critical upgrade error (jgranado).
  Resolves: rhbz#436865
- Support booting from FCP-attached CD/DVD drive on s390 (dcantrell).
  Resolves: rhbz#184648
- The actual size of a logical volume must be rounted down (jgranado).
  Resolves: rhbz#415871
- Set network device MTU if user specified mtu= (dcantrell).
  Resolves: rhbz#435874

* Wed Jul 16 2008 Joel Granados <jgranado@redhat.com> 11.1.2.115-1
- Pass the cmdline options to the nfs structure (jgranado).
  Resolves: rhbz#432603
- Remove hicolor-icon-theme>gtk2 from whiteout.py (msivak).
  Resolves: rhbz#369251
- Ask the user if he wants to use VNC instead of text mode (msivak).
  Resolves: rhbz#453551
- Leftover bits of encrypted block device support (dlehman).
  Resolves: rhbz#229865
- Rescue of systems containing encrypted block devices (dlehman).
  Resolves: rhbz#229865
- Support preexisting encrypted block devices (dlehman).
  Resolves: rhbz#229865
- Kickstart support for encrypted block devices (dlehman).
  Resolves: rhbz#229865
- User interface for manipulating encrypted block devices (dlehman).
  Resolves: rhbz#229865
- Partitioning with encrypted block devices (dlehman).
  Resolves: rhbz#229865
- Device-level support for encrypted block devices (dlehman).
  Resolves: rhbz#229865

* Wed Jul 9 2008 Joel Granados <jgranado@redhat.com> 11.1.2.114-1
- Enable upgrades for mayor version in rhel5 only (jgranado).
  Resolves: rhbz#436865
- Handling of invalid timezone value in kickstart added (rvykydal).
  Resolves: rhbz#404321
- GCC is complaining about unchecked return value from read call (msivak).
  Resolves: rhbz#448009
- Enable re-IPL on s390x after installation (dcantrell).
  Resolves: rhbz#432416
- Change the maximum recommended swap size to "2000 + (current ram)" (jgranado).
  Resolves: rhbz#447372
- Don't show the virtualization option if we are in Xen or in Vmware (jgranado).
  Resolves: rhbz#258441
- Prepare the system a little before initializing the pcmcia devices (msivak).
  Resolves: rhbz#448009
- Change the total number of processed packages/files/.. to avoid negative counter in remaining packages (msivak).
  Resolves: rhbz#436103
- Create additional /dev/xvda device nodes (clumens).
  Resolves: rhbz#437752
- Don't use error messages from dosfslabel as the label (clumens)
  Resolves: rhbz#427457
- Add nui driver (jgranado).
  Resolves: rhbz#444820
- Allow the use of the "-" character in lvm names (jgranado).
  Resolves: rhbz#430907
- yum.remove removes installed packages, not to be installed packages (msivak).
  Resolves: rhbz#442325
- Allow removing packages by glob now that yum supports it (msivak).
  Resolves: rhbz#442325

* Wed Apr 16 2008 Chris Lumens <clumens@redhat.com> 11.1.2.113-1
- Require the latest version of libnl-devel.
  Resolves: rhbz#441922
- Fix definition of __libc_setlocale_lock for new glibc.
  Resolves: rhbz#441940
- Add support for the bcm5710 driver.
  Resolves: rhbz#442553
- Require the latest libdhcp (dcantrell).
  Resolves: rhbz#435978
- Fix networking tracebacks (pjones, clumens).
  Resolves: rhbz#442020

* Tue Apr 08 2008 Chris Lumens <clumens@redhat.com> 11.1.2.112-1
- Make isys.dhcpNetDevice() work in rescue mode (dcantrell).
  Related: rhbz#435978

* Wed Apr 02 2008 Chris Lumens <clumens@redhat.com> 11.1.2.111-1
- Don't rebuild the initrds if no modules were installed.
  Resolves: rhbz#439379
- Bootable requests can not be on logical volumes.
  Resolves: rhbz#439270
- Name the xen images for ia64 in the .treeinfo file (jgranado).
- Fix reporting on transaction errors (jgranado).
  Resolves: rhbz#437813
- Fix loop iteration in nl_ip2str (dcantrell).
  Resolves: rhbz#437773
- Allow GPT on ppc or ppc64 (dcantrell).
  Resolves: rhbz#438683

* Tue Mar 25 2008 Chris Lumens <clumens@redhat.com> 11.1.2.110-1
- Don't try to initialize iSCSI when the portal cannot be detected (msivak).
  Resolves: rhbz#435173

* Tue Mar 25 2008 Chris Lumens <clumens@redhat.com> 11.1.2.109-1
- Make sure DHCP works in rescue mode (dcantrell).
  Resolves: rhbz#435978

* Mon Mar 17 2008 Chris Lumens <clumens@redhat.com> 11.1.2.108-1
- Avoid SIGSEGV on s390x in netlink loop (dcantrell).
  Resolves: rhbz#436377

* Thu Mar  6 2008 Jeremy Katz <katzj@redhat.com> - 11.1.2.107-1
- Fix another case which could have None options
  Resolves: rhbz#435998

* Wed Mar 05 2008 Chris Lumens <clumens@redhat.com> 11.1.2.106-1
- Fix the case where we're checking for _netdev but options is None (pjones).
  Resolves: rhbz#435998

* Mon Mar 03 2008 Chris Lumens <clumens@redhat.com> 11.1.2.105-1
- Add support for _rnetdev mount option in fstab (pjones).
  Resolves: rhbz#435716
- Lots of network UI configuration fixes (dcantrell).
  Resolves: rhbz#432011
- Fix lvm error handling (msivak).
  Related: rhbz#224636

* Thu Feb 21 2008 Chris Lumens <clumens@redhat.com> 11.1.2.104-1
- Handle exceptions when setting up repos not enabled by a key.
  Resolves: rhbz#433028
- Show unconfigured interfaces as UNCONFIGURED (dcantrell).
  Related:  rhbz#275291

* Tue Feb 19 2008 Chris Lumens <clumens@redhat.com> 11.1.2.103-1
- Fix a traceback in the backported pkgorder fix.
  Resolves: rhbz#432006
- Fix wrong function names for iscsi login/start (pjones).
  Resolves: rhbz#433276

* Sat Feb 16 2008 Chris Lumens <clumens@redhat.com> 11.1.2.102-1
- Correct auth command reading problem for ks files (dcantrell).
  Related: rhbz#427388
- Use correct salt length for MD5, SHA256, & SHA512 (dcantrell).
  Related: rhbz#427388

* Wed Feb 13 2008 Chris Lumens <clumens@redhat.com> 11.1.2.101-1
- Make sure interface description is defined (dcantrell).
  Resolves: rhbz#432635
- Set an attribute when iscsid is started
  Resolves: rhbz#431904

* Mon Feb 11 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.100-1
- Better fixes for iscsi probing (pjones, jlaska)
  Related: rhbz#431924
- Make man pages work in the chrooted environment (jgranado)
  Resolves: rhbz#243443
- Use correct variable in comparison (jgranado)
  Related: rhbz#432035

* Fri Feb 08 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.99-1
- Prevent writing out IPV6ADDR=none lines to ifcfg-ethX files (jgranado)
  Resolves: rhbz#432035

* Thu Feb 07 2008 Chris Lumens <clumens@redhat.com> 11.1.2.98-1
- Fix an infinite loop in using libnl (dcantrell).
  Related: rhbz#303681

* Thu Feb 07 2008 Chris Lumens <clumens@redhat.com> 11.1.2.97-1
- Add module dependencies of qeth.ko.
  Resolves: rhbz#431922
- Make sure ISCSIADM and such are defined (pjones).
  Resolves: rhbz#431924
- Use libnl to read MAC and IP addresses (dcantrell).
  Resolves: rhbz#303681
- Fix usage of minstg2 vs. stage2 in low-mem cases (jgranado).
  Resolves: rhbz#207657

* Tue Feb 05 2008 Chris Lumens <clumens@redhat.com> 11.1.2.96-1
- Include libnssutil3.so in the initrd for s390 as well.
  Resolves: rhbz#431054
- Document the dhcptimeout parameter (msivak).
  Related: rhbz#198147, rhbz#254032

* Mon Feb 04 2008 Chris Lumens <clumens@redhat.com> 11.1.2.95-1
- Propagate hostname from stage 1 to stage 2 on s390x (dcantrell).
  Resolves: rhbz#354021

* Fri Feb 01 2008 Chris Lumens <clumens@redhat.com> 11.1.2.94-1
- Include libnssutil3.so for sshd on s390 (dcantrell).
- Remove old IP addresses from interface on reconfig (dcantrell).
  Resolves: rhbz#218273
- More fixes for .treeinfo (jgranado).

* Wed Jan 30 2008 Chris Lumens <clumens@redhat.com> 11.1.2.93-1
- Support network --bootproto=query in kickstart installs.
  Resolves: rhbz#401531
- Set the format flag for new volume groups (msivak).
  Resolves: rhbz#246523
- More fixes for .treeinfo (jgranado).
  Related: rhbz#253992

* Mon Jan 28 2008 David Cantrell <dcantrell@redhat.com> 11.1.2.92-1
- Fix remaining issues with createLuserConf() changes
  Related: rhbz#430237

* Mon Jan 28 2008 Chris Lumens <clumens@redhat.com> 11.1.2.91-1
- Include python-iniparse in stage2 for pirut.
  Resolves:  rhbz#430212
- Update the information contained in .treeinfo files (jgranado).
  Resolves: rhbz#253992
- Fix namespace issue with createLuserConf (dcantrell).
  Resolves: rhbz#430237
- Write /etc/resolv.conf and /etc/hosts in stage1 on s390 (dcantrell).
  Related: rhbz#428694, rhbz#216158

* Wed Jan 23 2008 Chris Lumens <clumens@redhat.com> 11.1.2.90-1
- Add the stage2 to the .treeinfo file (jgranado).
  Resolves: rhbz#253992
- Fix handling %packages section in output anaconda-ks.cfg file.
  Related: rhbz#280101
- Fix a traceback caused by the patch for 427388.
  Resolves: rhbz#429902
- Fix some additional errors in createLuserConf() (dcantrell).
  Resolves: rhbz#429902
- Fix iscsi so that mkinitrd can talk to the running daemon (pjones).

* Mon Jan 21 2008 Chris Lumens <clumens@redhat.com> 11.1.2.89-1
- Support SHA256/SHA512 password encoding from kickstart (dcantrell).
  Resolves: rhbz#427388

* Fri Jan 18 2008 Chris Lumens <clumens@redhat.com> 11.1.2.88-1
- Allow users to back up past instkey dialog (dlehman).
  Resolves: rhbz#252349
- Handle missing FTP files the same way as missing HTTP files (dlehman).
  Resolves: rhbz#350251
- Add support for iSCSI iBFT (msivak).
  Resolves: rhbz#307761
- Do not display NICs as UNCONFIGURED in network_text.py (dcantrell).
  Resolves: rhbz#275291
- If bootproto is dhcp, unset any static settings (dcantrell).
  Resolves: rhbz#218489
- Add support for the mptctl driver.
  Resolves: rhbz#382941
- Fix a traceback running pkgorder in non-base products (dgregor).
  Resolves: rhbz#317131
- Fix a traceback when adding zFCP disk without specifying details (msivak).
  Resolves: rhbz#428180
- Catch lvm tools errors when creating logical volumes (msivak).
  Resolves: rhbz#224636
- Add support for specifying the dhcp timeout (msivak).
  Resolves: rhbz#198147, rhbz#254032
- Don't add a trailing 1 to filesystem labels (jgranado).
  Resolves: rhbz#415861
- Add spufs support (jgranado).
  Resolves: rhbz#247720
- List iSCSI multipath devices in the installer UI. (dcantrell).
  Resolves: rhbz#391951
- Fix selected device when adding an advanced storage device (msivak).
  Resolves: rhbz#248447
- Add maketreeinfo.py script (jgranado).
  Resolves: rhbz#253992
- Make F12 work for the network config screen in text installs (jgranado).
  Resolves: rhbz#250982
- Add the ixgbe driver (jgranado).
  Resolves: rhbz#350911
- Write out IPV6INIT= to network-scripts (jgranado).
  Resolves: rhbz#243524
- Close md devices to fix RAID tracebacks (jgranado).
  Related: rhbz#208970
- Use input %packages section for anaconda-ks.cfg (msivak).
  Resolves: rhbz#280101
- Add option for selecting different comps file (msivak).
  Resolves: rhbz#352081
- Add nicdelay parameter (msivak).
  Resolves: rhbz#349521
- Be more accepting in which strings we wait for from sshd (alanm).
  Resolves: rhbz#286031
- Allow the use of double quotes in the pxeboot config file (jgranado).
  Resolves: rhbz#248170
- Read the nic info before showing the configuration window (jgranado).
  Resolves: rhbz#278451
- Make the back button work on the network config screen in loader (jgranado).
  Resolves: rhbz#233655
- Get lcs interface name correctly (msivak).
  Resolves: rhbz#237508
- Include more terminfo files to fix s390 telnet mode (msivak).
  Resolves: rhbz#231173
- Fix kickstart docs for --dhcpclass parameter (jgranado).
  Resolves: rhbz#248910
- Fix traceback when displaying autopartition error messages (jgranado).
  Resolves: rhbz#247257
- Fix comparison of unusual network interface names (jgranado).
  Resolves: rhbz#246135
- Populate the kickstart file dialog with the original value (jgranado).
  Resolves: rhbz#245936
- Make the man pages work in rescue mode (jgranado).
  Resolves: rhbz#243443
- Sort text package list (jgranado).
  Resolves: rhbz#242456
- Don't eject the cd before the %post scripts are run (jgranado).
  Resolves: rhbz#238711

* Wed Oct 17 2007 Chris Lumens <clumens@redhat.com> 11.1.2.87-1
- Prompt for manual network configuration in the loader if needed.
  Related: rhbz#296081

* Mon Oct 15 2007 Chris Lumens <clumens@redhat.com> 11.1.2.86-1
- Don't try to use DHCP in networks with static IP configuration.
  Resolves: rhbz#296081

* Wed Oct 03 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.85-1
- Check both IP structure members in getFileFromNfs()
  Resolves: rhbz#316251

* Thu Sep 27 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.84-1
- Check return values correctly on netlink_interfaces_ip2str() and
  netlink_interfaces_mac2str()
  Resolves: rhbz#230525
  Related: rhbz#209284

* Wed Sep 19 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.83-1
- Add cxgb3 driver (pjones)
  Resolves: rhbz#296791

* Tue Sep 18 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.82-1
- Fix kickstart over NFS installs on s390x (ks=nfs:host:/path)
  Resolves: rhbz#250689

* Mon Sep 17 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.81-1
- Make major and minor long ints in devMakeInode()
  Related: rhbz#218816

* Mon Sep 17 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.80-1
- Create all variations of tape drive device nodes (dlehman)
  Resolves: rhbz#218816

* Fri Sep 14 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.79-1
- Correct infinite loop problem with new recvfrom() code for reading large
  netlink messages
  Related: rhbz#230525
- Make sure we clear the netlink cache before looking up IP or MAC addrs
  Related: rhbz#235824

* Thu Sep 13 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.78-1
- Fix manual IPv4 configuration when adding an iSCSI device
  Related: rhbz#235824

* Wed Sep 12 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.77-1
- Revert netlink_init_interfaces_list() changes
  Resolves: rhbz#287541

* Tue Sep 11 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.76-1
- Fix going back to the network device selection screen in loader
  Resolves: rhbz#253285
- Rework netlink_get_interface_ip() to handle large recvfrom responses (pjones)
  Related: rhbz#230525
- Driver disk fixes (clumens)
  Related: rhbz#213318
- Make sure MACADDR is written to ifcfg-* files (bhinson)
  Related: rhbz#248049

* Wed Sep 05 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.75-1
- Fix network handling via CMS conf file on s390x
  Resolves: rhbz#278261

* Wed Sep 05 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.74-1
- Find all NICs with netlink call
  Related: rhbz#230525

* Tue Sep 04 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.73-1
- Handle empty VSWITCH parameter (bhinson AT redhat DOT com)
  Related: rhbz#248049

* Tue Sep 04 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.72-1
- Rebuild against kudzu-1.2.57.1.15
  Resolves: rhbz#276161

* Fri Aug 31 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.71-1
- Remove extra newtPopWindow() call
  Related: rhbz#260621

* Thu Aug 30 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.70-1
- Fix text wrap width on partition type combo (dlehman)
  Related: rhbz#221791
- Avoid SIGSEGV in for kickstart installs on Configure TCP/IP window
  Related: rhbz#260621

* Wed Aug 29 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.69-1
- Skip Configure TCP/IP window for kickstart installs
  Resolves: rhbz#260621
- Do not run _isys.vtActivate() on s390x
  Related: rhbz#217563
- Keep drive selection box disabled if user clicks Back (clumens)
  Related: rhbz#219207

* Mon Aug 27 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.68-1
- Do not return after NIC config for iSCSI setup
  Resolves: rhbz#233029

* Fri Aug 24 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.67-1
- Fix "no more mirrors" problems when retrieving packages (dlehman)
  Resolves: rhbz#240582
- Don't add duplicate fstab entries if the fstype is none (clumens)
  Resolves: rhbz#253485
- Allow users to change their NIC and reconfigure it in loader
  Resolves: rhbz#253285
- Validate IP addresses correctly for manual entry on s390x linuxrc
  Related: rhbz#234152
- Correct setting addon repository names (clumens)
  Related: rhbz#206152

* Fri Aug 17 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.66-1
- Select appropriate kernel devel package (dlehman)
  Related: rhbz#226784

* Fri Aug 17 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.65-1
- Don't assume tb[IFLA_ADDRESS] contains data
  Resolves: rhbz#252988
- Add support for VSWITCH and MACADDR conf variables on s390x
  Resolves: rhbz#248049
- Fix ks=nfs: regression on s390x
  Resolves: rhbz#250689

* Mon Aug 13 2007 Peter Jones <pjones@redhat.com> - 11.1.2.64-1
- Fix memory size comparison in PAE test.
  Related: rhbz#207573
- Add e1000e and igb modules.
  Resolves: rhbz#251733
  Resolves: rhbz#251735

* Fri Aug 10 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.63-1
- Disable zFCP device before removing LUN (bhinson AT redhat DOT com)
  Resolves: rhbz#249341

* Wed Aug 08 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.62-1
- Add a symlink in /etc to /mnt/runtime/etc/yum, handle kABI
  requires/provides (dlehman)
  Resolves: rhbz#241412
- Fix converting UI selections into which drives should be used for
  partitioning (clumens)
  Resolves: rhbz#247997

* Mon Aug 06 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.61-1
- Honor ip=<val>/ipv6=<val>/noipv4/noipv6 boot parameters and skip the
  loader configuration if enough settings are passed on the boot line
  Resolves: rhbz#246603

* Fri Jul 20 2007 Peter Jones <pjones@redhat.com> - 11.1.2.60-1
- Hopefully fix usb-storage reloading.  Still needs testing
  Related: rhbz#247830
- Ignore failure to unmount /mnt/source if we don't think there's a real mount
  (dlehman)
  Related: rhbz#223059
- Prevent SIGSEGV when going back from NFS entry box after manual IPv4
  configuration (dcantrell)
  Resolves: rhbz#248075
- Fix the timezone window (dcantrell)
  Resolves: rhbz#248928

* Wed Jul 18 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.59-1
- Correctly discover underlying physical disks for RAID devices (pjones)
  Resolves: rhbz#248616
- Mark iSCSI root with _netdev mount option (markmc AT redhat DOT com)
  Resolves: rhbz#244994
- Clear screen after post-install NIC settings
  Resolves: rhbz#248130
- Display mpath model and unit info on text partitioning screen
  Related: rhbz#185852

* Mon Jul 16 2007 Peter Jones <pjones@redhat.com> - 11.1.2.58-1
- Only skip redhat-lsb during dependency resolution if it's not
  the only thing left
  Resolves: rhbz#248195

* Thu Jul 12 2007 Peter Jones <pjones@redhat.com> - 11.1.2.57-1
- Only use GPT when we've got really big disks
  Resolves: rhbz#247830
- Allow ia64 virt installs without "debug" option
  Resolves: rhbz#246718
- Copy firmware files correctly from driver disks
  Related: rhbz#224076

* Thu Jul 12 2007 Peter Jones <pjones@redhat.com> - 11.1.2.56-1
- Save "nodmraid" option so mkinitrd won't turn it on during boot
  Related: rhbz#185852
- Don't mark partitions as bootable on GPT disks unless we're using EFI
  Related: rhbz#130236
- Fix size display errors with large disks
  Related: rhbz#130236

* Tue Jul 10 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.55-1
- Display mpath model information on the custom partitioning screen
  Related: rhbz#185852

* Tue Jul 10 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.54-1
- Add missing colon on an if statement in getMpathModel()
  Related: rhbz#185852
- Do not add extra 'mapper/' to fulldev in getMpathModel()
  Related: rhbz#185852

* Tue Jul 10 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.53-1
- Use scsi_id to gather WWID info in getMpathModel()
  Related: rhbz#185852
- Do not strip 'mapper/' from mpath device names in the partitioning UI
  Related: rhbz#185852

* Mon Jul 09 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.52-1
- If we have seen an mpath device, do not gather its WWID again
  Related: rhbz#185852
- Fix code indentation errors
  Related: rhbz#185852
- Fix errors in the getMpathInfo() function when executing multipath
  Related: rhbz#185852
- Display mpath devices without the 'mapper/' text
  Related: rhbz#185852
- Get WWID from bindings file if multipath command returns nothing
  Related: rhbz#185852
- Require that USB devices remain stable for a longer time period (pjones)
  Resolves: rhbz#222684

* Mon Jul 09 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.51-1
- Ignore empty lines when collecting WWIDs per mpath device
  Related: rhbz#185852
- Comment out existing blacklist and blacklist_exceptions blocks in the
  /etc/multipath.conf file
  Related: rhbz#185852
- Reset SELinux file contexts on multipath.conf and bindings files
  Related: rhbz#185852

* Fri Jul 06 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.50-1
- Read default multipath.conf values from either the target system or the
  anaconda stage2 environment.  Make sure we only read one WWID per mpath
  alias and log an error if we didn't.
  Related: rhbz#185852
- Install the PAE kernel when applicable (e.g., >4GB memory)
  Resolves: rhbz#207573
- Read mpathNNN devices when generating the bindings and multipath.conf files
  Related: rhbz#185852
- Make sure the partitioning UI screen displays WWID and model information
  for multipath devices
  Related: rhbz#185852
- Use GPT on all architectures with non-boot disks >=2TB (pjones)
  Resolves: rhbz#130236

* Thu Jul 05 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.49-1
- Generate multipath bindings and multipath.conf before package
  installation.  Use scsi_id to collect WWIDs rather than the multipath
  command to maintain consistency with what pyblock has done.
  Related: rhbz#185852

* Fri Jun 29 2007 Chris Lumens <clumens@redhat.com> - 11.1.2.48-1
- Support new driver disk repo layout.
  Resolves: rhbz#213318
- Add missing TEXT_EDIT_BUTTON constants back (dcantrell).
  Resolves: rhbz#245606.
- Fix a traceback when writing out multipath configs (dcantrell).
  Related: rhbz#185852.

* Thu Jun 28 2007 Chris Lumens <clumens@redhat.com> - 11.1.2.47-1
- Fix traceback when writing out repo lines.
  Resolves: rhbz#246084

* Wed Jun 27 2007 Chris Lumens <clumens@redhat.com> - 11.1.2.46-1
- Create package header directory since yum doesn't anymore (katzj).
  Resolves: rhbz#245918
- Write out repo lines to anaconda-ks.cfg.
  Resolves: rhbz#206152
- Enable multipathd on mpath installs (dcantrell).
  Resolves: rhbz#243421
- Pull scsi_id from /lib/udev, include kpartx and mpath commands (dcantrell).
  Resolves: rhbz#185852
- Display model information in the UI for mpath devices (dcantrell).
  Resolves: rhbz#208341
- Add nspr libraries and additional nss libraries.
  Related: rhbz#245215
- Fox error reporting in iscsi connection code (pjones).

* Tue Jun 26 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.45-1
- Add keyutils-libs (clumens)
  Resolves: rhbz#245734
- Set up and use yum backend plugins (dlehman)
  Resolves: rhbz#241412
- Install debuginfo packages (james.antill)
  Resolves: rhbz#236033

* Tue Jun 26 2007 James Antill <jantill@redhat.com> - 11.1.2.44-2
- Remove default exclude for debuginfo.
- Resolves: rhbz#236033

* Fri Jun 22 2007 Chris Lumens <clumens@redhat.com> - 11.1.2.44-1
- Fix typo in multipath part of making stage2 image (dcantrell).
- Include the scsi_id command in the stage2 image (dcantrell).
  Resolves: rhbz#185852
- Write out a minimal /etc/multipath.conf (dcantrell).
  Related: rhbz#185852

* Thu Jun 21 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.43-1
- Correct iSCSI portal discovery
  Resolves: rhbz#233029

* Thu Jun 21 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.42-1
- Handle ip=dhcp correctly so kickstart files are fetched automatically
  Resolves: rhbz#244418
- Write newline after NETWORKING_IPV6=yes line
  Resolves: rhbz#226911
- Make sure libnss3.so is included in the stage2 image
  Resolves: rhbz#245215

* Wed Jun 20 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.41-1
- Include Xen block devices in the blacklist_exception block
  Related: rhbz#243527
- Remove the lvm.conf filter modification to avoid regression
  Related: rhbz#243531
- Fix traceback when looking for multipath devices to collect WWIDs for
  Related: rhbz#185852

* Tue Jun 19 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.40-1
- Add libselinux-python to the stage2 image (clumens)
  Resolves: rhbz#244892
- Copy static multipath commands in to stage2 image
  Related: rhbz#185852
- Filter /dev/mapper/mpath* and /dev/mpath* in lvm.conf
  Related: rhbz#185852
- Run /sbin/multipath and copy generated bindings file to target system,
  populate blacklist_exception block in multipath.conf with WWIDs from
  generated bindings file
  Related: rhbz#185852

* Mon Jun 18 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.39-1
- Flush driveDict so zFCP are picked up after being brought online
  Resolves: rhbz#236903
- Warn user when more than 15 partitions found on a libata-controlled disk
  Resolves: rhbz#238858
- Add mpath filters to lvm.conf on target system
  Resolves: rhbz#243531
- Make sure target system has multipath bindings file, add multipath WWIDs
  to blacklist_exception block in multipath.conf
  Resolves: rhbz#243527
- Always print device node name for mpath devices in fstab
  Resolves: rhbz#243532

* Thu Jun 14 2007 Chris Lumens <clumens@redhat.com> - 11.1.2.38-1
- Import tempfile to fix kickstart install tracebacks.
  Resolves: rhbz#244240

* Tue Jun 12 2007 David Cantrell <dcantrell@redhat.com> - 11.1.2.37-1
- Add support for Areca RAID controllers (clumens)
  Resolves: rhbz#238014
- Pass -br to the X server so there is no more hatch (clumens)
  Resolves: rhbz#195919
- Echo 1 to each zFCP LUN to make entire device available (dcantrell)
  Resolves: rhbz#207097
- Prevent static network configuration from failing (dcantrell)
  Resolves: rhbz#221660
- Allow user to skip entering a gateway or nameserver when adding an iSCSI
  address (dcantrell)
  Resolves: rhbz#235824
- Do not log errors when unmounting /mnt/source if it was not supposed to
  be mounted in the first place (dlehman)
  Resolves: rhbz#223059
- Handle F13 shortcut key on installation key dialog (dlehman)
  Resolves: rhbz#210673
- Create nodes for and probe for tape drives (dlehman)
  Resolves: rhbz#218816
- Improve configuration screens for systems with multiple NICs (dcantrell)
  Resolves: rhbz#218200
- Per-interface IPv4 and IPv6 configuration (dcantrell)
  Resolves: rhbz#213110
  Related: rhbz#218200
- Add logging for yum logging (katzj)
  Resolves: rhbz#212259
- Only ask user to run VNC is Xvnc is present (dcantrell)
  Resolves: rhbz#217563
- Add /sbin/sfdisk (dcantrell)
  Resolves: rhbz#224297
- For /dev/hvc0 terminals, set TERM to vt320 (dcantrell)
  Resolves: rhbz#219556
- Set DHCPv6_DISABLE flag when using IPv6 auto neighbor discovery (dcantrell)
  Resolves: rhbz#231645
- Handle more than 10 Ethernet interfaces (dcantrell)
  Resolves: rhbz#230525
- Support OSA layer 2 networking on zSeries (bhinson)
  Resolves: rhbz#233376
- Handle ksdevice=BOOTIF correctly (dcantrell)
  Resolves: rhbz#209284
- Fix text wrap width in auto partitioning text mode screen (dlehman)
  Resolves: rhbz#221791
- Correctly count SCSI disk devices (dlehman)
  Resolves: rhbz#230526
- Include /usr/sbin/dmidecode on ia64 (dlehman)
  Resolves: rhbz#232947
- Bind mount /dev/pts in rescue mode (dlehman)
  Resolves: rhbz#228714
- Do not ignore productpath in pkgorder (dlehman)
  Resolves: rhbz#230487
- Describe 'nfs --opts' in kickstart-docs.txt (clumens)
  Resolves: rhbz#234187
- Sanity check network info on zSeries (dcantrell)
  Resolves: rhbz#234152
- Do not bring up network in stage 2 if it's already up (dcantrell)
  Resolves: rhbz#232400
- Do not traceback when trying to remove the /mnt/sysimage tree (dcantrell)
  Resolves: rhbz#227650
- Write correct infor to /etc/sysconfig/network (dcantrell)
  Resolves: rhbz#222147
- If custom partitioning is selected, make drive selection non
  sensitive (clumens)
  Resolves: rhbz#219207
- Do not traceback if users neglects to enter an lvsize (clumens)
  Resolves: rhbz#221253
- Do not load a module when the kickstart device line is incorrect (clumens)
  Resolves: rhbz#227510
- Handle errors resulting from malformed repositories (clumens)
  Resolves: rhbz#219274
- Remove all invalid RAID requests when using kickstart (clumens)
  Resolves: rhbz#235279
- Avoid traceback getting the PID of iscsiadm (clumens)
  Resolves: rhbz#223257
- Make sure kickstart scripts execute with correct working dir (clumens)
  Resolves: rhbz#237317
- Support multiple ksappend lines (clumens)
  Resolves: rhbz#222201
- Write out fstab after migrate (clumens)
  Resolves: rhbz#223215
- Make the packages section in anaconda-ks.cfg match UI selections (clumens)
  Resolves: rhbz#227383, rhbz#231121, rhbz#235881
- Copy volume group format attribute to new request (clumens)
  Resolves: rhbz#217585
- Use /dev/ nodes for probing RAID superblocks (clumens)
  Resolves: rhbz#208970
- Put more space between device description and the stripe for tall
  languages (clumens)
  Resolves: rhbz#217294
- Add netxen_nic driver (clumens)
  Resolves: rhbz#230245
- Provide detailed disk info in text mode partitioning screen (dcantrell)
  Resolves: rhbz#235054
- If wrong interface is selection, allow user to choose another one (clumens)
  Resolves: rhbz#213787
- Focus installation key text box and populate fields correctly (dlehman)
  Resolves: rhbz#223831
- Make sure the regkey settings are written to anaconda-ks.cfg (dlehman)
  Resolves: rhbz#221450
- Select kernel-xen-devel when optional packages selected (dlehman)
  Resolves: rhbz#226784
- Fix typo in message shown when user skips entering the install key (dlehman)
  Resolves: rhbz#224491
- If autopart selection is custom, make sure review checkbox is active and
  not sensitive. (dlehman)
  Resolves: rhbz#220951
- Write NETWORKING_IPV6=no to /etc/sysconfig/network if IPv6 is disabled
  during installation. (dcantrell)
  Resolves: rhbz#226911
- Fix input validation loop in manual network config in loader
  Resolves: rhbz#223193 (dcantrell)
- Make "description" translate correctly (pjones)
  Resolves: rhbz#216067

* Thu Feb  1 2007 Peter Jones <pjones@redhat.com> - 11.1.2.36-1
- Fix traceback when using text mode with a language that we can't display
  Resolves: #225528

* Fri Jan 26 2007 Peter Jones <pjones@redhat.com> - 11.1.2.35-1
- Don't set the migration flag for FAT labels if we're formatting the
  partition
  Resolves: #223898
- Process directories recursively when relabelling
  Resolves: #218791

* Fri Jan 26 2007 Jeremy Katz <katzj@redhat.com> - 11.1.2.34-2
- fix ordering for split media installs (#223090)

* Wed Jan 24 2007 Peter Jones <pjones@redhat.com> - 11.1.2.34-1
- The PAE kernel isn't named according to the normal convention, so we need
  "kernel-PAE" instead of "kernel-pae" in the list for grub.
  Resolves: #223941

* Tue Jan 23 2007 Peter Jones <pjones@redhat.com> - 11.1.2.33-1
- Handle FAT/VFAT labels on upgrade better 
  Resolves: #223890
- Include kernel-pae in the list of kernels we set up in grub.conf (#223941)

* Mon Jan 22 2007 Peter Jones <pjones@redhat.com> - 11.1.2.32-1
- Don't try to migrate fat/vfat labels if there's no fstab yet (#223554).
- Always dasdfmt when we're relabeling a dasd device.
  Resolves: #223492
- Don't use FAT/VFAT labels that are in use on other filesystems
  Resolves: #218957

* Fri Jan 19 2007 Peter Jones <pjones@redhat.com> - 11.1.2.31-1
- Fix typo in yesterday's iscsi fix
  Resolves: #223257

* Thu Jan 18 2007 Peter Jones <pjones@redhat.com> - 11.1.2.30-1
- Fix iscsi shutdown's "ps" call
  Resolves: #223257
- Fix "halt" kickstart directive
  Resolves: #222953

* Wed Jan 17 2007 Peter Jones <pjones@redhat.com> - 11.1.2.29-1
- fix rhpl import 
  Resolves: #222991

* Tue Jan 16 2007 Peter Jones <pjones@redhat.com> - 11.1.2.28-1
- Use a GtkWindow for the release notes viewer (katzj)
  Resolves: #220418
- Add pirut to our textdomain so strings get translated (katzj)
  Resolves: #216067
- Don't log a pvrequest's "drive" attribute, since they don't all have them
  Resolves: #221992
- Fix "clearpart" and such to only happen once
  Resolves: #220021
- Handle multiple repo paths better
  Resolves: #221146
  Resolves: #221260
- label fat filesystems for /boot/efi on ia64
  Resolves: #218957
- Don't overwrite hdinstall partition when "clearpart --all --initlabel" is
  in ks.cfg (dlehman)
  Resolves: #220331
- Fix depsolver progress meter problems when there's not enough space (dlehman)
  Resolves: #215493
- Don't show "unsupported language" error when not in interactive mode (clumens)
  Resolves: #222096
- Change default mpath option to disabled
  Related: #219843
- Remove packages pulled in for deps when there's a space error (dlehman)
  Resolves: #222894
- Disable betanag (katzj)

* Thu Jan  4 2007 Peter Jones <pjones@redhat.com> - 11.1.2.27-1
- Include cdroms in the scsi disk count (katzj, #207336)
- Translation display fixes (katzj, #216067)
- Wait longer for usb floppy access (#211222)
- Make the package repo path list right (#221260)

* Wed Jan  3 2007 Peter Jones <pjones@redhat.com> - 11.1.2.26-1
- Fix bug trying to find repomd files (#221146)
- Don't do 'clearpart' stuff on fsset if we're not in a kickstart (#221090)

* Tue Jan  2 2007 Peter Jones <pjones@redhat.com> - 11.1.2.25-1
- Turn off multipath support by default (enable with "mpath" during boot)
- Don't clear partitions if it's already been done (#220021)
- Handle upgrade conditionals better (pnasrat, #218909, #214747)
- Handle new repo dict format (dlehman, #220241, #220326)
- Don't log messages about VT tech preview on s390 and ppc (dlehman, #220236)

* Mon Dec 18 2006 Peter Jones <pjones@redhat.com> - 11.1.2.24-1
- Make sure reg keys are written out un upgrade (dlehman, #219791)
- handle 'regkey --skip' correctly in kickstart (dlehman, #219544)
- Allow users to go back and change regkeys (dlehman, #219361)
- Do not accept regkeys that don't match the install media (dlehman, #219823)
- Honor dhcpclass parameter in isys (dcantrell, #220057)
- Pick paths better for url iso installs (#219205)

* Fri Dec 15 2006 David Cantrell <dcantrell@redhat.com> - 11.1.2.23-1
- Use subprocess in execConsole (clumens, #210481, #216155)
- Leave a way for mkinited to discover lack of mpath (pjones, #219843)
- Pass 'anaconda' to instClass.installDataClass() (pjones, #219793)
- Use intf, not self.anaconda.intf in partedUtils
- Handle DiskSet instantiation from LabelFactory when anaconda=None
- Resolves: rhbz#210481 rhbz#216155 rhbz#219843 rhbz#219793

* Thu Dec 14 2006 Peter Jones <pjones@redhat.com> - 11.1.2.22-1
- Only show information appropriate to the install class specified by the
  reg key (dlehman, #218967)
- Fix dasd formatting (dcantrell, #218861)
- Fix iscsi portal discovery (#216164)
- Update xvc0 major/minor (katzj, #218050)
- Fix device node creation in 'rescue' (clumens)
- Fix zFCP device addition (dcantrell, #210635)

* Wed Dec 13 2006 Peter Jones <pjones@redhat.com> - 11.1.2.21-1
- Handle reg keys with dashes (dlehman, #218716)
- Don't traceback with no iscsi (katzj, #218513)
- Unmount cdrom after installation when using local stage2 during http
  install (dlehman)
- Fix typo in iscsi code (katzj, #218513)
- Remove LIBUSER_CONF from the environment before running
  post (clumens, #218213)
- Don't allow virt by default on ia64 (#215429)
- Fix lvm off-by-one-extent problems with previously created volume groups
  (pjones, #217913)

* Wed Dec  6 2006 Peter Jones <pjones@redhat.com> - 11.1.2.20-1
- Remove language choices for which there is no font (katzj, #217498)
- Add stex module (katzj, #209179)
- Fix debug output (pnasrat, #217751, #217774)

* Fri Dec  1 2006 Dennis Gregorovic <dgregor@redhat.com> - 11.1.2.19-2
- rebuild
- Related: rhbz#217861

* Wed Nov 29 2006 Chris Lumens <clumens@redhat.com> - 11.1.2.19-1
- Don't always write out xconfig and monitor lines (#211977).
- Pull in xinf files from X driver packages on url images.
- Fix for changed API (katzj, #217673, #217689).

* Tue Nov 28 2006 Chris Lumens <clumens@redhat.com> - 11.1.2.18-1
- Fix registration key dialog (katzj).
- Base shown tasks on registration key (katzj).
- Init wreq structure before use (dcantrel, #215367).
- Fetch new release notes file on language change (#217501).
- Add ipv6= command line argument (dcantrel).
- Rework loader network config screen (dcantrel, #213108, #213112).
- Disable testing registration keys when out of beta (katzj, #217360).
- Fix si_LK timezone (katzj, #217288).
- Set the right home directory on kickstart user command (#216681).
- Allow correcting kickstart file location on error/typo (#216446).
- Check for .discinfo instead of using a static number (pjones, #214787).
- Nodes property typo (pnasrat, #216410).
- Only set broadcast and network addr if ipv4 is enabled (dcantrel, #215451).

* Fri Nov 17 2006 Chris Lumens <clumens@redhat.com> - 11.1.2.17-1
- Preserve drive order specified in kickstart (#214881).
- Be smarter about checking if iscsi is available (katzj, #216128).
- Install language support packages in text mode (nasrat, #215867).
- Fix kernel naming (katzj, #215746).
- Fix handling of iscsiadm output and activation of devices (pjones).
- Depsolve on optional/non-grouped packages (nasrat, #214848).
- Update kickstart documentation.
- Make sure source is unmounted on image installs before %post (#214677).
- Use mode 0600 for install-num file (katzj, #214853).

* Thu Nov 09 2006 Paul Nasrat <pnasrat@redhat.com> -11.1.2.16-1
- Fix traceback due to incorrect no discs (#214787)

* Wed Nov  8 2006 Peter Jones <pjones@redhat.com> - 11.1.2.15-1
- Fix segfault when there's no EDD, as on ppc (#214653)
- Always skip networking screen on kickstart installs (clumens, #214584)
- Update install method docs (clumens, #214159)

* Mon Nov  6 2006 Peter Jones <pjones@redhat.com> - 11.1.2.14-1
- Avoid traceback with PReP partitions on disks that aren't currently
  in use (clumens, #211098)
- Fix traceback when all space is in use (ddearau AT us.ibm.com, #213616)
- Fix text mode traceback (katzj, #213869)
- Use better API for network configuration dialog (katzj, #213356)

* Fri Nov 03 2006 Chris Lumens <clumens@redhat.com> - 11.1.2.13-1
- Install in text mode if a KVM confused X autodetection.

* Fri Nov 03 2006 Paul Nasrat <pnasrat@redhat.com> - 11.1.2.12-1
- Fix traceback on ftp loopback iso installs (#212014)
- Enable IPv6 dns support in loader (dcantrell)

* Wed Nov  1 2006 Peter Jones <pjones@redhat.com> - 11.1.2.11-1
- Fix localhost6 line in /etc/hosts (dcantrell, #210050)
- Add more fonts to the install image (katzj, #207428)
- Remove i386 dmraid on multi-arch upgrades (katzj, #209011)
- Improve split ISO URL installs (clumens)
- Fix line wrapping in clearpart (clumens, #213425)
- Always set an active value in the LVM PE size combo box (clumens, #212317)
- Don't try to clear partitions on drives in the skippedList (clumens)
- Don't try to resolve port numbers from urls as hostnames (clumens, #212622)

* Fri Oct 27 2006 Peter Jones <pjones@redhat.com> - 11.1.2.10-1
- Don't use keepalive sockets when they won't be reused (#212571)

* Fri Oct 27 2006 Jeremy Katz <katzj@redhat.com> - 11.1.2.9-1
- Fix install key handling (#212548)
- Catch hard drives that don't exist (clumens, #212377)
- Fix typo for slovak keyboard (#212304) 

* Thu Oct 26 2006 Chris Lumens <clumens@redhat.com> - 11.1.2.8-1
- Fall over to the next mirror correctly (#208077, #212014).

* Wed Oct 25 2006 Jeremy Katz <katzj@redhat.com> - 11.1.2.7-1
- Fix zfcp (#210094)
- Remove unneeded whiteout
- Fix a case where we might have leaked an fd (#212191)

* Tue Oct 24 2006 Jeremy Katz <katzj@redhat.com> - 11.1.2.6-1
- Add Sinhala (#207426)
- Fix a traceback in shell exec (pnasrat, #211830)
- Write out proper ipv6 localhost in /etc/hosts (dcantrel, #211800)
- Merge swap/graphical limits from fc6 (#211649)
- Fix canceling with iscsi (#211996)
- Fix static IPs with iscsi/repo adding
- Fix use of repos on upgrade (#211547)
- Add real key format (dlehman, #207752)

* Fri Oct 20 2006 David Cantrell <dcantrell@redhat.com> - 11.1.2.5-1
- Build against libdhcp-1.16
- Continue if vname or vparm are NULL in readNetInfo (#211502)
- Add fonts-telugu (katzj, #207428)
- Fix install progress bar/window dimensions (katzj, #211526)
- Don't specify a stdout of stderr for shells on zSeries (clumens, #210481)
- Use execConsole function to run shells (clumens)
- Only use netlink messages with ARP Ethernet headers (katzj, #210195)
- Force swap formatting on ppc (pnasrat, #206523)
- Don't traceback without a key in cmdline mode (katzj, #211476)
- Pass noipv4/noipv6 settings from stage 1 to stage 2 (#208334)
- Correct --onbiosdisk handling (clumens, #210705)
- Keep runlevel 3 if doing a VNC install (clumens, #211318)
- Don't use unicode line drawing on vt100-nav terminals (katzj, #208374)
- Remove multilib packages (pnasrat, #209011)

* Tue Oct 17 2006 David Cantrell <dcantrell@redhat.com> - 11.1.2.4-1
- yum fix retry on failure (katzj, #211117)
- Fix ordering for iSCSI tools on CD installs (katzj, #208832)
- Only go back a screen from regKeyScreen is possible (katzj, #211101)
- Support --skip for instkey (katzj)
- Parse /tmp/netinfo correctly on zSeries (#207991)
- Fix for virtualization being the group instead of xen (katzj)

* Mon Oct 16 2006 Jeremy Katz <katzj@redhat.com> - 11.1.2.3-1
- Better regex for finding ISO loopback mounts (clumens, #205133)
- Setup baseurl better for additional repos (clumens, #210877)
- Add qla2400 and qla2xxx to late module load list (#210886)
- Write out zfcp to anaconda-ks.cfg
- Write out iscsi to anaconda-ks.cfg
- Preserve installation number in anaconda-ks.cfg and on the system (#207029)
- Add support for 'key' directive in kickstart for installation number
- Handle non-base repos which may or may not exist better (#202810)
- Fix zfcp (#210094)
- Take up more space for package descriptions (#210531)
- New installation number dialog (#207752)

* Thu Oct 12 2006 David Cantrell <dcantrell@redhat.com> - 11.1.2.2-1
- Fix layout where extra repo selection box is not displayed (clumens)
- Fix desktop upgrade (katzj, #210408)
- Don't start a new process group and do exit(0) instead of return
  after receiving SIGTERM (pjones)
- Only do auditDaemon if we're not in test or rootpath mode (pjones)
- Error only when checking the initiator name (katzj, #210347)
- Don't force gateway and DNS values (#200029)
- Set IPv6 entry box sensitivity correctly in text mode
- Initialize useIPv4 and useIPv6 correctly when existing net info is there

* Wed Oct 11 2006 Chris Lumens <clumens@redhat.com> - 11.1.2.1-1
- Ignore basepath in getHeader to fix CD installs (pnasrat).
- Fix package installation.

* Tue Oct 10 2006 Jeremy Katz <katzj@redhat.com> - 11.1.2.0-1
- Allow setting the language to something not in lang-table (clumens, #176538)
- Fix split media (pnasrat)
- Fix going back from advanced bootloader (clumens, #210190)
- Bump early swap to be higher
- Add Telugu (#207428)
- Update edd support (Rez Kabir, #207331)
- Sleep hacks for usb-storage (zaitcev, #207336)

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

