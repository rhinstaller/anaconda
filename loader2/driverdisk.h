#ifndef DRIVERDISK_H
#define DRIVERDISK_H

#include "loader.h"
#include "modules.h"
#include "moduledeps.h"
#include "moduleinfo.h"

int loadDriverFromMedia(int class, struct loaderData_s *loaderData,
                        int usecancel, int noprobe);

int loadDriverDisks(int class, struct loaderData_s *loaderData);

int getRemovableDevices(char *** devNames);

int chooseManualDriver(int class, struct loaderData_s *loaderData);
void useKickstartDD(struct loaderData_s * loaderData, int argc, 
                    char ** argv);

void getDDFromSource(struct loaderData_s * loaderData, char * src);

#endif
