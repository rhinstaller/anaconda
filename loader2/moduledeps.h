#ifndef MODULEDEPS_H
#define MODULEDEPS_H

typedef struct moduleDependency_s * moduleDeps;

struct moduleDependency_s {
    char * name;
    char ** deps;
};

moduleDeps mlNewDeps(void);
int mlLoadDeps(moduleDeps * moduleDepListPtr, const char * path);
char ** mlGetDeps(moduleDeps modDeps, const char * modName);

#endif
