#ifndef H_MODULES
#define H_MODULES

#include "isys/isys.h"

typedef struct moduleList_s * moduleList;
typedef struct moduleDependency_s * moduleDeps;

struct loadedModuleInfo {
    char * name;
    char ** args;
    int weLoaded;
    char * path;
    int firstDevNum, lastDevNum;	/* only used for ethernet currently */
    enum driverMajor major;
    enum driverMinor minor;
};

struct moduleList_s {
    struct loadedModuleInfo mods[50];
    int numModules;
};


int mlReadLoadedList(moduleList * list);
void mlFreeList(moduleList list);
int mlLoadDeps(moduleDeps * moduleDepList, const char * path);
moduleDeps mlNewDeps(void);
int mlLoadModule(char * modName, void * location, moduleList modLoaded,
	         moduleDeps modDeps, char ** args, moduleInfoSet modInfo,
		 int flags);
char ** mlGetDeps(moduleDeps modDeps, const char * modName);
int mlModuleInList(const char * modName, moduleList list);
int mlWriteConfModules(moduleList list, int fd);

#endif
