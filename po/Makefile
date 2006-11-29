INSTALL= /usr/bin/install -c
INSTALL_PROGRAM= ${INSTALL}
INSTALL_DATA= ${INSTALL} -m 644
PREFIX=$(DESTDIR)/
INSTALLNLSDIR=usr/share/locale

MSGMERGE = msgmerge -v

NLSPACKAGE = anaconda

POS = $(wildcard *.po)
FMTCATALOGS = $(patsubst %.po,%.mo,$(POS))

GLADEFILES = ../ui/*.glade

POTFILES = ../anaconda ../*.py ../iw/*.py ../textw/*.py \
           ../installclasses/*.py \
           ../loader2/*.c 

NONPOTFILES = /usr/share/zoneinfo/zone.tab \
	   ../lang-table

all: $(FMTCATALOGS)

$(NLSPACKAGE).pot: $(POTFILES) $(NONPOTFILES) glade-po
	xgettext --from-code=UTF-8 --default-domain=$(NLSPACKAGE) \
		 --keyword=_ --keyword=N_ $(POTFILES) tmp/*.h
	cat /usr/share/zoneinfo/zone.tab | cut -f4 | grep "^[a-zA-Z]" | sort -u | while read line; do echo -e "\n#. generated from zone.tab\nmsgid \"$$line\"\nmsgstr \"\""; done >> $(NLSPACKAGE).po
	cat ../lang-table | cut -f1 | while read line; do echo -e "\n#. generated from lang-table\nmsgid \"$$line\"\nmsgstr \"\""; done >> $(NLSPACKAGE).po
	if cmp -s $(NLSPACKAGE).po $(NLSPACKAGE).pot; then \
	    rm -f $(NLSPACKAGE).po; \
	else \
	    mv $(NLSPACKAGE).po $(NLSPACKAGE).pot; \
	fi

glade-po: $(GLADEFILES)
	rm -rf tmp/
	for f in $(GLADEFILES); do \
		intltool-extract --type=gettext/glade -l $$f ;\
	done

update-po: Makefile $(NLSPACKAGE).pot refresh-po

refresh-po: Makefile
	for cat in $(POS); do \
		lang=`basename $$cat .po`; \
		if $(MSGMERGE) $$lang.po $(NLSPACKAGE).pot > $$lang.pot ; then \
			mv -f $$lang.pot $$lang.po ; \
			echo "$(MSGMERGE) of $$lang succeeded" ; \
		else \
			echo "$(MSGMERGE) of $$lang failed" ; \
			rm -f $$lang.pot ; \
		fi \
	done

report:
	@for cat in $(POS); do \
		echo -n "$$cat: "; \
		msgfmt -v --statistics -o /dev/null $$cat; \
	done

clean:
	rm -f *mo

reallyclean: clean
	rm -f $(NLSPACKAGE).pot

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
	msgfmt --check -o $@ $<

depend:
