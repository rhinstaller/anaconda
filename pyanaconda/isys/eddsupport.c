/*
 * eddsupport.c - handling of mapping disk drives in Linux to disk drives
 * according to the BIOS using the edd kernel module
 *
 * Copyright (C) 2004  Dell, Inc.  All rights reserved.
 * Copyright (C) 2004  Red Hat, Inc.  All rights reserved.
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
 *
 * Author(s): Rezwanul_Kabir@Dell.com
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/reboot.h>
#include <sys/types.h>
#include <linux/types.h>


#include "eddsupport.h"
#include "devices.h"
#include "isys.h"

#define EDD_DIR "/sys/firmware/edd"
#define SIG_FILE "mbr_signature"
#define MBRSIG_OFFSET 0x1b8

#define HASH_TABLE_SIZE 17


struct diskMapEntry{
    uint32_t key;
    char *diskname;
    struct diskMapEntry *next;
};

struct diskMapTable {
    struct diskMapEntry **table;
    int tableSize;
};

static struct diskMapTable *mbrSigToName = NULL;
static int diskHashInit = 0;



static struct diskMapTable*  initializeHashTable(int);
static int insertHashItem(struct diskMapTable *, struct diskMapEntry *);
static struct diskMapEntry* lookupHashItem(struct diskMapTable *, uint32_t);
static int addToHashTable(struct diskMapTable *, uint32_t , char *);
static struct device ** createDiskList();
static int mapBiosDisks(struct device ** , const char *);
static int readDiskSig(char *,  uint32_t *);
static int readMbrSig(char *, uint32_t *);

/* This is the top level function that creates a disk list present in the
 * system, checks to see if unique signatures exist on the disks at offset 
 * 0x1b8.  If a unique signature exists then it will map BIOS disks to their 
 * corresponding hd/sd device names.  Otherwise, we'll avoid mapping drives.
 */

int probeBiosDisks() {
    struct device ** devices = NULL;

    devices = createDiskList();
    if(!devices){
#ifdef STANDALONE
        fprintf(stderr, "No disks!\n");
#endif
        return -1;
    }

    if(!mapBiosDisks(devices, EDD_DIR)){
#ifdef STANDALONE
            fprintf(stderr, "WARNING: couldn't map BIOS disks\n");
#endif
            return -1;
    }
    return 0;
}


static struct device ** createDiskList(){
    return getDevices (DEVICE_DISK);
}

static int readDiskSig(char *device, uint32_t *disksig) {
    int fd, rc;
    char devnodeName[64];

    snprintf(devnodeName, sizeof(devnodeName), "/dev/%s", device);
    fd = open(devnodeName, O_RDONLY);
    if (fd < 0) {
#ifdef STANDALONE 
        fprintf(stderr, "Error opening device %s: %s\n ", device, 
                strerror(errno));
#endif 
        return -errno;
    }

    rc = lseek(fd, MBRSIG_OFFSET, SEEK_SET);
    if (rc < 0){
        close(fd);

#ifdef STANDALONE
        fprintf(stderr, "Error seeking to MBRSIG_OFFSET in %s: %s\n", 
                device, strerror(errno));
#endif
        return -1;
    }

    rc = read(fd, disksig, sizeof(uint32_t));
    if (rc < sizeof(uint32_t)) {
        close(fd);

#ifdef STANDALONE
        fprintf(stderr, "Failed to read signature from %s\n", device); 
#endif
        return -1;
    }

    close(fd);
    return 0;
}

static int mapBiosDisks(struct device** devices,const char *path) {
    DIR *dirHandle;
    struct dirent *entry;
    char * sigFileName;
    uint32_t mbrSig, biosNum, currentSig;
    struct device **currentDev, **foundDisk;
    int i, rc, dm_nr, highest_dm;

    dirHandle = opendir(path);
    if(!dirHandle){
#ifdef STANDALONE
        fprintf(stderr, "Failed to open directory %s: %s\n", path, 
                strerror(errno));
#endif
        return 0;
    }

    mbrSigToName = initializeHashTable(HASH_TABLE_SIZE);
    if(!mbrSigToName){
#ifdef STANDALONE
        fprintf(stderr, "Error initializing mbrSigToName table\n");
#endif
        closedir(dirHandle);
        return 0;
    }

    while ((entry = readdir(dirHandle)) != NULL) {
        if(!strncmp(entry->d_name,".",1) || !strncmp(entry->d_name,"..",2)) {
            continue;
        }
        sscanf((entry->d_name+9), "%x", &biosNum);
        
        sigFileName = malloc(strlen(path) + strlen(entry->d_name) + 20);
        sprintf(sigFileName, "%s/%s/%s", path, entry->d_name, SIG_FILE);
        if (readMbrSig(sigFileName, &mbrSig) == 0) {
            for (currentDev = devices, i = 0, foundDisk=NULL, highest_dm=-1;
                    (*currentDev) != NULL;
                    currentDev++) {
                if (!(*currentDev)->device)
                    continue;

                if ((rc=readDiskSig((*currentDev)->device, &currentSig)) < 0) {
                    if (rc == -ENOMEDIUM || rc == -ENXIO)
                        continue;
                    closedir(dirHandle);
                    return 0;
                } 

                if (mbrSig == currentSig) {
                    /* When we have a fakeraid setup we will find multiple hits
                       a number for the raw disks (1 when striping, 2 when
                       mirroring, more with raid on raid like raid 01 or 10)
                       and a number for the dm devices (normally only one dm
                       device will match, but more with raid on raid).
                       Since with raid on raid the last dm device created
                       will be the top layer raid, we want the highest matching
                       dm device. */
                    if (!strncmp((*currentDev)->device, "dm-", 3) &&
                         sscanf((*currentDev)->device+3, "%d", &dm_nr) == 1) {
                        if (dm_nr > highest_dm) {
                            highest_dm = dm_nr;
                            foundDisk=currentDev;
                            i = 1;
                        }
                    } else if (!foundDisk ||
                               strncmp((*foundDisk)->device, "dm-", 3)) {
                        foundDisk=currentDev;
                        i++;
                    }
                }
            }

            if (i==1) {
                if(!addToHashTable(mbrSigToName, (uint32_t)biosNum, 
                               (*foundDisk)->device)) {
                    closedir(dirHandle);
                    return 0;
                }
            }
        } 
    }
    closedir(dirHandle);
    return 1;
} 


static int readMbrSig(char *filename, uint32_t *int_sig){
    FILE* fh;

    fh = fopen(filename,"r");
    if(fh == NULL) {
#ifdef STANDALONE
        fprintf(stderr, "Error opening mbr_signature file %s: %s\n", filename,
                strerror(errno));
#endif
        return -1;
    }
    fseek(fh, 0, SEEK_SET);
    if (fscanf(fh, "%x", int_sig) != 1) {
#ifdef STANDALONE
        fprintf(stderr, "Error reading %s\n", filename);
#endif
        fclose(fh);
        return -1;
    }

    fclose(fh);
    return 0;
}                                                   


static struct diskMapTable* initializeHashTable(int size) {
    struct diskMapTable *hashTable;

    hashTable = malloc(sizeof(struct diskMapTable));
    hashTable->tableSize = size;
    hashTable->table = malloc(sizeof(struct diskMapEntry *) * size);
    memset(hashTable->table,0,(sizeof(struct diskMapEntry *) * size));
    return hashTable;
}


static int insertHashItem(struct diskMapTable *hashTable,
                          struct diskMapEntry *hashItem) {
    int index;

    index = (hashItem->key) % (hashTable->tableSize);

    if(hashTable->table[index] == NULL){
        hashTable->table[index] = hashItem;
        return index;
    } else {
        hashItem->next = hashTable->table[index];
        hashTable->table[index] = hashItem;
        return index;
    }
}


static struct diskMapEntry * lookupHashItem(struct diskMapTable *hashTable,
                                            uint32_t itemKey) {
    int index;
    struct diskMapEntry *hashItem;

    index = itemKey % (hashTable->tableSize);
    for (hashItem = hashTable->table[index]; 
         (hashItem != NULL) && (hashItem->key != itemKey); 
         hashItem = hashItem->next) { 
        ;
    }
    return hashItem;
}


static int addToHashTable(struct diskMapTable *hashTable, 
                          uint32_t itemKey, char *diskName) {
    int index;
    struct diskMapEntry *diskSigToNameEntry;

    diskSigToNameEntry = malloc(sizeof(struct diskMapEntry));
    diskSigToNameEntry->next = NULL;
    diskSigToNameEntry->key = itemKey;
    diskSigToNameEntry->diskname = diskName;

    if ((index = insertHashItem(hashTable, diskSigToNameEntry)) < 0){
#ifdef STANDALONE
        fprintf(stderr, "Unable to insert item\n");
#endif
        return 0;
    } else {
        return 1;
    }
}


char * getBiosDisk(char *biosStr) {
    uint32_t biosNum;
    struct diskMapEntry * disk;

    if (diskHashInit == 0) {
        probeBiosDisks();
        diskHashInit = 1;
    }

    if (mbrSigToName == NULL)
        return NULL;

    sscanf(biosStr,"%x",&biosNum);
    disk = lookupHashItem(mbrSigToName, biosNum);
    if (disk) return disk->diskname;

    return NULL;
}
