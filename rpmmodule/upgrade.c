#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

#include <glob.h>	/* XXX rpmio.h */
#include <dirent.h>	/* XXX rpmio.h */

#include <rpmlib.h>

#include "hash.h"
#include "upgrade.h"

#define MAXPKGS 1024

#define USEDEBUG 0

#define DEBUG(x) {   \
     if (USEDEBUG)   \
         printf x; \
     }

#if 0
static void printMemStats(char *mess)
{
    char buf[1024];
    printf("%s\n", mess);
    sprintf(buf, "cat /proc/%d/status | grep VmSize", getpid());
    system(buf);
}
#endif

int pkgCompare(void * first, void * second) {
    struct packageInfo ** a = first;
    struct packageInfo ** b = second;

    /* put packages w/o names at the end */
    if (!(*a)->name) return 1;
    if (!(*b)->name) return -1;

    return strcasecmp((*a)->name, (*b)->name);
}


/* Adds all files in the second file list which are not in the first
   file list to the hash table. */
static void compareFileList(int availFileCount, char **availBaseNames,
			    char ** availDirNames, int * availDirIndexes,
			    int instFileCount, char **instBaseNames,
			    char ** instDirNames, int * instDirIndexes,
			    struct hash_table *ht)
{
    int installedX, availX, rc;
    char * availDir, * availBase;
    char * instDir, * instBase;
    static int i = 0;
    
    availX = 0;
    installedX = 0;
    while (installedX < instFileCount) {
	instBase = instBaseNames[installedX];
	instDir = instDirNames[instDirIndexes[installedX]];

	if (availX == availFileCount) {
	    /* All the rest have moved */
	    DEBUG(("=> %d: %s%s\n", i++, instDir, instBase))
	    if (strncmp(instDir, "/etc/rc.d/", 10))
		htAddToTable(ht, instDir, instBase);
	    installedX++;
	} else {
	    availBase = availBaseNames[availX];
	    availDir = availDirNames[availDirIndexes[availX]];

	    rc = strcmp(availDir, instDir);
	    if (!rc) 
		rc = strcmp(availBase, instBase);

	    if (rc > 0) {
		/* Avail > Installed -- file has moved */
		DEBUG(("=> %d: %s%s\n", i++, instDir, instBase))
		if (strncmp(instDir, "/etc/rc.d/", 10))
		    htAddToTable(ht, instDir, instBase);
		installedX++;
	    } else if (rc < 0) {
		/* Avail < Installed -- avail has some new files */
		availX++;
	    } else {
		/* Files are equal -- file not moved */
		availX++;
		installedX++;
	    }
	}
    }
}

static void addLostFiles(rpmdb db, struct pkgSet *psp, struct hash_table *ht)
{
    int num;
    Header h;
    char *name;
    struct packageInfo **pack;
    struct packageInfo key;
    struct packageInfo *keyaddr = &key;
    char **installedFiles;
    char **installedDirs;
    int_32 * installedDirIndexes;
    int installedFileCount;

    num = rpmdbFirstRecNum(db);
    while (num) {
	h = rpmdbGetRecord(db, num);
	headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);
	if (name && !strcmp(name, "metroess")) {
	    /* metro was removed from 5.1, but leave it if it's already
	       installed */
	    headerFree(h);
	    num = rpmdbNextRecNum(db, num);
	    continue;
	}
	key.name = name;
	
	pack = bsearch(&keyaddr, psp->packages, psp->numPackages,
		       sizeof(*psp->packages), (void *)pkgCompare);
	if (!pack) {
	    if (headerGetEntryMinMemory(h, RPMTAG_BASENAMES, NULL,
			  (void **) &installedFiles, &installedFileCount)) {
		headerGetEntryMinMemory(h, RPMTAG_DIRINDEXES, NULL,
			  (void **) &installedDirIndexes, NULL);
		headerGetEntryMinMemory(h, RPMTAG_DIRNAMES, NULL,
			  (void **) &installedDirs, NULL);

		compareFileList(0, NULL, NULL, NULL, installedFileCount,
				installedFiles, installedDirs,
				installedDirIndexes, ht);

		free(installedFiles);
		free(installedDirs);
	    }
	}
	
	headerFree(h);
	num = rpmdbNextRecNum(db, num);
    }
}

static int findPackagesWithObsoletes(rpmdb db, struct pkgSet *psp)
{
    dbiIndexSet matches;
    int rc, count, obsoletesCount;
    struct packageInfo **pip;
    char **obsoletes;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	if ((*pip)->selected) {
	    pip++;
	    continue;
	}

	if (headerGetEntryMinMemory((*pip)->h, RPMTAG_OBSOLETES, NULL,
		       (void **) &obsoletes, &obsoletesCount)) {
	    while (obsoletesCount--) {
		rc = rpmdbFindPackage(db, obsoletes[obsoletesCount], &matches);
		if (!rc) {
		    if (matches.count) {
			(*pip)->selected = 1;
			dbiFreeIndexRecord(matches);
			break;
		    }

		    dbiFreeIndexRecord(matches);
		}
	    }

	    free(obsoletes);
	}

	pip++;
    }

    return 0;
}

static void errorFunction(void)
{
}

static int findUpgradePackages(rpmdb db, struct pkgSet *psp,
			       struct hash_table *ht)
{
    int skipThis;
    Header h, installedHeader;
    char *name;
    dbiIndexSet matches;
    int rc, i, count;
    char **installedFiles, **availFiles;
    char **installedDirs, ** availDirs;
    int_32 * installedDirIndexes, * availDirIndexes;
    int installedFileCount, availFileCount;
    struct packageInfo **pip;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	h = (*pip)->h;
	name = NULL;
	headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);
	if (!name) {
	    /* bum header */
	    /*logMessage("Failed with bad header");*/
	    return(-1);
	}
	
	DEBUG (("Avail: %s\n", name));
	rc = rpmdbFindPackage(db, name, &matches);

	if (rc == 0) {
	    skipThis = 0;
	    rpmErrorSetCallback(errorFunction);
	    for (i = 0; i < matches.count; i++) {
		installedHeader =
		    rpmdbGetRecord(db, matches.recs[i].recOffset);
		if (rpmVersionCompare(installedHeader, h) >= 0) {
		    /* already have a newer version installed */
		    DEBUG (("Already have newer version\n"))
		    skipThis = 1;
		    headerFree(installedHeader);
		    break;
		}
		headerFree(installedHeader);
	    }
	    rpmErrorSetCallback(NULL);
	    if (! skipThis) {
		DEBUG (("No newer version installed\n"))
	    }
	} else {
	    skipThis = 1;
	    DEBUG (("Not installed\n"))
	}
	
	if (skipThis) {
	    DEBUG (("DO NOT INSTALL\n"))
	} else {
	    DEBUG (("UPGRADE\n"))
	    (*pip)->selected = 1;

	    if (!headerGetEntryMinMemory(h, RPMTAG_BASENAMES, NULL,
			  (void **) &availFiles, &availFileCount)) {
		availFiles = NULL;
		availFileCount = 0;
	    } else {
		headerGetEntryMinMemory(h, RPMTAG_DIRNAMES, NULL,
			    (void **) &availDirs, NULL);
		headerGetEntryMinMemory(h, RPMTAG_DIRINDEXES, NULL,
			    (void **) &availDirIndexes, NULL);
	    }

	    for (i = 0; i < matches.count; i++) {
		/* Compare the file lists */
		installedHeader =
		    rpmdbGetRecord(db, matches.recs[i].recOffset);
		if (headerGetEntryMinMemory(installedHeader, RPMTAG_BASENAMES, 
			      NULL, (void **) &installedFiles,
			      &installedFileCount)) {
		    headerGetEntryMinMemory(installedHeader, RPMTAG_DIRNAMES, 
				NULL, (void **) &installedDirs, NULL);
		    headerGetEntryMinMemory(installedHeader, RPMTAG_DIRINDEXES, 
				NULL, (void **) &installedDirIndexes, NULL);

		    compareFileList(availFileCount, availFiles,
				    availDirs, availDirIndexes,
				    installedFileCount, installedFiles, 
				    installedDirs, installedDirIndexes,
				    ht);

		    free(installedFiles);
		    free(installedDirs);
		}
		headerFree(installedHeader);
	    }

	    if (availFiles) {
		free(availFiles);
		free(availDirs);
	    }
	}

	if (rc == 0) {
	    dbiFreeIndexRecord(matches);
	}

	DEBUG (("\n\n"))

	pip++;
    }

    return 0;
}

static int removeMovedFilesAlreadyHandled(struct pkgSet *psp,
					  struct hash_table *ht)
{
    char *name;
    int i, count;
    Header h;
    char **availFiles, ** availDirs;
    int_32 * availDirIndexes;
    int availFileCount;
    struct packageInfo **pip;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	h = (*pip)->h;
	if ((*pip)->selected) {
	    name = NULL;
	    headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);

	    if (headerGetEntryMinMemory(h, RPMTAG_BASENAMES, NULL,
			  (void **) &availFiles, &availFileCount)) {

		headerGetEntryMinMemory(h, RPMTAG_DIRNAMES, NULL, 
			       (void **) &availDirs, NULL);
		headerGetEntryMinMemory(h, RPMTAG_DIRINDEXES, NULL, 
			       (void **) &availDirIndexes, NULL);

		for (i = 0; i < availFileCount; i++) {
		    if (htInTable(ht, availDirs[availDirIndexes[i]],
					  availFiles[i])) {
			htRemoveFromTable(ht, availDirs[availDirIndexes[i]],
					  availFiles[i]);
			DEBUG (("File already in %s: %s%s\n", name, 
				availDirs[availDirIndexes[i]], availFiles[i]))
			break;
		    }
		}

		free(availFiles);
		free(availDirs);
	    }
	}

	pip++;
    }

    return 0;
}

static int findPackagesWithRelocatedFiles(struct pkgSet *psp,
					  struct hash_table *ht)
{
    char *name;
    int i, count;
    Header h;
    char **availFiles, **availDirs;
    int_32 * availDirIndexes;
    int availFileCount;
    struct packageInfo **pip;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	h = (*pip)->h;
	if (! (*pip)->selected) {
	    name = NULL;
	    headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);

	    if (headerGetEntry(h, RPMTAG_BASENAMES, NULL,
			 (void **) &availFiles, &availFileCount)) {
		headerGetEntryMinMemory(h, RPMTAG_DIRNAMES, NULL,
			    (void **) &availDirs, NULL);
		headerGetEntryMinMemory(h, RPMTAG_DIRINDEXES, NULL,
			    (void **) &availDirIndexes, NULL);

		for (i = 0; i < availFileCount; i++) {
		    if (htInTable(ht, availDirs[availDirIndexes[i]], 
				    availFiles[i])) {
			htRemoveFromTable(ht, availDirs[availDirIndexes[i]],
					  availFiles[i]);
			DEBUG (("Found file in %s: %s%s\n", name,
				availDirs[availDirIndexes[i]], availFiles[i]))
			(*pip)->selected = 1;
			break;
		    }
		}
		free(availFiles);
		free(availDirs);
	    }
	}

	pip++;
    }

    return 0;
}

/*
static void printCount(struct pkgSet *psp)
{
    int i, upgradeCount;
    struct packageInfo *pip;
    
    upgradeCount = 0;
    pip = psp->packages;
    i = psp->numPackages;
    while (i--) {
	if (pip->selected) {
	    upgradeCount++;
	}
	pip++;
    }
    logMessage("marked %d packages for upgrade", upgradeCount);
}
*/

static int unmarkPackagesAlreadyInstalled(rpmdb db, struct pkgSet *psp)
{
    dbiIndexSet matches;
    Header h, installedHeader;
    char *name;
    struct packageInfo **pip;
    int count, rc, i;

    count = psp->numPackages;
    pip = psp->packages;
    while (count--) {
	if ((*pip)->selected) {
	    h = (*pip)->h;
	    /* If this package is already installed, don't bother */
	    name = NULL;
	    headerGetEntry(h, RPMTAG_NAME, NULL, (void **) &name, NULL);
	    if (!name) {
		/* bum header */
		/*logMessage("Failed with bad header");*/
		return(-1);
	    }
	    rc = rpmdbFindPackage(db, name, &matches);
	    if (rc == 0) {
		rpmErrorSetCallback(errorFunction);
		for (i = 0; i < matches.count; i++) {
		    installedHeader =
			rpmdbGetRecord(db, matches.recs[i].recOffset);
		    if (rpmVersionCompare(installedHeader, h) >= 0) {
			/* already have a newer version installed */
			DEBUG (("Already have newer version\n"))
			(*pip)->selected = 0;
			headerFree(installedHeader);
			break;
		    }
		    headerFree(installedHeader);
		}
		rpmErrorSetCallback(NULL);
		dbiFreeIndexRecord(matches);
	    }
	}

	pip++;
    }

    return 0;
}
	    
static void emptyErrorCallback(void) {
}

int ugFindUpgradePackages(struct pkgSet *psp, char *installRoot)
{
    rpmdb db;
    struct hash_table *hashTable;
    rpmErrorCallBackType old;    

    /*logDebugMessage(("ugFindUpgradePackages() ..."));*/

    rpmReadConfigFiles(NULL, NULL);

    rpmSetVerbosity(RPMMESS_FATALERROR);
    old = rpmErrorSetCallback(emptyErrorCallback);

    if (rpmdbOpenForTraversal(installRoot, &db)) {
	/*logMessage("failed opening %s/var/lib/rpm/packages.rpm",
		     installRoot);*/
	return(-1);
    }

    rpmErrorSetCallback(old);
    rpmSetVerbosity(RPMMESS_NORMAL);
    
    hashTable = htNewTable(1103);

    /* For all packages that are installed, if there is no package       */
    /* available by that name, add the package's files to the hash table */
    addLostFiles(db, psp, hashTable);
    /*logDebugMessage(("added lost files"));
    printCount(psp);*/
    
    /* Find packges that are new, and mark them in installThisPackage,  */
    /* updating availPkgs with the count.  Also add files to the hash   */
    /* table that do not exist in the new package - they may have moved */
    if (findUpgradePackages(db, psp, hashTable)) {
	rpmdbClose(db);
	return(-1);
    }
    /*logDebugMessage(("found basic packages to upgrade"));
    printCount(psp);
    hash_stats(hashTable);*/

    /* Remove any files that were added to the hash table that are in */
    /* some other package marked for upgrade.                         */
    removeMovedFilesAlreadyHandled(psp, hashTable);
    /*logDebugMessage(("removed extra files which have moved"));
    printCount(psp);*/

    findPackagesWithRelocatedFiles(psp, hashTable);
    /*logDebugMessage(("found packages with relocated files"));
    printCount(psp);*/

    findPackagesWithObsoletes(db, psp);
    /*logDebugMessage(("found packages that obsolete installed packages"));
    printCount(psp);*/
    
    unmarkPackagesAlreadyInstalled(db, psp);
    /*logDebugMessage(("unmarked packages already installed"));
    printCount(psp);*/
    
    htFreeHashTable(hashTable);
    
    /*printMemStats("Done");*/

    rpmdbClose(db);

    return 0;
}
