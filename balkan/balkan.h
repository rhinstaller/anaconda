#ifndef H_BALKAN
#define H_BALKAN 1

#define BALKAN_ERROR_ERRNO	1
#define BALKAN_ERROR_BADMAGIC	2
#define BALKAN_ERROR_BADTABLE	3

struct partition {
    long startSector;
    long size;			/* in sectors */
    int type;			/* -1 for "not used" */
};

struct partitionTable {
    int allocationUnit;		/* in sectors */
    int maxNumPartitions;
    int sectorSize;
    struct partition parts[50];
};

int balkanReadTable(int fd, struct partitionTable * table);

#endif
