#ifndef H_MODULES

typedef struct moduleList_s * moduleList;
typedef struct moduleDependency_s * moduleDeps;

int mlReadLoadedList(moduleList * list);
void mlFreeList(moduleList list);
int mlLoadDeps(moduleDeps * moduleDepList, const char * path);
moduleDeps mlNewDeps(void);
int mlLoadModule(char * modName, moduleList modLoaded,
	         moduleDeps modDeps, int testing);
char ** mlGetDeps(moduleDeps modDeps, const char * modName);
int mlModuleInList(const char * modName, moduleList list);
int mlWriteConfModules(moduleList list, moduleInfoSet modInfo, int fd);

#endif
