/*
 * kickstart.c - kickstart file handling
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1999-2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#include <alloca.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "log.h"
#include "kickstart.h"

#include "kbd.h"
#include "net.h"
#include "method.h"

#include "../isys/imount.h"
#include "../isys/isys.h"
#include "../isys/probe.h"

struct ksCommandNames {
    int code;
    char * name;
    void (*setupData) (struct loaderData_s *loaderData,
                       int argc, char ** argv, int * flagsPtr);
} ;

struct ksCommand {
    int code, argc;
    char ** argv;
};

static void setTextMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv, int * flagsPtr);

struct ksCommandNames ksTable[] = {
    { KS_CMD_NFS, "nfs", setKickstartNfs },
    { KS_CMD_CDROM, "cdrom", NULL },
    { KS_CMD_HD, "harddrive", NULL },
    { KS_CMD_TEXT, "text", setTextMode },
    { KS_CMD_URL, "url", NULL },
    { KS_CMD_NETWORK, "network", setKickstartNetwork },
    { KS_CMD_KEYBOARD, "keyboard", setKickstartKeyboard },
    { KS_CMD_LANG, "lang", setKickstartLanguage },
    { KS_CMD_NONE, NULL, NULL }
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

    logMessage("reading kickstart file");

    if ((fd = open(cmdFile, O_RDONLY)) < 0) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Error opening kickstart file %s: %s"),
                       cmdFile, strerror(errno));
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
            /* do nothing */
        } else if (!strcmp(start, "%packages")) {
            inPackages = 1;
        } else if  (*chptr == '\\') {
            /* JKFIXME: this should be handled better, but at least we 
             * won't segfault now */
        } else {
            if (poptParseArgvString(start, &argc, 
                                    (const char ***) &argv) || !argc) {
                newtWinMessage(_("Kickstart Error"), _("OK"), 
                               _("Error in %s on line %d of kickstart file %s."),
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
    int i;

    for(i = 0; i < numCommands; i++)
	if (commands[i].code == cmd) return 1;

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

    for (; i < numCommands; i++) {    
        if (commands[i].code == cmd) {
            if (argv) *argv = commands[i].argv;
            if (argc) *argc = commands[i].argc;
            return 0;
        }
    }
    
    return 1;
}

int kickstartFromFloppy(int flags) {
    struct device ** devices;
    int i;

    logMessage("doing kickstart from floppy");
    devices = probeDevices(CLASS_FLOPPY, BUS_MISC | BUS_IDE | BUS_SCSI, 
                           PROBE_ALL);
    if (!devices) {
        logMessage("no floppy devices");
        return 1;
    }

    for (i = 0; devices[i]; i++) {
        if (devices[i]->detached == 0) {
            logMessage("first non-detached floppy is %s", devices[i]->device);
            break;
        }
    }

    if (!devices[i] || (devices[i]->detached != 0)) {
        logMessage("no floppy devices");
        return 1;
    }

    if (devMakeInode(devices[i]->device, "/tmp/floppy"))
        return 1;

    if ((doPwMount("/tmp/floppy", "/tmp/ks", "vfat", 1, 0, NULL, NULL)) && 
        doPwMount("/tmp/floppy", "/tmp/ks", "ext2", 1, 0, NULL, NULL)) {
        logMessage("failed to mount floppy: %s", strerror(errno));
        return 1;
    }
    
    if (access("/tmp/ks/ks.cfg", R_OK)) {
        startNewt(flags);
        newtWinMessage(_("Error"), _("OK"),
                       _("Cannot find ks.cfg on boot floppy."));
        return 1;
    }

    copyFile("/tmp/ks/ks.cfg", "/tmp/ks.cfg");
    umount("/tmp/ks");
    unlink("/tmp/floppy");

    logMessage("kickstart file copied to /tmp/ks.cfg");

    return 0;
}

void getKickstartFile(struct knownDevices * kd, 
                      struct loaderData_s * loaderData, int * flagsPtr) {
    char * c = loaderData->ksFile;
    int flags = *flagsPtr;

    loaderData->ksFile = NULL;

    if (!strncmp(c, "ks=http://", 10) || !strncmp(c, "ks=ftp://", 9)) {
        if (kickstartFromUrl(c + 3, kd, loaderData, flags))
            return;
        loaderData->ksFile = strdup("/tmp/ks.cfg");
    } else if (!strncmp(c, "ks=cdrom:", 9)) {
        logMessage("grabbing kickstart from cdrom currently unsupported");
        return;
    } else if (!strncmp(c, "ks=nfs:", 7)) {
        logMessage("grabbing kickstart from nfs currently unsupported");
        return;
    } else if (!strncmp(c, "ks=floppy", 9)) {
        if (kickstartFromFloppy(*flagsPtr)) 
            return;
        loaderData->ksFile = strdup("/tmp/ks.cfg");
    } else if (!strncmp(c, "ks=hd:", 6)) {
        logMessage("grabbing kickstart from hd currently unsupported");
        return;
    } else if (!strncmp(c, "ks=file:", 8)) {
        loaderData->ksFile = c + 8;
    } else if (!strcmp(c, "ks")) {
        logMessage("grabbing kickstart from nfs with dhcp next-server currently unsupported");
        return;
    }

    (*flagsPtr) = (*flagsPtr) | LOADER_FLAGS_KICKSTART;
    return;
}

static void setTextMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv, int * flagsPtr) {
    (*flagsPtr) = (*flagsPtr) | LOADER_FLAGS_TEXT;
    return;
}

void setupKickstart(struct loaderData_s * loaderData, int * flagsPtr) {
    struct ksCommandNames * cmd;
    int argc;
    char ** argv;

    logMessage("setting up kickstart");
    for (cmd = ksTable; cmd->name; cmd++) {
        if ((!ksGetCommand(cmd->code, NULL, &argc, &argv)) && cmd->setupData) {
            cmd->setupData(loaderData, argc, argv, flagsPtr);
        }
    }
}
