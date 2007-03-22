all:

install:
	mkdir -p $(DESTDIR)/usr/bin
	mkdir -p $(DESTDIR)/usr/sbin
	mkdir -p $(DESTDIR)/usr/share/applications
	mkdir -p $(DESTDIR)/etc/pam.d $(DESTDIR)/etc/security/console.apps
	mkdir -p $(DESTDIR)/etc/X11/xinit/xinitrc.d

	install -m 0755 liveinst.sh $(DESTDIR)/usr/sbin/liveinst
	ln -s consolehelper $(DESTDIR)/usr/bin/liveinst

	install -m 0644 liveinst.pam $(DESTDIR)/etc/pam.d/liveinst
	install -m 0644 liveinst.console $(DESTDIR)/etc/security/console.apps/liveinst

	install -m 0644 liveinst.desktop $(DESTDIR)/usr/share/applications

	install -m 0755 liveinst.xinit $(DESTDIR)/etc/X11/xinit/xinitrc.d/zz-liveinst.sh

clean:
	rm -f *~
