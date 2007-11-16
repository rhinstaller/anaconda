all: command-line.txt kickstart-docs.txt

command-line.txt:
	curl -A "anaconda-build" -o command-line.txt "http://fedoraproject.org/wiki/Anaconda/Options?action=raw"

kickstart-docs.txt:
	curl -A "anaconda-build" -o kickstart-docs.txt "http://fedoraproject.org/wiki/Anaconda/Kickstart?action=raw"

clean:
	rm -rf kickstart-docs.txt command-line.txt api

depend:

install:
