#ifndef H_MODULES
#define H_MODULES

#include "moduleinfo.h"
#include "moduledeps.h"

#define MODULES_MAXLOADED 256

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
    struct loadedModuleInfo mods[MODULES_MAXLOADED];
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

void mlWriteBlacklist();
#endif
