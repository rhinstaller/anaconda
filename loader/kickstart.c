#include <alloca.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <stdlib.h>
#include <string.h>
#include <newt.h>
#include <popt.h>
#include <unistd.h>

#include "lang.h"
#include "loader.h"
#include "kickstart.h"

struct ksCommandNames {
    int code;
    char * name;
} ;

struct ksCommand {
    int code, argc;
    char ** argv;
};

struct ksCommandNames ksTable[] = {
    { KS_CMD_NFS, "nfs" },
    { KS_CMD_CDROM, "cdrom" },
    { KS_CMD_HD, "harddrive" },
    { KS_CMD_TEXT, "text" },
    { KS_CMD_URL, "url" },
    { KS_CMD_NETWORK, "network" },
    { KS_CMD_DEVICE, "device" },
    { KS_CMD_XDISPLAY, "xdisplay" },
    { KS_CMD_NONE, NULL }
};

struct ksCommand * commands = NULL;
int numCommands = 0;

int ksReadCommands(char * cmdFile) {
    int fd;
    char * buf;
    struct stat sb;
    char * start, * end, * chptr;
    char oldch;
    int line = 0;
    char ** argv; 
    int argc;
    int inPackages = 0;
    struct ksCommandNames * cmd;
    int commandsAlloced = 5;

    if ((fd = open(cmdFile, O_RDONLY)) < 0) {
	newtWinMessage(_("Kickstart Error"), _("OK"), 
			_("Error opening: kickstart file %s: %s"), cmdFile, 
			strerror(errno));
	return LOADER_ERROR;
    }

    fstat(fd, &sb);

    buf = alloca(sb.st_size + 1);
    if (read(fd, buf, sb.st_size) != sb.st_size) {
	newtWinMessage(_("Kickstart Error"), _("OK"), 
			_("Error reading contents of kickstart file %s: %s"),
			cmdFile, strerror(errno));
	close(fd);
	return LOADER_ERROR;
    }

    close(fd);

    buf[sb.st_size] = '\0';

    commands = malloc(sizeof(*commands) * commandsAlloced);

    start = buf;
    while (*start && !inPackages) {
	line++;

	if (!(end = strchr(start, '\n')))
	    end = start + strlen(start);

	oldch = *end;
	*end = '\0';

	while (*start && isspace(*start)) start++;

	chptr = end - 1;
	while (chptr > start && isspace(*chptr)) chptr--;

	if (isspace(*chptr)) 
	    *chptr = '\0';
	else
	    *(chptr + 1) = '\0';

	if (!*start || *start == '#') {
	    /* no nothing */
	} else if (!strcmp(start, "%packages")) {
	    inPackages = 1;
	} else {
	    if (poptParseArgvString(start, &argc, &argv) || !argc) {
		newtWinMessage(_("Kickstart Error"), _("OK"), 
			       _("Error on line %d of kickstart file %s."),
				argv[0], line, cmdFile);
	    } else {
		for (cmd = ksTable; cmd->name; cmd++)
		    if (!strcmp(cmd->name, argv[0])) break;

		if (cmd->name) {
		    if (numCommands == commandsAlloced) {
			commandsAlloced += 5;
			commands = realloc(commands,
					   sizeof(*commands) * commandsAlloced);
		    }

		    commands[numCommands].code = cmd->code;
		    commands[numCommands].argc = argc;
		    commands[numCommands].argv = argv;
		    numCommands++;
		}
	    }
	}

	if (oldch)
	    start = end + 1;
	else
	    start = end;
    }

    return 0;
}

int ksHasCommand(int cmd) {
    int i = 0;

    while (i < numCommands) {
	if (commands[i].code == cmd) return 1;
	i++;
    }

    return 0;
}

int ksGetCommand(int cmd, char ** last, int * argc, char *** argv) {
    int i = 0;

    if (last) {
	for (i = 0; i < numCommands; i++) {
	    if (commands[i].argv == last) break;
	}

	i++;
    }

    while (i < numCommands) {
	if (commands[i].code == cmd) {
	    if (argv) *argv = commands[i].argv;
	    if (argc) *argc = commands[i].argc;
	    return 0;
	}
	i++;
    }

    return 1;
}
