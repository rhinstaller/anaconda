#ifndef MODULEDEPS_H
#define MODULEDEPS_H

struct moduleDependency_s {
    char * name;
    char ** deps;
};

struct extractedModule {
    char * path;
    char * location;
};

moduleDeps mlNewDeps(void);
int mlLoadDeps(moduleDeps * moduleDepListPtr, const char * path);
char ** mlGetDeps(moduleDeps modDeps, const char * modName);

#endif
