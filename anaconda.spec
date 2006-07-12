ExcludeArch: ppc64
Name: anaconda
Version: 9.1.6.15
Release: 1.RHEL
License: GPL
Summary: The Red Hat Linux installation program.
Group: Applications/System
Source: anaconda-%{PACKAGE_VERSION}.tar.bz2
BuildPreReq: pump-devel >= 0.8.15, kudzu-devel >= 1.1.22.15-1, pciutils-devel, bzip2-devel, e2fsprogs-devel, python-devel gtk2-devel rpm-python >= 4.2-0.61, newt-devel, rpm-devel, gettext >= 0.11, modutils-devel, rhpl, booty, libxml2-python, zlib-devel, bogl-devel >= 0:0.1.9-17, bogl-bterm >= 0:0.1.9-17, elfutils-devel, beecrypt-devel
%ifarch i386
BuildRequires: dietlibc
%endif
Prereq: chkconfig /etc/init.d
Requires: rpm-python >= 4.2-0.61, rhpl > 0.63, parted >= 1.6.3-7, booty, libxml2-python
Url: http://rhlinux.redhat.com/anaconda/

BuildRoot: %{_tmppath}/anaconda-%{PACKAGE_VERSION}

%description
The anaconda package contains the Red Hat Linux installation program.  
These files are of little use on an already installed system.

%package runtime
Summary: Red Hat Linux installer portions needed only for fresh installs.
Group: Applications/System
AutoReqProv: false

%description runtime
The anaconda-runtime package contains parts of the Red Hat Linux
installer which are needed for installing new systems. These files are
used to build Red Hat Linux media sets, but are not meant for use on
already installed systems.

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
* Wed Jul 12 2006 Peter Jones <pjones@redhat.com> - 9.1.6.15-1.RHEL
- Make the driver image fit on a disk again (#192005).  Again.

* Tue Jun 20 2006 Peter Jones <pjones@redhat.com> - 9.1.6.14-1.RHEL
- Make the driver image fit on a disk again (#192005)

* Tue May 30 2006 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.13-2.RHEL
- Rebuild against later kudzu for (#140772)

* Thu May 25 2006 Peter Jones <pjones@redhat.com> - 9.1.6.13-1.RHEL
- Add adp94xx driver to whitelist (#192951)

* Thu May 11 2006 Peter Jones <pjones@redhat.com> - 9.1.6.12-1.RHEL
- Fix size checking of http header array (#191184).

* Fri May 05 2006 Peter Jones <pjones@redhat.com> - 9.1.6.11-1.RHEL
- Use -Os in the loader after all, or else boot images are too large (#190835).
- Use a dynamic buffer for httpGetFileDesc in the loader (#188089).

* Mon May 01 2006 Peter Jones <pjones@redhat.com> - 9.1.6.10-1.RHEL
- Correct module info parsing on driver disks (dcantrel, #164549).
- Add nicdelay= boot parameter (#162693).
- Handle control characters correctly in rescue mode shell (dcantrel, #126620).
- Set controlling terminal for rescue mode (dcantrel, #126620).
- Don't use -Os in the loader makefile (#188089).
- Allow vfat driver disks (#186400).

* Tue Nov 29 2005 Chris Lumens <clumens@redhat.com> - 9.1.6.9-1.RHEL
- Set HWADDR in ifcfg-eth* files (#159972).
- Fix video card selection in text installs (#168807).
- Fix smp detection for dual-core (pnasrat, #169266).
- Fix noparport option (pnasrat, #169135).
- Fix kickstart parsing in sections (pnasrat, #165865).
- Fix for no pkgorder run (pnasrat, #170721).
- Add bnx2 (pjones).

* Tue Sep 20 2005 Peter Jones <pjones@redhat.com> - 9.1.6.8-2.RHEL
- Rebuild for newer kudzu (#168498)

* Thu Aug 04 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.8-1.RHEL
- Fix for DASD partitioning (#137920)

* Tue Jul 19 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.7-1.RHEL
- Fix missing import (#163616)

* Mon Jul 18 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.6-1.RHEL
- Fixup drvblock overflow prevention (#163080)

* Mon Jul 18 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.5-1.RHEL
- Fixup remove isplash bootdisk (#143237)

* Fri Jul 15 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.4-1.RHEL
- Don't overflow drvblock (#163080)
- Splash on isolinux as bootdisk too small (#143237)

* Wed Jul 13 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.3-1.RHEL
- multiple NICs fixes for kickstart (clumens, #158556)

* Tue Jul 12 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.2-1.RHEL
- U6 build fixes

* Tue Jul 12 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.1-1.RHEL
- U6 Fix autopartiioning on i5 (#137920)
- U6 fix braces for MTU fix

* Tue Jul 12 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.6.0-1.RHEL
- U6 restore syslinux splash (#143237)
- U6 s390 initrd size (katzj, #149029)
- U6 support for MTU in loader (katzj, #155414)
- Partition ks.cfg section - correctly quote fstypes (katzj, #159193)
- Remove /var/lib/rpm late (#138884)

* Mon May 09 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.5.8-1.RHEL
- U5 backport n.arch logic error

* Mon Apr 11 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.5.7-1.RHEL
- U5 backport n.arch fix (#139824)

* Tue Mar 29 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.5.6-1.RHEL
- AHCI support (#152181)

* Wed Mar  2 2005 Jeremy Katz <katzj@redhat.com> - 9.1.5.5-1.RHEL
- Support 2 TB filesystems (#116286)
- Don't use vesa for all graphics adapters with ftp/http installs (#144128)

* Mon Feb 28 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.5.4-1.RHEL
- Perform ethtool setup in more places (#145422)

* Sat Feb 19 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.5.3-1.RHEL
- Add forcedeth support (#148868
- Add 3w-9xxx (katzj, #128651)

* Tue Feb 08 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.5.2-1.RHEL
- Only configure ksdevice if no --device (#138852)
- backport changes from Kristian Høgsberg <krh@redhat.com> 
  for usb mouse crashes (#139568)

* Thu Jan  6 2005 Jeremy Katz <katzj@redhat.com> - 9.1.5.1-1.RHEL
- Support parsing of pxelinux IPAPPEND (bnocera, #134054)
- Load ibmvscsic late (#137920)
- Add command line option "latefcload" to load known fiberchannel controllers 
  later than other modules.  Should help some users with fiberchannel 
  controllers so that they don't end up with their SAN as /dev/sda

* Tue Jan 04 2005 Paul Nasrat <pnasrat@redhat.com> - 9.1.5.0-1.RHEL
- Backport ignoredisk (#140464)
- Fix quoting for ETHTOOL_OPTS (#142041)
- U5 backport n.arch support (#139824)

* Wed Nov 10 2004 Jeremy Katz <katzj@redhat.com> - 9.1.4.1-1.RHEL
- Don't ask about manually loading devices if we have all 
  virtual hardware (#135108)
- Make it so that installs from USB storage don't explode (#135492)
- Tweaks to the pci.ids stuff so that the splash screen should fit (notting)
- Fix segfault loading modules (#137182)
- ipr should be similar to ibmsis in special casing of auto-partitioning 
  stuff on ppc hardware
- Make serial imply nofb (#134167)

* Wed Oct  6 2004 Jeremy Katz <katzj@redhat.com> - 9.1.4.0-4.RHEL
- take three

* Tue Oct  5 2004 Jeremy Katz <katzj@redhat.com> - 9.1.4.0-3.RHEL
- another attempt to get bootdisk.img to fit

* Tue Oct  5 2004 Jeremy Katz <katzj@redhat.com> - 9.1.4.0-2.RHEL
- get boot disks fitting again

* Fri Sep 24 2004 Jeremy Katz <katzj@redhat.com> - 9.1.4.0-1.RHEL
- Support using ksdevice=macaddr (#130605)
- Don't sig11 if nfs server isn't running (#131746)
- Use pci.ids instead of requiring in pcitable (notting)
- Update scripts to handle multilib gtk2/pango

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

