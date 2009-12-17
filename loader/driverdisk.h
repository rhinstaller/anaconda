/*
 * driverdisk.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef DRIVERDISK_H
#define DRIVERDISK_H

#include "loader.h"
#include "modules.h"
#include "moduleinfo.h"

#define DD_RPMDIR_TEMPLATE "/tmp/DD-%d"
#define DD_EXTRACTED "/tmp/DD"
#define DD_MODULES "/tmp/DD/lib/modules"
#define DD_FIRMWARE "/tmp/DD/lib/firmware"

extern char *ddFsTypes[];

int loadDriverFromMedia(int class, struct loaderData_s *loaderData,
                        int usecancel, int noprobe);

int loadDriverDisks(int class, struct loaderData_s *loaderData);

int getRemovableDevices(char *** devNames);

int chooseManualDriver(int class, struct loaderData_s *loaderData);
void useKickstartDD(struct loaderData_s * loaderData, int argc, 
                    char ** argv);

void getDDFromSource(struct loaderData_s * loaderData, char * src);

int loadDriverDiskFromPartition(struct loaderData_s *loaderData, char* device);

GSList* findDriverDiskByLabel(void);

int modprobeNormalmode();
int modprobeDDmode();

#endif
