INSTALL= /usr/bin/install -c
INSTALL_PROGRAM= ${INSTALL}
INSTALL_DATA= ${INSTALL} -m 644
PREFIX=$(DESTDIR)/
INSTALLNLSDIR=usr/share/locale

MSGMERGE = msgmerge
LONG_MERGE = -w 9999999

NLSPACKAGE = anaconda

LONG_PO  = ja.po ko.po zh.po
SHORT_PO = $(filter-out $(LONG_PO), $(wildcard *.po))
FMTCATALOGS = $(patsubst %.po,%.mo,$(SHORT_PO) $(LONG_PO))

POTFILES = ../*.py ../iw/*.py ../textw/*.py \
           ../installclasses/*.py \
           ../libfdisk/*.c ../loader/*.c \
           ../gnome-map/*.c \
	   ../comps/comps-master

all: $(FMTCATALOGS)

$(NLSPACKAGE).pot: $(POTFILES)
	xgettext --default-domain=$(NLSPACKAGE) \
		--add-comments --keyword=_ --keyword=N_ $(POTFILES)
	./compsgettext ../comps/comps-master >> $(NLSPACKAGE).po
	if cmp -s $(NLSPACKAGE).po $(NLSPACKAGE).pot; then \
	    rm -f $(NLSPACKAGE).po; \
	else \
	    mv $(NLSPACKAGE).po $(NLSPACKAGE).pot; \
	fi


update-po: Makefile $(NLSPACKAGE).pot refresh-po

refresh-po: Makefile
	for cat in $(SHORT_PO); do \
		lang=`basename $$cat .po`; \
		if $(MSGMERGE) $$lang.po $(NLSPACKAGE).pot > $$lang.pot ; then \
			mv -f $$lang.pot $$lang.po ; \
			echo "$(MSGMERGE) of $$lang succeeded" ; \
		else \
			echo "$(MSGMERGE) of $$lang failed" ; \
			rm -f $$lang.pot ; \
		fi \
	done
	for cat in $(LONG_PO); do \
		lang=`basename $$cat .po`; \
		if $(MSGMERGE) $(LONG_MERGE) $$lang.po $(NLSPACKAGE).pot > $$lang.pot ; then \
			mv -f $$lang.pot $$lang.po ; \
			echo "$(MSGMERGE) $(LONG_MERGE) of $$lang succeeded" ; \
		else \
			echo "$(MSGMERGE) $(LONG_MERGE) of $$lang failed" ; \
			rm -f $$lang.pot ; \
		fi \
	done

clean:
	rm -f *mo $(NLSPACKAGE).pot

distclean: clean
	rm -f .depend Makefile

depend:

install:	$(FMTCARALOGS) all 
	mkdir -p $(PREFIX)/$(INSTALLNLSDIR)
	for n in $(FMTCATALOGS); do \
	    l=`basename $$n .mo`; \
	    $(INSTALL) -m 755 -d $(PREFIX)/$(INSTALLNLSDIR)/$$l; \
	    $(INSTALL) -m 755 -d $(PREFIX)/$(INSTALLNLSDIR)/$$l/LC_MESSAGES; \
	    $(INSTALL) -m 644 $$n \
		$(PREFIX)/$(INSTALLNLSDIR)/$$l/LC_MESSAGES/$(NLSPACKAGE).mo; \
	done

.PHONY: missing

missing:
	mkdir -p missing; \
	for n in $(FMTCATALOGS); do \
	    msghack -w 999999 --missing $$n > missing/$$n-; \
            msghack -w 999999 --empty missing/$$n- | grep -v "^#," > missing/$$n; \
	    rm missing/$$n-; \
	done

missing-mixed:
	mkdir -p missing-mixed; \
	for n in $(FMTCATALOGS); do \
	    msghack -w 999999 --missing $$n > missing-mixed/$$n; \
	done

%.mo: %.po
	cat $< timeconfig/$< | msgfmt -o $@ -

depend:
