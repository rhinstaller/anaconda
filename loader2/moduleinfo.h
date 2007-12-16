/*
 * moduleinfo.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
 */

#ifndef MODULEINFO_H
#define MODULEINFO_H

enum driverMajor { DRIVER_NONE = 0, DRIVER_SCSI, DRIVER_NET, DRIVER_CDROM,
		   DRIVER_PCMCIA, DRIVER_FS, DRIVER_IDE, DRIVER_OTHER = 1000,
                   DRIVER_ANY = 5000 };
enum driverMinor { DRIVER_MINOR_NONE = 0, DRIVER_MINOR_ETHERNET,
		   DRIVER_MINOR_TR };

struct moduleArg {
    char * arg;
    char * description;
};

#define MI_FLAG_NOMISCARGS	(1 << 0)

struct moduleInfo {
    char * moduleName;
    char * description;
    enum driverMajor major;
    enum driverMinor minor;
    int numArgs;
    struct moduleArg * args;
    int flags;
    void * locationID;
};

struct moduleInfoSet_s {
    struct moduleInfo * moduleList;
    int numModules;
};

struct moduleBallLocation {
    char * path; /* path to module ball that this driver is from. if NULL,
                  * implies /modules/modules.cgz */
    char * title; /* title used for driver disk -- may be NULL */
    int version;  /* module ball version, used to determine layout */
};
#define CURRENT_MODBALLVER 1

/* valid moduleball versions
 * 0: old single-arch module ball, modules are in uname.release
 * 1: multi-arch, modules are in uname.release/arch
 */

typedef struct moduleInfoSet_s * moduleInfoSet;

moduleInfoSet newModuleInfoSet(void);
void freeModuleInfoSet(moduleInfoSet mis);
int readModuleInfo(const char * filename, moduleInfoSet mis, void * path, int override);
struct moduleInfo * findModuleInfo(moduleInfoSet mis, 
				   const char * moduleName);

/* NULL moduleName indicates the end of the list; the list must be freed() */
struct moduleInfo * getModuleList(moduleInfoSet mis, 
				  enum driverMajor major);


#endif
