/*
   hpt: Highpoint Fake Raid reader
	  Copyright (C) 2003

   Based off of pdc.c
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


struct hpt_raid_conf
{
       int8_t  filler1[32];
       u_int32_t       magic;
#define HPT_MAGIC_OK   0x5a7816f0
#define HPT_MAGIC_BAD  0x5a7816fd  

       u_int32_t       magic_0;
       u_int32_t       magic_1;
       u_int32_t       order;  
#define HPT_O_MIRROR   0x01  
#define HPT_O_STRIPE   0x02
#define HPT_O_OK       0x04

       u_int8_t        raid_disks;
       u_int8_t        raid0_shift; 
       u_int8_t        type;
#define HPT_T_RAID_0   0x00 
#define HPT_T_RAID_1   0x01
#define HPT_T_RAID_01_RAID_0   0x02
#define HPT_T_SPAN             0x03
#define HPT_T_RAID_3           0x04   
#define HPT_T_RAID_5           0x05
#define HPT_T_SINGLEDISK       0x06
#define HPT_T_RAID_01_RAID_1   0x07

       u_int8_t        disk_number;
       u_int32_t       total_secs; 
       u_int32_t       disk_mode;  
       u_int32_t       boot_mode;
       u_int8_t        boot_disk; 
       u_int8_t        boot_protect;
       u_int8_t        error_log_entries;
       u_int8_t        error_log_index;  
       struct
       {
               u_int32_t       timestamp;
               u_int8_t        reason;   
#define HPT_R_REMOVED          0xfe      
#define HPT_R_BROKEN           0xff      

               u_int8_t        disk;
               u_int8_t        status;
               u_int8_t        sectors;
               u_int32_t       lba;
       } errorlog[32];
       u_int8_t        filler[60];
};


static int read_disk_sb (int fd, unsigned char * buffer, int bufsize)
{
	if ((lseek64(fd, 4096, SEEK_SET)) == -1) return -1;
	if ((read(fd, buffer, bufsize)) < bufsize) return -1;

	return 0;
}


int hpt_dev_running_raid(int fd)
{
    int i;
	struct hpt_raid_conf *prom;
	unsigned char block[4096];

	if (read_disk_sb(fd,(unsigned char*)&block,sizeof(block)))
	    return -1;
	
	prom = (struct hpt_raid_conf*)&block[512];

	if (prom->magic !=  0x5a7816f0) {
		//		fprintf(stderr, "hptraid: bad magic!\n");
		return 0;
	}

    if (prom->type) {
		//        fprintf(stderr, "hptraid: only RAID0 is supported currently\n");
        return 0;
    }

    i = prom->disk_number;
    if (i<0)
        return 0;
    if (i>8)
        return 0;

	//	fprintf(stderr, "type is %d, i is %d\n", prom->type, i);
	
	return 1;
}

#if 0
int main(int argc, char ** argv) {
  int fd, rc;

  fd = open("/dev/ataraid/d0", O_RDONLY);
  rc = hpt_dev_running_raid(fd);
  if (rc != 1) {
	  //	fprintf(stderr, "no hpt magic\n");
	close(fd);
	return 1;
  } else {
	  //	  fprintf(stderr, "we have hpt magic\n");
	  close(fd);
  }

  return 0;
}
#endif
