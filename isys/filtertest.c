#include <stdio.h>
#include <fcntl.h>
#include <stdarg.h>

#include "cpio.h"

void warn() {
}

void logMessage(char * text, ...) {
    va_list args;
    
    va_start(args, text);
    
    vfprintf(stderr, text, args);
    fprintf(stderr, "\n");

    va_end(args);
}

int main(int argc, char ** argv) {
    gzFile in, out; 
    int rc;

    if (argc < 3) {
	fprintf(stderr, "bad arguments!\n");
	return 1;
    }

    in = gunzip_open(argv[1]);
    if (!in) {
	fprintf(stderr, "failed to open %s\n", argv[1]);
    }

    out = gzip_dopen(1);

    rc = myCpioFilterArchive(in, out, argv + 2);

    gzip_close(out);

    return rc;
}
