INSTALL= /usr/bin/install -c
INSTALL_PROGRAM= ${INSTALL}
INSTALL_DATA= ${INSTALL} -m 644
PREFIX=$(DESTDIR)/
INSTALLNLSDIR=usr/share/locale

MSGMERGE = msgmerge -w 9999999

NLSPACKAGE = anaconda

CATALOGS = $(shell ls *.po)
FMTCATALOGS = $(patsubst %.po,%.mo,$(CATALOGS))

POTFILES = ../*.py ../iw/*.py ../textw/*.py \
           ../libfdisk/*.c ../loader/*.c

all: $(NLSPACKAGE).pot $(FMTCATALOGS)

$(NLSPACKAGE).pot: $(POTFILES)
	xgettext --default-domain=$(NLSPACKAGE) \
		--add-comments --keyword=_ --keyword=N_ $(POTFILES)
	if cmp -s $(NLSPACKAGE).po $(NLSPACKAGE).pot; then \
	    rm -f $(NLSPACKAGE).po; \
	else \
	    mv $(NLSPACKAGE).po $(NLSPACKAGE).pot; \
	fi


update-po: Makefile
	$(MAKE) $(NLSPACKAGE).pot
	catalogs='$(CATALOGS)'; \
	for cat in $$catalogs; do \
		lang=`basename $$cat .po`; \
		if $(MSGMERGE) $$lang.po $(NLSPACKAGE).pot > $$lang.pot ; then \
			mv -f $$lang.pot $$lang.po ; \
			echo "$(MSGMERGE) of $$lang succeeded" ; \
		else \
			echo "$(MSGMERGE) of $$lang failed" ; \
			rm -f $$lang.pot ; \
		fi \
	done

refresh-po: Makefile
	catalogs='$(CATALOGS)'; \
	for cat in $$catalogs; do \
		lang=`basename $$cat .po`; \
		if $(MSGMERGE) $$lang.po $(NLSPACKAGE).pot > $$lang.pot ; then \
			mv -f $$lang.pot $$lang.po ; \
			echo "$(MSGMERGE) of $$lang succeeded" ; \
		else \
			echo "$(MSGMERGE) of $$lang failed" ; \
			rm -f $$lang.pot ; \
		fi \
	done

clean:
	rm -f *mo $(NLSPACKAGE).pot

distclean: clean
	rm -f .depend Makefile

depend:

install:	all
	mkdir -p $(PREFIX)/$(INSTALLNLSDIR)
	for n in $(CATALOGS); do \
	    l=`basename $$n .po`; \
	    mo=$$l.mo; \
	    $(INSTALL) -m 755 -d $(PREFIX)/$(INSTALLNLSDIR)/$$l; \
	    $(INSTALL) -m 755 -d $(PREFIX)/$(INSTALLNLSDIR)/$$l/LC_MESSAGES; \
	    $(INSTALL) -m 644 $$mo \
		$(PREFIX)/$(INSTALLNLSDIR)/$$l/LC_MESSAGES/$(NLSPACKAGE).mo; \
	done

missing: Makefile
	mkdir -p missing; \
	for n in $(CATALOGS); do \
	    msghack -w 999999 --missing $$n > missing/$$n-; \
            msghack -w 999999 --empty missing/$$n- | grep -v "^#," > missing/$$n; \
	    rm missing/$$n-; \
	done

%.mo: %.po
	msgfmt -o $@ $<
