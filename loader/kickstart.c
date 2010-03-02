/*
 * kickstart.c - kickstart file handling
 *
 * Copyright (C) 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
 * All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <alloca.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <glib.h>

#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "kickstart.h"
#include "modules.h"

#include "kbd.h"
#include "driverdisk.h"
#include "net.h"
#include "method.h"

#include "nfsinstall.h"
#include "urlinstall.h"
#include "cdinstall.h"
#include "hdinstall.h"

#include "../isys/imount.h"
#include "../isys/isys.h"
#include "../isys/log.h"

/* boot flags */
extern uint64_t flags;

struct ksCommandNames {
    int code;
    char * name;
    void (*setupData) (struct loaderData_s *loaderData,
                       int argc, char ** argv);
} ;

struct ksCommand {
    int code, argc;
    char ** argv;
};

static void setTextMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv);
static void setGraphicalMode(struct loaderData_s * loaderData, int argc, 
                             char ** argv);
static void setCmdlineMode(struct loaderData_s * loaderData, int argc, 
                           char ** argv);
static void setSELinux(struct loaderData_s * loaderData, int argc, 
                       char ** argv);
static void setPowerOff(struct loaderData_s * loaderData, int argc, 
                        char ** argv);
static void setHalt(struct loaderData_s * loaderData, int argc, 
                    char ** argv);
static void setShutdown(struct loaderData_s * loaderData, int argc, 
                        char ** argv);
static void setMediaCheck(struct loaderData_s * loaderData, int argc, 
                          char ** argv);
static void setUpdates(struct loaderData_s * loaderData, int argc,
                       char ** argv);

struct ksCommandNames ksTable[] = {
    { KS_CMD_NFS, "nfs", setKickstartNfs },
    { KS_CMD_CDROM, "cdrom", setKickstartCD },
    { KS_CMD_HD, "harddrive", setKickstartHD },
    { KS_CMD_TEXT, "text", setTextMode },
    { KS_CMD_GRAPHICAL, "graphical", setGraphicalMode },
    { KS_CMD_URL, "url", setKickstartUrl },
    { KS_CMD_NETWORK, "network", setKickstartNetwork },
    { KS_CMD_KEYBOARD, "keyboard", setKickstartKeyboard },
    { KS_CMD_LANG, "lang", setKickstartLanguage },
    { KS_CMD_DD, "driverdisk", useKickstartDD },
    { KS_CMD_DEVICE, "device", loadKickstartModule },
    { KS_CMD_CMDLINE, "cmdline", setCmdlineMode },
    { KS_CMD_SELINUX, "selinux", setSELinux },
    { KS_CMD_POWEROFF, "poweroff", setPowerOff },
    { KS_CMD_HALT, "halt", setHalt },
    { KS_CMD_SHUTDOWN, "shutdown", setShutdown },
    { KS_CMD_MEDIACHECK, "mediacheck", setMediaCheck },
    { KS_CMD_UPDATES, "updates", setUpdates },
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
    gint argc = 0;
    gchar **argv = NULL;
    GError *optErr = NULL;
    int inSection = 0; /* in a section such as %post, %pre or %packages */
    struct ksCommandNames * cmd;
    int commandsAlloced = 5;

    if ((fd = open(cmdFile, O_RDONLY)) < 0) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Error opening kickstart file %s: %m"),
                       cmdFile);
        return LOADER_ERROR;
    }

    fstat(fd, &sb);
    buf = alloca(sb.st_size + 1);
    if (read(fd, buf, sb.st_size) != sb.st_size) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Error reading contents of kickstart file %s: %m"),
                       cmdFile);
        close(fd);
        return LOADER_ERROR;
    }

    close(fd);

    buf[sb.st_size] = '\0';

    commands = malloc(sizeof(*commands) * commandsAlloced);

    start = buf;
    while (*start && !inSection) {
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

        if (!*start || *start == '#' || !strncmp(start, "%include", 8)) {
            /* keep parsing the file */
        } else if (*start == '%') {
            /* assumed - anything starting with %something is a section */
            inSection = 1;
        } else if  (*chptr == '\\') {
            /* JKFIXME: this should be handled better, but at least we 
             * won't segfault now */
        } else {
            if (!g_shell_parse_argv(start, &argc, &argv, &optErr) && argc) {
                newtWinMessage(_("Kickstart Error"), _("OK"),
                               _("Error in %s on line %d of kickstart "
                                 "file %s."), argv[0], line, cmdFile);
                g_error_free(optErr);
            } else if (!argc) {
                newtWinMessage(_("Kickstart Error"), _("OK"),
                               _("Missing options on line %d of kickstart "
                                 "file %s."), line, cmdFile);
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

int kickstartFromRemovable(char *kssrc) {
    struct device ** devices;
    char *p, *kspath;
    int i, rc;

    logMessage(INFO, "doing kickstart from removable media");
    devices = getDevices(DEVICE_DISK);
    /* usb can take some time to settle, even with the various hacks we
     * have in place. some systems use portable USB CD-ROM drives, try to
     * make sure there really isn't one before bailing. */
    for (i = 0; !devices && i < 10; ++i) {
        logMessage(INFO, "sleeping to wait for a USB disk");
        sleep(2);
        devices = getDevices(DEVICE_DISK);
    }
    if (!devices) {
        logMessage(ERROR, "no disks");
        return 1;
    }

    for (i = 0; devices[i]; i++) {
        if (devices[i]->priv.removable == 1) {
            logMessage(INFO, "first removable media is %s", devices[i]->device);
            break;
        }
    }

    if (!devices[i] || (devices[i]->priv.removable == 0)) {
        logMessage(ERROR, "no removable devices");
        return 1;
    }

    /* format is floppy:[/path/to/ks.cfg] */
    kspath = "";
    p = strchr(kssrc, ':');
    if (p)
	kspath = p + 1;

    if (!p || strlen(kspath) < 1)
	kspath = "/ks.cfg";

    if ((rc=getKickstartFromBlockDevice(devices[i]->device, kspath))) {
	if (rc == 3) {
	    startNewt();
	    newtWinMessage(_("Error"), _("OK"),
			   _("Cannot find ks.cfg on removable media."));
	}
	return 1;
    }

    return 0;
}


/* given a device name (w/o '/dev' on it), try to get ks file */
/* Error codes: 
      1 - could not create device node
      2 - could not mount device as ext2, vfat, or iso9660
      3 - kickstart file named path not there
*/
int getKickstartFromBlockDevice(char *device, char *path) {
    return getFileFromBlockDevice(device, path, "/tmp/ks.cfg");
}

static char *newKickstartLocation(const char *origLocation) {
    const char *location;
    char *retval = NULL;
    newtComponent f, okay, cancel, answer, locationEntry;
    newtGrid grid, buttons;

    startNewt();

    locationEntry = newtEntry(-1, -1, NULL, 60, &location, NEWT_FLAG_SCROLL);
    newtEntrySet(locationEntry, origLocation, 1);

    /* button bar at the bottom of the window */
    buttons = newtButtonBar(_("OK"), &okay, _("Cancel"), &cancel, NULL);

    grid = newtCreateGrid(1, 3);

    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT,
                     newtTextboxReflowed(-1, -1, _("Unable to download the kickstart file.  Please modify the kickstart parameter below or press Cancel to proceed as an interactive installation."), 60, 0, 0, 0),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, locationEntry,
                     0, 1, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons,
                     0, 1, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    f = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, f, 1);
    newtGridWrappedWindow(grid, _("Error downloading kickstart file"));
    newtGridFree(grid, 1);

    /* run the form */
    answer = newtRunForm(f);

    if (answer != cancel)
        retval = strdup(location);

    newtFormDestroy(f);
    newtPopWindow();

    return retval;
}

int isKickstartFileRemote(char *ksFile) {
    char *location = NULL;

    if (ksFile == NULL) {
        return 0;
    }

    if (!strcmp(ksFile, "ks")) {
       return 1;
    } else if (!strncmp(ksFile, "ks=", 3)) {
        location = ksFile + 3;
    }

    if (!strncmp(location, "http", 4) ||
        !strncmp(location, "ftp://", 6) ||
        !strncmp(location, "nfs:", 4)) {
        return 1;
    } else {
        return 0;
    }
}

void getKickstartFile(struct loaderData_s *loaderData) {
    char *c;
    int rc = 1;

    /* Chop off the parameter name, if given. */
    if (!strncmp(loaderData->ksFile, "ks=", 3))
        c = loaderData->ksFile+3;
    else
        c = loaderData->ksFile;

    while (rc != 0) {
        if (!strncmp(c, "ks", 2)) {
            rc = kickstartFromNfs(NULL, loaderData);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "http", 4) || !strncmp(c, "ftp://", 6)) {
            rc = kickstartFromUrl(c, loaderData);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "nfs:", 4)) {
            rc = kickstartFromNfs(c+4, loaderData);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "floppy", 6)) {
            rc = kickstartFromRemovable(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "hd:", 3)) {
            rc = kickstartFromHD(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "bd:", 3)) {
            rc = kickstartFromBD(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "cdrom", 5)) {
            rc = kickstartFromCD(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "file:", 5)) {
            loaderData->ksFile = c+5;
            break;
        }

        if (rc != 0) {
            char *newLocation;

            if (!strcmp(c, "ks"))
                newLocation = newKickstartLocation("");
            else
                newLocation = newKickstartLocation(c);

            if (loaderData->ksFile != NULL)
                free(loaderData->ksFile);

            if (newLocation != NULL) {
               loaderData->ksFile = strdup(newLocation);
               free(newLocation);
               return getKickstartFile(loaderData);
            }
            else
               return;
        }
    }

    flags |= LOADER_FLAGS_KICKSTART;
    return;
}

static void setUpdates(struct loaderData_s * loaderData, int argc,
                       char ** argv) {
   if (argc == 1)
      flags |= LOADER_FLAGS_UPDATES;
   else if (argc == 2)
      loaderData->updatessrc = strdup(argv[1]);
   else
      logMessage(WARNING, "updates command given with incorrect arguments");
}

static void setTextMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv) {
    logMessage(INFO, "kickstart forcing text mode");
    flags |= LOADER_FLAGS_TEXT;
    return;
}

static void setGraphicalMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv) {
    logMessage(INFO, "kickstart forcing graphical mode");
    flags |= LOADER_FLAGS_GRAPHICAL;
    return;
}

static void setCmdlineMode(struct loaderData_s * loaderData, int argc, 
                           char ** argv) {
    logMessage(INFO, "kickstart forcing cmdline mode");
    flags |= LOADER_FLAGS_CMDLINE;
    return;
}

static void setSELinux(struct loaderData_s * loaderData, int argc, 
                       char ** argv) {
    flags |= LOADER_FLAGS_SELINUX;
    return;
}

static void setPowerOff(struct loaderData_s * loaderData, int argc, 
                        char ** argv) {
    if (!FL_NOKILL(flags))
        flags |= LOADER_FLAGS_POWEROFF;
    return;
}

static void setHalt(struct loaderData_s * loaderData, int argc, 
                    char ** argv) {
    if (!FL_NOKILL(flags))
        flags |= LOADER_FLAGS_HALT;
    return;
}

static void setShutdown(struct loaderData_s * loaderData, int argc, 
                    char ** argv) {
    gint eject = 0, reboot = 0, halt = 0, poweroff = 0;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksOptions[] = {
        { "eject", 'e', 0, G_OPTION_ARG_INT, &eject, NULL, NULL },
        { "reboot", 'r', 0, G_OPTION_ARG_INT, &reboot, NULL, NULL },
        { "halt", 'h', 0, G_OPTION_ARG_INT, &halt, NULL, NULL },
        { "poweroff", 'p', 0, G_OPTION_ARG_INT, &poweroff, NULL, NULL },
        { NULL },
    };

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to shutdown kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (FL_NOKILL(flags)) {
        flags |= LOADER_FLAGS_HALT;
    } else  {
        if (poweroff)
            flags |= LOADER_FLAGS_POWEROFF;
        if ((!poweroff && !reboot) || (halt))
            flags |= LOADER_FLAGS_HALT;
    }
}

static void setMediaCheck(struct loaderData_s * loaderData, int argc, 
                          char ** argv) {
    flags |= LOADER_FLAGS_MEDIACHECK;
    return;
}

void runKickstart(struct loaderData_s * loaderData) {
    struct ksCommandNames * cmd;
    int argc;
    char ** argv;

    logMessage(INFO, "setting up kickstart");
    for (cmd = ksTable; cmd->name; cmd++) {
        if ((!ksGetCommand(cmd->code, NULL, &argc, &argv)) && cmd->setupData) {
            cmd->setupData(loaderData, argc, argv);
        }
    }
}

/* vim:set sw=4 sts=4 et: */
