#include <fcntl.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <zlib.h>

#include "cpio.h"

int installCpioFile(FD_t fd, char * cpioName, char * outName, int inWin) {
    struct cpioFileMapping map;
    int rc;
    char * failedFile;
    CFD_t cfdbuf, *cfd = &cfdbuf;

    if (outName) {
	map.archivePath = cpioName;
	map.fsPath = outName;
	map.mapFlags = CPIO_MAP_PATH;
    }

    cfd->cpioIoType = cpioIoTypeGzFd;
    cfd->cpioGzFd = gzdFdopen(fdDup(fdFileno(fd)), "r");
    
    rc = cpioInstallArchive(cfd, outName ? &map : NULL, 1, NULL, NULL, 
			    &failedFile);
    gzdClose(cfd->cpioGzFd);

    if (rc || access(outName, R_OK)) {
	return -1;
    }

    return 0;
}
