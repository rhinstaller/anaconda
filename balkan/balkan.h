#ifndef H_BALKAN
#define H_BALKAN 1

#define BALKAN_ERROR_ERRNO	1
#define BALKAN_ERROR_BADMAGIC	2
#define BALKAN_ERROR_BADTABLE	3

#define BALKAN_PART_DOS		1
#define BALKAN_PART_EXT2	2
#define BALKAN_PART_OTHER	3
#define BALKAN_PART_NTFS	4
#define BALKAN_PART_SWAP	5
#define BALKAN_PART_UFS		6

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
