/*
 * modules.h
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

#ifndef H_MODULES
#define H_MODULES

#include "moduleinfo.h"
#include "moduledeps.h"

typedef struct moduleList_s * moduleList;

struct loadedModuleInfo {
    char * name;
    char ** args;
    int weLoaded;
    int written;
    char * path;
    int firstDevNum, lastDevNum;
    enum driverMajor major;
    enum driverMinor minor;
};

struct extractedModule {
    char * path;
    char * location;
};

struct moduleList_s {
    struct loadedModuleInfo mods[100];
    int numModules;
};

int mlReadLoadedList(moduleList * mlp);
int mlLoadModule(const char * module, moduleList modLoaded, 
                 moduleDeps modDeps, moduleInfoSet modInfo, 
                 char ** args);
int mlLoadModuleSet(const char * modNames, 
		    moduleList modLoaded, moduleDeps modDeps, 
		    moduleInfoSet modInfo);

int mlModuleInList(const char * modName, moduleList list);
void writeScsiDisks(moduleList list);

int removeLoadedModule(const char * modName, moduleList modLoaded);
char * getModuleLocation(int version);

#endif
