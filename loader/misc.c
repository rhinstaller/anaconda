#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

#include "log.h"

int copyFile(char * source, char * dest) {
    int infd = -1, outfd = -1;
    char buf[4096];
    int i;

    outfd = open(dest, O_CREAT | O_RDWR, 0666);
    infd = open(source, O_RDONLY);

    if (infd < 0) {
	logMessage("failed to open %s: %s", source, strerror(errno));
    }

    while ((i = read(infd, buf, sizeof(buf))) > 0) {
	if (write(outfd, buf, i) != i) break;
    }

    close(infd);
    close(outfd);

    return 0;
}

