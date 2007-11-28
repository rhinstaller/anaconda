all: command-line.txt kickstart-docs.txt

command-line.txt: toc-kill.xsl
	curl -A "anaconda-build" -o command-line.xml "http://fedoraproject.org/wiki/Anaconda/Options?action=format&mimetype=xml/docbook"
	xmlto --skip-validation -m toc-kill.xsl txt command-line.xml

kickstart-docs.txt:
	curl -A "anaconda-build" -o kickstart-docs.xml "http://fedoraproject.org/wiki/Anaconda/Kickstart?action=format&mimetype=xml/docbook"
	xmlto --skip-validation txt kickstart-docs.xml

clean:
	rm -rf kickstart-docs.txt command-line.txt api *.xml

depend:

install:
