#ifndef H_MODULES
#define H_MODULES

typedef struct moduleList_s * moduleList;
typedef struct moduleDependency_s * moduleDeps;

struct loadedModuleInfo {
    char * name;
    char ** args;
    int weLoaded;
    char * path;
};

struct moduleList_s {
    struct loadedModuleInfo mods[50];
    int numModules;
};

int mlReadLoadedList(moduleList * list);
void mlFreeList(moduleList list);
int mlLoadDeps(moduleDeps * moduleDepList, const char * path);
moduleDeps mlNewDeps(void);
int mlLoadModule(char * modName, char * path, moduleList modLoaded,
	         moduleDeps modDeps, char ** args, int flags);
char ** mlGetDeps(moduleDeps modDeps, const char * modName);
int mlModuleInList(const char * modName, moduleList list);
int mlWriteConfModules(moduleList list, moduleInfoSet modInfo, int fd);

#endif
