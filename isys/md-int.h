/*
   md.h : Multiple Devices driver for Linux
          Copyright (C) 1994-96 Marc ZYNGIER
	  <zyngier@ufr-info-p7.ibp.fr> or
	  <maz@gloups.fdn.fr>
	  
   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2, or (at your option)
   any later version.
   
   You should have received a copy of the GNU General Public License
   (for example /usr/src/linux/COPYING); if not, write to the Free
   Software Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.  
*/

#ifndef MD_INT_H
#define MD_INT_H

/* don't include the kernel RAID header! */
#define _MD_H

typedef unsigned int md_u32;
typedef unsigned short md_u16;
typedef unsigned char md_u8;

#include <linux/major.h>
#include <sys/ioctl.h>

/*
 * Different major versions are not compatible.
 * Different minor versions are only downward compatible.
 * Different patchlevel versions are downward and upward compatible.
 */

struct md_version {
	int major;
	int minor;
	int patchlevel;
};

/*
 * default readahead
 */
#define MD_READAHEAD	(256 * 1024)

/* These are the ioctls for md versions < 0.50 */
#define REGISTER_MD_DEV		_IO (MD_MAJOR, 1)
#define START_MD     		_IO (MD_MAJOR, 2)
#define STOP_MD      		_IO (MD_MAJOR, 3)

/* status */
#define RAID_VERSION            _IOR (MD_MAJOR, 0x10, struct md_version)
#define GET_ARRAY_INFO          _IOR (MD_MAJOR, 0x11, md_array_info_t)
#define GET_DISK_INFO           _IOR (MD_MAJOR, 0x12, md_disk_info_t)
#define PRINT_RAID_DEBUG        _IO (MD_MAJOR, 0x13)

/* configuration */
#define CLEAR_ARRAY             _IO (MD_MAJOR, 0x20)
#define ADD_NEW_DISK            _IOW (MD_MAJOR, 0x21, md_disk_info_t)
#define HOT_REMOVE_DISK         _IO (MD_MAJOR, 0x22)
#define SET_ARRAY_INFO          _IOW (MD_MAJOR, 0x23, md_array_info_t)
#define SET_DISK_INFO           _IO (MD_MAJOR, 0x24)
#define WRITE_RAID_INFO         _IO (MD_MAJOR, 0x25)
#define UNPROTECT_ARRAY         _IO (MD_MAJOR, 0x26)
#define PROTECT_ARRAY           _IO (MD_MAJOR, 0x27)
#define HOT_ADD_DISK            _IO (MD_MAJOR, 0x28)

/* usage */
#define RUN_ARRAY               _IOW (MD_MAJOR, 0x30, struct md_param)
#define START_ARRAY             _IO (MD_MAJOR, 0x31)
#define STOP_ARRAY              _IO (MD_MAJOR, 0x32)
#define STOP_ARRAY_RO           _IO (MD_MAJOR, 0x33)
#define RESTART_ARRAY_RW        _IO (MD_MAJOR, 0x34)


/* for raid < 0.50 only */
#define MD_PERSONALITY_SHIFT	16

#define MD_RESERVED       0UL
#define LINEAR            1UL
#define STRIPED           2UL
#define RAID0             STRIPED
#define RAID1             3UL
#define RAID5             4UL
#define TRANSLUCENT       5UL
#define LVM               6UL
#define MAX_PERSONALITY   7UL

/*
 * MD superblock.
 *
 * The MD superblock maintains some statistics on each MD configuration.
 * Each real device in the MD set contains it near the end of the device.
 * Some of the ideas are copied from the ext2fs implementation.
 *
 * We currently use 4096 bytes as follows:
 *
 *	word offset	function
 *
 *	   0  -    31	Constant generic MD device information.
 *        32  -    63   Generic state information.
 *	  64  -   127	Personality specific information.
 *	 128  -   511	12 32-words descriptors of the disks in the raid set.
 *	 512  -   911	Reserved.
 *	 912  -  1023	Disk specific descriptor.
 */

/*
 * If x is the real device size in bytes, we return an apparent size of:
 *
 *	y = (x & ~(MD_RESERVED_BYTES - 1)) - MD_RESERVED_BYTES
 *
 * and place the 4kB superblock at offset y.
 */
#define MD_RESERVED_BYTES		(64 * 1024)
#define MD_RESERVED_SECTORS		(MD_RESERVED_BYTES / 512)
#define MD_RESERVED_BLOCKS		(MD_RESERVED_BYTES / BLOCK_SIZE)

#define MD_NEW_SIZE_SECTORS(x)		((x & ~(MD_RESERVED_SECTORS - 1)) - MD_RESERVED_SECTORS)
#define MD_NEW_SIZE_BLOCKS(x)		((x & ~(MD_RESERVED_BLOCKS - 1)) - MD_RESERVED_BLOCKS)

#define MD_SB_BYTES			4096
#define MD_SB_WORDS			(MD_SB_BYTES / 4)
#define MD_SB_BLOCKS			(MD_SB_BYTES / BLOCK_SIZE)
#define MD_SB_SECTORS			(MD_SB_BYTES / 512)

/*
 * The following are counted in 32-bit words
 */
#define	MD_SB_GENERIC_OFFSET		0
#define MD_SB_PERSONALITY_OFFSET	64
#define MD_SB_DISKS_OFFSET		128
#define MD_SB_DESCRIPTOR_OFFSET		992

#define MD_SB_GENERIC_CONSTANT_WORDS	32
#define MD_SB_GENERIC_STATE_WORDS	32
#define MD_SB_GENERIC_WORDS		(MD_SB_GENERIC_CONSTANT_WORDS + MD_SB_GENERIC_STATE_WORDS)
#define MD_SB_PERSONALITY_WORDS		64
#define MD_SB_DISKS_WORDS		384
#define MD_SB_DESCRIPTOR_WORDS		32
#define MD_SB_RESERVED_WORDS		(1024 - MD_SB_GENERIC_WORDS - MD_SB_PERSONALITY_WORDS - MD_SB_DISKS_WORDS - MD_SB_DESCRIPTOR_WORDS)
#define MD_SB_EQUAL_WORDS		(MD_SB_GENERIC_WORDS + MD_SB_PERSONALITY_WORDS + MD_SB_DISKS_WORDS)
#define MD_SB_DISKS			(MD_SB_DISKS_WORDS / MD_SB_DESCRIPTOR_WORDS)

/*
 * Device "operational" state bits
 */
#define MD_DISK_FAULTY		0 /* disk is faulty / operational */
#define MD_DISK_ACTIVE		1 /* disk is running or spare disk */
#define MD_DISK_SYNC		2 /* disk is in sync with the raid set */

typedef struct md_device_descriptor_s {
	md_u32 number;		/* 0 Device number in the entire set	      */
	md_u32 major;		/* 1 Device major number		      */
	md_u32 minor;		/* 2 Device minor number		      */
	md_u32 raid_disk;	/* 3 The role of the device in the raid set   */
	md_u32 state;		/* 4 Operational state			      */
	md_u32 reserved[MD_SB_DESCRIPTOR_WORDS - 5];
} md_descriptor_t;

#define MD_SB_MAGIC		0xa92b4efc

/*
 * Superblock state bits
 */
#define MD_SB_CLEAN		0
#define MD_SB_ERRORS		1

typedef struct md_superblock_s {
	/*
	 * Constant generic information
	 */
	md_u32 md_magic;		/*  0 MD identifier 			      */
	md_u32 major_version;	/*  1 major version to which the set conforms */
	md_u32 minor_version;	/*  2 minor version ...			      */
	md_u32 patch_version;	/*  3 patchlevel version ...		      */
	md_u32 gvalid_words;	/*  4 Number of used words in this section    */
	md_u32 set_magic;	/*  5 Raid set identifier		      */
	md_u32 ctime;		/*  6 Creation time			      */
	md_u32 level;		/*  7 Raid personality			      */
	md_u32 size;		/*  8 Apparent size of each individual disk   */
	md_u32 nr_disks;	/*  9 total disks in the raid set	      */
	md_u32 raid_disks;	/* 10 disks in a fully functional raid set    */
	md_u32 md_minor;	/* 11 preferred MD minor device number	      */
	md_u32 gstate_creserved[MD_SB_GENERIC_CONSTANT_WORDS - 12];

	/*
	 * Generic state information
	 */
	md_u32 utime;		/*  0 Superblock update time		      */
	md_u32 state;		/*  1 State bits (clean, ...)		      */
	md_u32 active_disks;	/*  2 Number of currently active disks	      */
	md_u32 working_disks;	/*  3 Number of working disks		      */
	md_u32 failed_disks;	/*  4 Number of failed disks		      */
	md_u32 spare_disks;	/*  5 Number of spare disks		      */
	md_u32 gstate_sreserved[MD_SB_GENERIC_STATE_WORDS - 6];

	/*
	 * Personality information
	 */
	md_u32 layout;		/*  0 the array's physical layout	      */
	md_u32 chunk_size;	/*  1 chunk size in bytes		      */
	md_u32 pstate_reserved[MD_SB_PERSONALITY_WORDS - 2];

	/*
	 * Disks information
	 */
	md_descriptor_t disks[MD_SB_DISKS];

	/*
	 * Reserved
	 */
	md_u32 reserved[MD_SB_RESERVED_WORDS];

	/*
	 * Active descriptor
	 */
	md_descriptor_t descriptor;

} md_superblock_t;

/*
 * options passed in raidstart:
 */

#define MAX_CHUNK_SIZE (4096*1024)

struct md_param
{
	int			personality;	/* 1,2,3,4 */
	int			chunk_size;	/* in bytes */
	int			max_fault;	/* unused for now */
};

typedef struct md_array_info_s {
	/*
	 * Generic constant information
	 */
	md_u32 major_version;
	md_u32 minor_version;
	md_u32 patch_version;
	md_u32 ctime;
	md_u32 level;
	md_u32 size;
	md_u32 nr_disks;
	md_u32 raid_disks;
	md_u32 md_minor;
	md_u32 not_persistent;

	/*
	 * Generic state information
	 */
	md_u32 utime;		/*  0 Superblock update time		      */
	md_u32 state;		/*  1 State bits (clean, ...)		      */
	md_u32 active_disks;	/*  2 Number of currently active disks	      */
	md_u32 working_disks;	/*  3 Number of working disks		      */
	md_u32 failed_disks;	/*  4 Number of failed disks		      */
	md_u32 spare_disks;	/*  5 Number of spare disks		      */

	/*
	 * Personality information
	 */
	md_u32 layout;		/*  0 the array's physical layout	      */
	md_u32 chunk_size;	/*  1 chunk size in bytes		      */

} md_array_info_t;

typedef struct md_disk_info_s {
	/*
	 * configuration/status of one particular disk
	 */
	md_u32 number;
	md_u32 major;
	md_u32 minor;
	md_u32 raid_disk;
	md_u32 state;

} md_disk_info_t;


/*
 * Supported RAID5 algorithms
 */
#define RAID5_ALGORITHM_LEFT_ASYMMETRIC		0
#define RAID5_ALGORITHM_RIGHT_ASYMMETRIC	1
#define RAID5_ALGORITHM_LEFT_SYMMETRIC		2
#define RAID5_ALGORITHM_RIGHT_SYMMETRIC		3

#endif _MD_H
