ExcludeArch: ppc64
Name: anaconda
Version: 10.0.3.6
Release: 1
License: GPL
Summary: Graphical system installer
Group: Applications/System
Source: anaconda-%{PACKAGE_VERSION}.tar.bz2
BuildPreReq: pump-devel >= 0.8.20, kudzu-devel >= 1.1.52, pciutils-devel, bzip2-devel, e2fsprogs-devel, python-devel gtk2-devel rpm-python >= 4.2-0.61, newt-devel, rpm-devel, gettext >= 0.11, rhpl, booty, libxml2-python, zlib-devel, bogl-devel >= 0:0.1.9-17, bogl-bterm >= 0:0.1.9-17, elfutils-devel, beecrypt-devel, libselinux-devel >= 1.6, xorg-x11-devel
%ifarch i386
BuildRequires: dietlibc
%endif
Requires: rpm-python >= 4.2-0.61, rhpl > 0.63, parted >= 1.6.3-7, booty, kudzu
Requires: pyparted, libxml2-python
Requires: anaconda-help, system-logos
Obsoletes: anaconda-images <= 10
Url: http://fedora.redhat.com/projects/anaconda-installer/

BuildRoot: %{_tmppath}/anaconda-%{PACKAGE_VERSION}

%description
The anaconda package contains the program which was used to install your 
system.  These files are of little use on an already installed system.

%package runtime
Summary: Red Hat Linux installer portions needed only for fresh installs.
Group: Applications/System
AutoReqProv: false
Requires: libxml2-python

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

