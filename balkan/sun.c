/* Sun style partitioning */

#include "balkan.h"

#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>

#include "byteswap.h"

struct singlePartitionTable {
	unsigned char info[128];   /* Informative text string */
	unsigned char spare0[14];
	struct sun_info {
		unsigned char spare1;
		unsigned char id;
		unsigned char spare2;
		unsigned char flags;
	} infos[8];
	unsigned char spare1[246]; /* Boot information etc. */
	unsigned short rspeed;     /* Disk rotational speed */
	unsigned short pcylcount;  /* Physical cylinder count */
	unsigned short sparecyl;   /* extra sects per cylinder */
	unsigned char spare2[4];   /* More magic... */
	unsigned short ilfact;     /* Interleave factor */
	unsigned short ncyl;       /* Data cylinder count */
	unsigned short nacyl;      /* Alt. cylinder count */
	unsigned short ntrks;      /* Tracks per cylinder */
	unsigned short nsect;      /* Sectors per track */
	unsigned char spare3[4];   /* Even more magic... */
	struct sun_partition {
		unsigned int start_cylinder;
		unsigned int num_sectors;
	} parts[8];
	unsigned short magic;      /* Magic number */
	unsigned short csum;       /* Label xor'd checksum */
};

#define SUN_LABEL_MAGIC		0xDABE
#define SECTOR_SIZE		512
#define WHOLE_DISK		5
#define UFS_SUPER_MAGIC		0x00011954

int sunpReadTable(int fd, struct partitionTable * table) {
    struct singlePartitionTable singleTable;
    int i, rc, magic;
    unsigned short *p, csum;

    table->maxNumPartitions = 8;

    for (i = 0; i < table->maxNumPartitions; i++)
	table->parts[i].type = -1;

    table->sectorSize = SECTOR_SIZE;

    if (lseek(fd, 0, SEEK_SET) < 0)
	return BALKAN_ERROR_ERRNO;

    if (read(fd, &singleTable, sizeof(singleTable)) != sizeof(singleTable))
	return BALKAN_ERROR_ERRNO;
	
    if (be16_to_cpu(singleTable.magic) != SUN_LABEL_MAGIC)
	return BALKAN_ERROR_BADMAGIC;

    for (p = (unsigned short *)&singleTable, csum = 0;
	 p < (unsigned short *)(&singleTable+1);)
	csum ^= *p++;

    if (csum)
	return BALKAN_ERROR_BADMAGIC;

    for (i = 0; i < 8; i++) {
	if (!singleTable.parts[i].num_sectors) continue;

	table->parts[i].startSector =
	    be32_to_cpu(singleTable.parts[i].start_cylinder) *
	    be16_to_cpu(singleTable.nsect) *
	    be16_to_cpu(singleTable.ntrks);
	table->parts[i].size =
	    be32_to_cpu(singleTable.parts[i].num_sectors);
	table->parts[i].type = singleTable.infos[i].id;
    }

    for (i = 0; i < 8; i++) {
	if (table->parts[i].type == -1) continue;

	switch (table->parts[i].type) {
	  case 0x83:
	    table->parts[i].type = BALKAN_PART_EXT2;
	    break;

	  case 0x82:
	    table->parts[i].type = BALKAN_PART_SWAP;
	    break;

	  case 0xfd:
	    table->parts[i].type = BALKAN_PART_RAID;
	   break;

	  default:
	    if (table->parts[i].type != WHOLE_DISK &&
		lseek64(fd, (8192 + 0x55c + SECTOR_SIZE *
			    (off64_t) table->parts[i].startSector),
		       SEEK_SET) >= 0 &&
		read(fd, &magic, 4) == 4 &&
		(magic == UFS_SUPER_MAGIC ||
		 swab32(magic) == UFS_SUPER_MAGIC))
		table->parts[i].type = BALKAN_PART_UFS;
	    else
		table->parts[i].type = BALKAN_PART_OTHER;
	    break;
	}
    }

    return 0;
}

#ifdef STANDALONE_TEST

void main() {
    int fd;
    int i;
    struct partitionTable table;

    fd = open("/dev/hda", O_RDONLY);

    printf("rc= %d\n", sunpReadTable(fd, &table));

    for (i = 0; i < table.maxNumPartitions; i++) {
	if (table.parts[i].type == -1) continue;

	printf("%d: %x %d\n", i, table.parts[i].type, table.parts[i].size);
    }
}

#endif
