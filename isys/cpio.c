#include <fcntl.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <zlib.h>

#include "cpio.h"

int installCpioFile(gzFile fd, char * cpioName, char * outName, int inWin) {
    struct cpioFileMapping map;
    int rc;
    const char * failedFile;

    FILE *myfile;

    myfile = fopen("/dev/tty3", "rw");

    if (outName) {
	map.archivePath = cpioName;
	map.fsPath = outName;
	map.mapFlags = CPIO_MAP_PATH;
    }

    rc = myCpioInstallArchive(fd, outName ? &map : NULL, 1, NULL, NULL, 
			    &failedFile);

    fprintf(myfile, "Failed file = %s\n", failedFile);

    if (rc || access(outName, R_OK)) {
	return -1;
    }

    return 0;
}
