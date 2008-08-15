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

int loadDriverDiskFromPartition(struct loaderData_s *loaderData, char* device);

struct ddlist {
  char* device;
  struct ddlist* next;
};

struct ddlist* ddlist_add(struct ddlist *list, const char* device);
int ddlist_free(struct ddlist *list);

struct ddlist* findDriverDiskByLabel(void);

#endif
