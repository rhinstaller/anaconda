/*
   silraid: Silicon Image Fake Raid reader
	  Copyright (C) 2003

   Based off of anaconda/isys/pdc.c and linux/drivers/ide/raid/silraid.c
*/


#include <unistd.h>
#include <sys/ioctl.h>
#include <stdio.h>
#include <fcntl.h>

#ifdef DIET
#include <sys/mount.h>
#else
#include <linux/fs.h>
#endif

#include <string.h>


#ifdef DIET
typedef char char16_t;
typedef unsigned char u_int8_t;
typedef unsigned short u_int16_t;
typedef uint32_t u_int32_t;
#else
typedef unsigned int uint32_t;
#endif

#ifndef BLKSSZGET
#define BLKSSZGET  _IO(0x12,104)/* get block device sector size */
#endif

#ifndef HDIO_GETGEO_BIG_RAW
#define HDIO_GETGEO_BIG_RAW  0x0331

/* BIG GEOMETRY */
struct hd_big_geometry {
    unsigned char heads;
    unsigned char sectors;
    unsigned int cylinders;
    unsigned long start;
};
#endif

struct sil_raid_conf {
        char unknown[0x36];             /* 0x00 to 0x35 */
        char diskname[32];              /* 0x36 to 0x56 */
        char unknown2[0x6c-86];         /* 0x57 to 0x6B */
        unsigned int array_sectors;     /* 0x6C to 0x6F */
        char unknown2b[8];              /* 0x70 to 0x77 */
        unsigned int thisdisk_sectors;  /* 0x78 to 0x7B */
        char unknown2c[0xFF-0x7B];      /* 0x7C to 0xFF */
        char unknown3[4];               /* 0x100 to 0x103 */
        unsigned short PCI_DEV_ID;      /* 0x104 and 0x105 */
        unsigned short PCI_VEND_ID;     /* 0x106 and 0x107 */
        char unknown4[4];               /* 0x108 to 0x10B */
        unsigned char seconds;          /* 0x10C */
        unsigned char minutes;          /* 0x10D */
        unsigned char hour;             /* 0x10E */
        unsigned char day;              /* 0x10F */
        unsigned char month;            /* 0x110 */
        unsigned char year;             /* 0x111 */
        unsigned short raid0_sectors_per_stride; /* 0x112 */
        char unknown6[2];               /* 0x113 - 0x115 */
        unsigned char disk_in_set;      /* 0x116 */
        unsigned char raidlevel;        /* 0x117 */
        unsigned char disks_in_set;     /* 0x118 */
        char unknown7[0x12a - 0x118];   /* 0x118 - 0x12a */
        unsigned char idechannel;       /* 0x12b */
        char unknown8[0x13D-0x12B];     /* 0x12c - 0x13d */
        unsigned short checksum1;       /* 0x13e and 0x13f */
        char assumed_zeros[509-0x13f];
        unsigned short checksum2;       /* 0x1FE and 0x1FF */
} __attribute__((packed));



static unsigned long long calc_silblock_offset (int fd) {
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


static int read_disk_sb (int fd, unsigned char * buffer, int bufsize)
{
    unsigned long long sb_offset;

    /* 
     * Calculate the position of the superblock,
     * it's at the first sector of the last cylinder
     */
    sb_offset = calc_silblock_offset(fd);
    if (sb_offset == ((unsigned long long) -1))
	return -1;
    
    if ((lseek64(fd, sb_offset * 512, SEEK_SET)) == -1) return -1;
    if ((read(fd, buffer, bufsize)) < bufsize) return -1;
    
    return 0;
}

static unsigned short silraid_checksum(unsigned short *buffer)
{
        int i;
        int sum = 0;
        for (i=0; i<0x13f/2; i++)
                sum += buffer[i];
        return (-sum)&0xFFFF;
}

int silraid_dev_running_raid(int fd)
{
    struct sil_raid_conf *sil;
    unsigned char block[4096];

    if (read_disk_sb(fd,(unsigned char*)&block,sizeof(block)))
	return -1;
    
    sil = (struct sil_raid_conf*)&block[4096-512];

    if (sil->unknown[0] != 'Z') /* Need better check */
	return 0;

    if (sil->checksum1 != silraid_checksum((unsigned short*)sil))
	return 0;

    if (sil->raidlevel != 0) /* different raidlevel */
	return 0;

    return 1;
}

#if 0
int main(int argc, char ** argv) {
  int fd, rc;

  fd = open("/dev/ataraid/d0", O_RDONLY);
  rc = silraid_dev_running_raid(fd);
  if (rc != 1) {
	  //	fprintf(stderr, "no silraid magic\n");
	close(fd);
	return 1;
  } else {
	  //	  fprintf(stderr, "we have silraid magic\n");
	  close(fd);
  }

  return 0;
}
#endif
