/*
 * edd.h - real mode bios library for discovering EDD capabilities of
 *         BIOS drives
 *
 * Matt Wilson <msw@redhat.com>
 *
 * Copyright 2000 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * library public license.
 *
 * You should have received a copy of the GNU Library Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#ifndef __EDD_H__
#define __EDD_H__

#include <sys/types.h>

#define EDD_ERROR 1
#define EDD_SUCCESS 0

#define EDD_CAPABILITY_EDA 		1 << 0
#define EDD_CAPABILITY_REMOVABLE 	1 << 1
#define EDD_CAPABILITY_EDD		1 << 2

typedef struct EDDParameters_t {
  u_int16_t buffer_size;
  u_int16_t info_flags;
  u_int32_t cyls;
  u_int32_t heads;
  u_int32_t sectors;
  u_int64_t total_sectors;
  u_int16_t bytes_per_sector;
  /* -- 2.0+ -- */
  u_int32_t parameters;
  /* -- 3.0 -- */
  u_int16_t path_signature;
  unsigned char path_length;
  unsigned char path_reserved[3];
  unsigned char path_bus[3];  
  unsigned char path_interface[8];
  unsigned char path_interface_path[8];
  unsigned char path_device_path[8];
  unsigned char tail_reserved;
  unsigned char checksum;
} EDDParameters;

typedef struct EDDCapability_t {
  int drive;
  struct {
    int major, minor;
  } version;
  int eda : 1;
  int removable : 1;
  int edd : 1;
} EDDCapability;

EDDCapability * edd_supported(int drive);
EDDParameters * edd_get_parameters (EDDCapability *ec);


#endif /* __EDD_H__ */
