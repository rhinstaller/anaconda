#include <stdio.h>
#include <string.h>

#include "commands.h"

struct commandTableEntry {
    char * name;
    int (*fn)(int argc, char ** argv);
};

struct commandTableEntry commandTable[] = {
	{ "cat", catCommand },
	{ "chmod", chmodCommand },
	{ "df", dfCommand },
	{ "gunzip", gunzipCommand },
	{ "ln", lnCommand },
	{ "ls", lsCommand },
	{ "lsmod", lsmodCommand },
	{ "mkdir", mkdirCommand },
	{ "mknod", mknodCommand },
	{ "umount", umountCommand },
	{ "mount", mountCommand },
	{ "rm", rmCommand },
	{ "uncpio", uncpioCommand },
	{ NULL, NULL }
};

int main (int argc, char ** argv) {    
    int len = strlen(argv[0]);
    struct commandTableEntry * cmd;

    for (cmd = commandTable; cmd->name; cmd++) {
	if (!strcmp(argv[0] + len - strlen(cmd->name), cmd->name)) 
	    break;
    }

    if (cmd->name)
    	return cmd->fn(argc, argv);

    printf("collage may be run as:\n");
    for (cmd = commandTable; cmd->name; cmd++) 
        printf("\t%s\n", cmd->name);

    return 1;
}

