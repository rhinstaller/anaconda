#ifndef TELNETD_H
#define TELNETD_H

void startTelnetd(struct knownDevices * kd, struct loaderData_s * loaderData,
                  moduleInfoSet modInfo, moduleList modLoaded, 
                  moduleDeps modDeps, int flags);

#endif
