/*
   pdc: Promise Fake Raid reader
	  Copyright (C) 2001

*/

#include <unistd.h>
#include <sys/ioctl.h>
#include <stdio.h>
#include <fcntl.h>
#include <linux/hdreg.h>
#include <linux/fs.h>
#include <string.h>

typedef unsigned int uint32_t;

struct promise_raid_conf {
    char                promise_id[24];
#define PR_MAGIC        "Promise Technology, Inc."

    int32_t             dummy_0;
    int32_t             magic_0;
    int32_t             dummy_1;
    int32_t             magic_1;
    int16_t             dummy_2;
    int8_t              filler1[470];
    struct {
        int32_t flags;                          /* 0x200 */
#define PR_F_CONFED             0x00000080

        int8_t          dummy_0;
        int8_t          disk_number;
        int8_t          channel;
        int8_t          device;
        int32_t         magic_0;
        int32_t         dummy_1;
        int32_t         dummy_2;                /* 0x210 */
        int32_t         disk_secs;
        int32_t         dummy_3;
        int16_t         dummy_4;
        int8_t          status;
#define PR_S_DEFINED            0x01
#define PR_S_ONLINE             0x02
#define PR_S_OFFLINE            0x10

        int8_t          type;
#define PR_T_STRIPE             0x00
#define PR_T_MIRROR             0x01
#define PR_T_STRIPE_MIRROR      0x04
#define PR_T_SPAN               0x08

        u_int8_t        total_disks;            /* 0x220 */
        u_int8_t        raid0_shift;
        u_int8_t        raid0_disks;
        u_int8_t        array_number;
        u_int32_t       total_secs;
        u_int16_t       cylinders;
        u_int8_t        heads;
        u_int8_t        sectors;
        int32_t         magic_1;
        int32_t         dummy_5;                /* 0x230 */
        struct {
            int16_t     dummy_0;
            int8_t      channel;
            int8_t      device;
            int32_t     magic_0;
            int32_t     disk_number;
        } disk[8];
    } raid;
    int32_t             filler2[346];
    uint32_t            checksum;
};


static unsigned long calc_pdcblock_offset (int fd) {
	unsigned long lba = 0;
	struct hd_big_geometry g;
	long sectors;
	int sector_size = 1;
	
	if (ioctl(fd, HDIO_GETGEO_BIG_RAW, &g))
	    return -1;
	    
	if (ioctl(fd, BLKGETSIZE, &sectors))
	    return -1;
	
	if (ioctl(fd, BLKSSZGET, &sector_size))
	    return -1;

	if (!sector_size || !sectors || !g.cylinders || !g.heads || !g.sectors)
	    return -1;

	sector_size /= 512;
	g.cylinders = (sectors / (g.heads * g.sectors)) / sector_size;

	lba = g.cylinders * (g.heads*g.sectors);
	lba = lba - g.sectors;
	    
	return lba;
}


static int read_disk_sb (int fd, unsigned char *buffer,int bufsize)
{
	int ret = -1;
	char bh[4096];
	unsigned long long sb_offset;
	
	/*
	 * Calculate the position of the superblock,
	 * it's at first sector of the last cylinder
	 */
	sb_offset = calc_pdcblock_offset(fd) * 512;
	if (sb_offset == -1)
	    return -1;
	
	lseek64(fd, sb_offset, SEEK_SET);
	read (fd, buffer, bufsize);

	ret = 0;

	return ret;
}

static unsigned int calc_sb_csum (unsigned int* ptr)
{	
	unsigned int sum;
	int count;
	
	sum = 0;
	for (count=0;count<511;count++)
		sum += *ptr++;
	
	return sum;
}

static int check_disk_sb (void)
{
	return 0;
}

int pdc_dev_running_raid(int fd)
{
	int i;
	struct promise_raid_conf *prom;
	unsigned char block[4096];

	if (read_disk_sb(fd,(unsigned char*)&block,sizeof(block)))
	    return -1;

	prom = (struct promise_raid_conf*)&block[0];
	
	if (!strcmp(prom->promise_id, "Promise Technology, Inc.") &&
		(prom->checksum == calc_sb_csum((unsigned int*)prom)))
	    return 1;

	return 0;
}
