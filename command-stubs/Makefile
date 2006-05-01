include ../Makefile.inc

STUBS = raidstart-stub raidstop-stub kudzu-probe-stub list-harddrives-stub \
	loadkeys-stub losetup-stub pump-stub mknod-stub syslogd-stub

all:
	@echo "Nothing to do"

depend:
	@echo "Nothing to do"

clean:
	/bin/rm -f *.pyc *~

install:
	for i in $(STUBS) ; do \
		install -m 755 $$i $(DESTDIR)/$(PYTHONLIBDIR) ; \
	done
