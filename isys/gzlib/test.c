#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "gzlib.h"

int main(int argc, char ** argv) {
    gzFile fd;
    char buf[4096];
    int i;

    if (argv[1]) {
	if (!strcmp(argv[1], "-d")) {
	    fd = gunzip_dopen(0);
	    while ((i = gunzip_read(fd, buf, sizeof(buf))) > 0)
		if (write(1, buf, i) != i) break;
	    if (i != 0) {
		fprintf(stderr, "error occured: %s\n", strerror(errno));
		return -1;
	    }
	} else {
	    fprintf(stderr, "unknown argument\n");
	    return -1;
	}
    } else {
	fd = gzip_dopen(1);
	while ((i = read(0, buf, sizeof(buf))) > 0)
	    if (gzip_write(fd, buf, i) != i) break;

	if (i != 0) {
	    fprintf(stderr, "error occured: %s\n", strerror(errno));
	    return -1;
	}
    }

    return 0;
}
