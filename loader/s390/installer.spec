Name: installer
Version: 0.13
Release: 1
Summary: Tool for configuring the package source for Red Hat Linux for S/390.
URL: http://www.redhat.com/
Source: %{name}-%{version}.tar.gz
License: GPL
Group: System Environment/Base
Prefix: %{_prefix}
BuildRoot: %{_tmppath}/%{name}-root
ExclusiveArch: s390 s390x

%description
Tools for installing and configuring Red Hat Linux for S/390.

%prep
%setup -n installer

%build
make CFLAGS="$RPM_OPT_FLAGS"

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR="$RPM_BUILD_ROOT"

%files
%defattr(-,root,root)
/usr/bin/*

%clean
rm -rf $RPM_BUILD_ROOT $RPM_BUILD_DIR/%{name}-%{version}

%changelog
* Thu Dec 28 2000 Bernhard Rosenkraenzer <bero@redhat.com>
- initial RPM
