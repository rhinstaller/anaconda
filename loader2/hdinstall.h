#ifndef H_HDINSTALL
#define H_HDINSTALL


char * mountHardDrive(struct installMethod * method,
                             char * location, struct knownDevices * kd,
                             moduleInfoSet modInfo, moduleList modLoaded,
                             moduleDeps * modDepsPtr, int flags);

#endif
