#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

#include "log.h"

int copyFileFd(int infd, char * dest) {
    int outfd;
    char buf[4096];
    int i;
    int rc = 0;

    outfd = open(dest, O_CREAT | O_RDWR, 0666);

    if (outfd < 0) {
	logMessage("failed to open %s: %s", dest, strerror(errno));
	return 1;
    }

    while ((i = read(infd, buf, sizeof(buf))) > 0) {
	if (write(outfd, buf, i) != i) {
	    rc = 1;
	    break;
	}
    }

    close(outfd);

    return rc;
}

int copyFile(char * source, char * dest) {
    int infd = -1;
    int rc;

    infd = open(source, O_RDONLY);

    if (infd < 0) {
	logMessage("failed to open %s: %s", source, strerror(errno));
	return 1;
    }

    rc = copyFileFd(infd, dest);

    close(infd);

    return rc;
}

char * readLine(FILE * f) {
    char buf[1024];

    fgets(buf, sizeof(buf), f);

    /* chop */
    buf[strlen(buf) - 1] = '\0';

    return strdup(buf);
}

