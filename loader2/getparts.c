/* 
 * getparts.c - functions associated with getting partitions for a disk
 *
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2004 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <ctype.h>
#include <string.h>
#include <dirent.h>
#include <errno.h>

#include "log.h"

/* see if this is a partition name or not */
static int isPartitionName(char *pname) {

    /* if it doesnt start with a alpha its not one */
    if (!isalpha(*pname))
	return 0;

    /* if it has a '/' in it then treat it specially */
    if (strchr(pname, '/') && !strstr(pname, "iseries") && 
        !strstr(pname, "i2o")) {
	/* assume its either a /dev/ida/ or /dev/cciss device */
	/* these have form of c?d?p? if its a partition */
	return strchr(pname, 'p') != NULL;
    } else {
	/* if it ends with a digit we're ok */
	return isdigit(pname[strlen(pname)-1]);
    }
}

/* return NULL terminated array of pointers to names of partitons in
 * /proc/partitions
 */
char **getPartitionsList(char * disk) {
    FILE *f;
    int numfound = 0;
    char **rc=NULL;

    f = fopen("/proc/partitions", "r");
    if (!f) {
	logMessage(ERROR, "getPartitionsList: could not open /proc/partitions");
	return NULL;
    }

    /* read through /proc/partitions and parse out partitions */
    while (1) {
	char *tmpptr, *pptr;
	char tmpstr[4096];

	tmpptr = fgets(tmpstr, sizeof(tmpstr), f);

	if (tmpptr) {
	    char *a, *b;
	    int toknum = 0;

	    a = tmpstr;
	    while (1) {
		b = strsep(&a, " \n");

		/* if no fields left abort */
		if (!b)
		    break;

		/* if field was empty means we hit another delimiter */
		if (!*b)
		    continue;

		/* make sure this is a valid partition line, should start */
		/* with a numeral */
		if (toknum == 0) {
		    if (!isdigit(*b))
			break;
		} else if (toknum == 2) {
		    /* if size is exactly 1 then ignore it as an extended */
		    if (!strcmp(b, "1"))
			break;
		} else if (toknum == 3) {
		    /* this should be the partition name */
		    /* now we need to see if this is the block device or */
		    /* actually a partition name                         */
		    if (!isPartitionName(b))
			break;

                    /* make sure that either we don't care about the disk
                     * or it's this one */
                    if ((disk != NULL) && (strncmp(disk, b, strlen(disk))))
                        break;

		    /* we found a partition! */
		    pptr = (char *) malloc(strlen(b) + 7);
		    sprintf(pptr, "/dev/%s", b);

		    if (!rc) {
			rc = (char **) malloc(2*sizeof(char *));
		        rc[0] = pptr;
			rc[1] = NULL;
		    } else {
			int idx;
			
			rc = (char **) realloc(rc, (numfound+2)*sizeof(char *));
			idx = 0;
			while (idx < numfound) {
			    if (strcmp(pptr, rc[idx]) < 0)
				break;

			    idx++;
			}

			/* move existing out of way if necessary */
			if (idx != numfound)
			    memmove(rc+idx+1, rc+idx, (numfound-idx)*sizeof(char *));

			rc[idx] = pptr;
			rc[numfound+1] = NULL;
		    }
		    numfound++;
		    break;
		}
		toknum++;
	    }
	} else {
	    break;
	}
    }

    fclose(f);

    return rc;
}

/* returns length of partitionlist */
int lenPartitionsList(char **list) {
    char **part;
    int  rc;

    if (!list) return 0;
    for (rc = 0, part = list; *part; rc++, part++);

    return rc;
}

int createDevNode(const char *dname, const char *devname)
{
    char *dnode;
    FILE *f;
    int major, minor;

    f = fopen(dname, "r");
    logMessage(DEBUGLVL, "Trying to get device info %s from %s.", devname, dname);

    if (!f) {
        logMessage(ERROR, "Could not open %s.", dname);
        return -1;
    }

    if(fscanf(f, "%i:%i", &major, &minor)<2){
        logMessage(ERROR, "Could not get major/minor from %s.", devname);
        fclose(f);
        return -2;
    }

    fclose(f);
   
    if(asprintf(&dnode, "/dev/%s", devname)<=0) {
        logMessage(ERROR, "Cannot allocate memory for device node (%s).", devname);
        return -3;
    }
    
    if(mknod(dnode, 0600 | S_IFBLK, makedev(major, minor))<0) {
        if(errno!=EEXIST) {
            logMessage(ERROR, "Failed to create device node (%s %i:%i).", dnode, major, minor);
        }

        free(dnode);
        return -4;
    }
    else {
        logMessage(DEBUGLVL, "Device node (%s %i:%i) created.", dnode, major, minor);
        free(dnode);
        return 0;
    }
}

/* Ensure all the device nodes from /sys/block exist in /dev
 * returns number of partitions found
 */
int createPartitionNodes()
{
    DIR *d, *subd;
    int numfound = 0;
    struct dirent *dirp;
    struct dirent *subdirp;

    logMessage(DEBUGLVL, "Creating device nodes...");

    d = opendir("/sys/block");
    if(!d) {
        logMessage(ERROR, "Cannot read /sys/block. Device nodes will not be created and driver discs may not work");
        return -1;
    }

    /* Go through /sys/block */
    while((dirp = readdir(d)) != NULL) {
        char *dname;

        if(!strcmp(dirp->d_name, "..") || !strcmp(dirp->d_name, "."))
            continue;
        
        logMessage(DEBUGLVL, "Trying to create device nodes for %s.", dirp->d_name);

        if(asprintf(&dname, "/sys/block/%s/dev", dirp->d_name)<=0) {
            logMessage(ERROR, "Cannot allocate memory for device info (%s).", dirp->d_name);
            continue;
        }

        if(!createDevNode(dname, dirp->d_name))
            numfound++;
        free(dname);

        /* Look for partitions */
        if(asprintf(&dname, "/sys/block/%s", dirp->d_name)<=0) {
            logMessage(ERROR, "Cannot allocate memory for device subdirectory (%s).", dirp->d_name);
            continue;
        }

        subd = opendir(dname);
        if(!subd) {
            logMessage(ERROR, "Cannot read /sys/block/%s. Partition nodes will not be created and driver discs may not work", dirp->d_name);
            free(dname);
            continue;
        }

        /* Go through /sys/block/$dname */
        while((subdirp = readdir(subd)) != NULL) {
            char *subdirname;

            /* check if it is a partition */
            if(strncmp(subdirp->d_name, dirp->d_name, strlen(dirp->d_name))){
                /* not a partition, check next.. */
                continue;
            }

            logMessage(DEBUGLVL, "Trying to create device nodes for %s.", subdirp->d_name);
            if(asprintf(&subdirname, "/sys/block/%s/%s/dev", dirp->d_name, subdirp->d_name)<=0) {
                logMessage(ERROR, "Cannot allocate memory for device info (%s).", subdirp->d_name);
                continue;
            }

            if(!createDevNode(subdirname, subdirp->d_name))
                numfound++;
            free(subdirname);
        }
        
        closedir(subd);
        free(dname);
    }

    closedir(d);

    return numfound;
}

/* frees partition list */
void freePartitionsList(char **list) {
    char **part;

    if (!list)
	return;

    for (part = list; *part; part++)
	if (*part)
	    free(*part);

    free(list);
}
