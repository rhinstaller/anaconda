#ifndef H_HDINSTALL
#define H_HDINSTALL


char * mountHardDrive(struct installMethod * method,
                      char * location, struct knownDevices * kd,
                      struct loaderData_s * loaderData,
                      moduleInfoSet modInfo, moduleList modLoaded,
                      moduleDeps * modDepsPtr, int flags);

#endif
