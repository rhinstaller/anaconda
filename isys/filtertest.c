#include <stdio.h>
#include <zlib.h>

#include "cpio.h"

int main(int argc, char ** argv) {
    char * pattern[2];
    gzFile in, out; 
    int rc;

    if (argc != 3) {
	fprintf(stderr, "ack!\n");
	return 1;
    }

    in = gzopen(argv[1], "r");
    if (!in) {
	fprintf(stderr, "failed to open %s\n", argv[1]);
    }

    out = gzdopen(1, "w");

    pattern[0] = argv[2];
    pattern[1] = NULL;

    rc = myCpioFilterArchive(in, out, pattern);
    fprintf(stderr, "returned %d\n", rc);

    gzclose(out);

    return rc;
}
