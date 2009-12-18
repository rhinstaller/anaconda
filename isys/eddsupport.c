/*
 * eddsupport.c - handling of mapping disk drives in Linux to disk drives
 * according to the BIOS using the edd kernel module
 *
 * Copyright 2004 Dell, Inc., Red Hat, Inc.
 *
 * Rezwanul_Kabir@Dell.com
 * Jeremy Katz <katzj@redhat.com>
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

#include <kudzu/kudzu.h>


#include "eddsupport.h"
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
    return probeDevices (CLASS_HD, BUS_UNSPEC, PROBE_ALL);
}

static int readDiskSig(char *device, uint32_t *disksig) {
    int fd, rc;

    if (devMakeInode(device, "/tmp/biosdev")){
        return -1;
    }

    fd = open("/tmp/biosdev", O_RDONLY);
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
    unlink("/tmp/biosdev");
    return 0;
}

static int mapBiosDisks(struct device** devices,const char *path) {
    DIR *dirHandle;
    struct dirent *entry;
    char * sigFileName;
    uint32_t mbrSig, biosNum, currentSig;
    struct device **currentDev, **foundDisk;
    int i, rc, ret;

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
        return 0;
    }

    while ((entry = readdir(dirHandle)) != NULL) {
        if(!strncmp(entry->d_name,".",1) || !strncmp(entry->d_name,"..",2)) {
            continue;
        }
        ret = sscanf((entry->d_name+9), "%x", &biosNum);
        
        sigFileName = malloc(strlen(path) + strlen(entry->d_name) + 20);
        sprintf(sigFileName, "%s/%s/%s", path, entry->d_name, SIG_FILE);
        if (readMbrSig(sigFileName, &mbrSig) == 0) {
	    	
	    for (currentDev = devices, i = 0, foundDisk=NULL; (*currentDev) != NULL && i<2; currentDev++) {
        	if (!(*currentDev)->device)
            		continue;
		
        	if ((rc=readDiskSig((*currentDev)->device, &currentSig)) < 0){
			if (rc == -ENOMEDIUM || rc == -ENXIO)
			     continue;
			return 0;
		} 
            		

            	if (mbrSig == currentSig){
			foundDisk=currentDev;
			i++;
		}
	    }

	    if (i==1){
            if(!addToHashTable(mbrSigToName, (uint32_t)biosNum, 
                               (*foundDisk)->device))
                return 0;
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
    int ret;

    if (diskHashInit == 0) {
        probeBiosDisks();
        diskHashInit = 1;
    }

    if (mbrSigToName == NULL)
        return NULL;

    ret = sscanf(biosStr,"%x",&biosNum);
    disk = lookupHashItem(mbrSigToName, biosNum);
    if (disk) return disk->diskname;

    return NULL;
}
