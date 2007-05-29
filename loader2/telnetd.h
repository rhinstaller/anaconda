#ifndef TELNETD_H
#define TELNETD_H

void startTelnetd(struct loaderData_s * loaderData,
                  moduleInfoSet modInfo, moduleList modLoaded, 
                  moduleDeps modDeps);

#endif
