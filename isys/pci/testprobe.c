#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "pciprobe.h"

int main(void) {
    char ** matches;

    if (probePciReadDrivers("pcitable")) {
	perror("error reading pci table");
	return 1;
    }

    matches = probePciDriverList();
    if (!matches) {
	printf("no pci drivers are needed\n");
    } else {
	while (*matches) {
	    printf("%s\n", *matches);
	    matches++;
	}
    }

    return 0;
}
