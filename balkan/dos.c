/* DOS style partitioning */

#include <fcntl.h>
#include <unistd.h>

#include "balkan.h"
#include "byteswap.h"

struct singlePartition {
    unsigned char active;
    unsigned char startHead;
    unsigned char startSector;
    unsigned char startCyl;
    unsigned char type;
    unsigned char endHead;
    unsigned char endSector;
    unsigned char endCyl;
    unsigned int  start;		/* in sectors */
    unsigned int  size;			/* in sectors */
};

struct singlePartitionTable {
    struct singlePartition parts[4];
};

/* Location of partition table in MBR */
#define TABLE_OFFSET		446
#define MBR_MAGIC       	0x55aa
#define MBR_MAGIC_OFFSET	510
#define SECTOR_SIZE		512

#define DOSP_TYPE_EXTENDED	5

long long llseek(int fd, long long offset, int whence);

static int readSingleTable(int fd, struct singlePartitionTable * table,
			long long partSector) {
    unsigned char sector[SECTOR_SIZE];
    unsigned short magic;

    if (llseek(fd, ((long long) SECTOR_SIZE * (long long) partSector),
	       SEEK_SET) < 0)
	return BALKAN_ERROR_ERRNO;

    if (read(fd, sector, sizeof(sector)) != sizeof(sector))
	return BALKAN_ERROR_ERRNO;

    magic = (sector[MBR_MAGIC_OFFSET] << 8) + sector[MBR_MAGIC_OFFSET + 1];
    if (magic != MBR_MAGIC)
	return BALKAN_ERROR_BADMAGIC;

    memcpy(table, sector + TABLE_OFFSET, sizeof(struct singlePartitionTable));

    return 0;
}

static int readNextTable(int fd, struct partitionTable * table, int nextNum, 
		  long long partSector, long long sectorOffset) {
    struct singlePartitionTable singleTable;
    int rc;
    int i, thisPart;
    int gotExtended = 0;

    if ((rc = readSingleTable(fd, &singleTable, partSector + sectorOffset)))
	return rc;

    if (nextNum >= 4) {
	/* This is an extended table */
	if (singleTable.parts[2].size || singleTable.parts[3].size)
	    return BALKAN_ERROR_BADTABLE;
    }

    for (i = 0; i < 4; i++) {
	if (!singleTable.parts[i].size) continue;
	if (singleTable.parts[i].type == DOSP_TYPE_EXTENDED &&
	    nextNum >= 4) continue;

	if (nextNum < 4)
	    thisPart = i;
	else
	    thisPart = nextNum++;

	table->parts[thisPart].startSector =
	    le32_to_cpu(singleTable.parts[i].start) + sectorOffset;
	table->parts[thisPart].size = le32_to_cpu(singleTable.parts[i].size);
	table->parts[thisPart].type = singleTable.parts[i].type;
    }

    if (nextNum < 4) nextNum = 4;

    /* look for extended partitions */
    for (i = 0; i < 4; i++) {
	if (!singleTable.parts[i].size) continue;

	if (singleTable.parts[i].type == DOSP_TYPE_EXTENDED) {
	    if (gotExtended) return BALKAN_ERROR_BADTABLE;
	    gotExtended = 1;

	    if (sectorOffset)
		rc = readNextTable(fd, table, nextNum > 4 ? nextNum : 4, 
				   singleTable.parts[i].start, sectorOffset);
	    else
		rc = readNextTable(fd, table, nextNum > 4 ? nextNum : 4, 
				   0, singleTable.parts[i].start);

	    if (rc) return rc;
	}
    }

    return 0;
}

int dospReadTable(int fd, struct partitionTable * table) {
    int i, rc;

    table->maxNumPartitions = 16;

    for (i = 0; i < table->maxNumPartitions; i++)
	table->parts[i].type = -1;

    table->sectorSize = SECTOR_SIZE;

    rc = readNextTable(fd, table, 0, 0, 0);

    if (!rc) {
	for (i = 0; i < 16; i++) {
	    if (table->parts[i].type == -1) continue;

	    switch (table->parts[i].type) {
	      case 0x01:
	      case 0x04:
	      case 0x06:
	      case 0x0b:
	      case 0x0c:
	      case 0x0e:
	      case 0x0f:
		table->parts[i].type = BALKAN_PART_DOS;
		break;

	      case 0x7:
		table->parts[i].type = BALKAN_PART_NTFS;

	      case 0x83:
		table->parts[i].type = BALKAN_PART_EXT2;
		break;

	      case 0x82:
		table->parts[i].type = BALKAN_PART_SWAP;
		break;

	      default:
		table->parts[i].type = BALKAN_PART_OTHER;
		break;
	    }
	}
    }

    return rc;
}

#ifdef STANDALONE_TEST

void main() {
    int fd;
    int i;
    struct partitionTable table;

    fd = open("/dev/hda", O_RDONLY);

    printf("rc= %d\n", dospReadTable(fd, &table));

    for (i = 0; i < table.maxNumPartitions; i++) {
	if (table.parts[i].type == -1) continue;

	printf("%d: %x %d\n", i, table.parts[i].type, table.parts[i].size);
    }
}

#endif
