/*
 * edd.c - real mode bios library for discovering EDD capabilities of
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

#include <sys/io.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "lrmi.h"
#include "edd.h"

static int edd_lrmi_initialized = 0;

static int
edd_lrmi_init (void) {
  if (edd_lrmi_initialized)
    return EDD_SUCCESS;

  if (iopl(3)) {
    fprintf (stderr, "ERROR: failed to set iopl permissions\n");
    return EDD_ERROR;
  }

  if (ioperm(0, 0x400, 1)) {
    fprintf (stderr, "ERROR: failed to set ioperm permissions\n");
    return EDD_ERROR;
  }    

  /* Initialize LRMI. */
  if(LRMI_init() == 1) {
    edd_lrmi_initialized = 1;
    return EDD_SUCCESS;
  }

  fprintf (stderr, "ERROR: failed to initialize lrmi library\n");
  return EDD_ERROR;
}

EDDParameters *
edd_get_parameters (EDDCapability *ec)
{
  struct LRMI_regs regs;
  EDDParameters *ep, *ret;

  return NULL;

  if (edd_lrmi_init() == EDD_ERROR) {
    return NULL;
  }

  (unsigned char *) ep = LRMI_alloc_real(sizeof(EDDParameters));
  if (ep == NULL) {
    return NULL;
  }
  
  memset(ep, 0, sizeof(EDDParameters));
  memset(&regs, 0, sizeof(regs));

  if (ec->version.major == 3)
    ep->buffer_size = 0x42;
  else if (ec->version.major == 2)
    ep->buffer_size = 0x1e;
  else
    ep->buffer_size = 0x1a;
  
  regs.eax = 0x4800;
  regs.edx = ec->drive & 0x00ff;
  regs.es = ((u_int32_t) ep) >> 4;
  regs.edi = ((u_int32_t) ep) & 0x0f;
  
  printf ("%p -> 0x%x 0x%x\n", ep, regs.es, regs.edi);

  if(LRMI_int(0x13, &regs) == 0) {
    LRMI_free_real((unsigned char *) ep);
    return NULL;
  }

  /* XXX check return */
  printf ("0x%x\n", regs.eax);
  printf ("0x%x\n", regs.flags);
  
  ret = malloc (sizeof (EDDParameters));
  if (ret == NULL) {
    fprintf (stderr, "out of memory\n");
    abort();
  }
  memcpy (ret, ep, sizeof (EDDParameters));
  LRMI_free_real((unsigned char *) ep);

  return ret;
}

EDDCapability *
edd_supported(int drive)
{
  struct LRMI_regs regs;

  FILE *f = fopen("/proc/cmdline", "r");
  if (f) {
      char buf[100];
      fgets(buf, sizeof(buf) - 1, f);
      fclose(f);
      if (strstr(buf, "lba32")) {
	  EDDCapability *ec = malloc (sizeof (EDDCapability));
	  ec->edd = 1;
	  return ec;
      }
      return NULL;
  }
  return NULL; 
 
  if (edd_lrmi_init() == EDD_ERROR) {
    return NULL;
  }

  memset(&regs, 0, sizeof(regs));
  regs.eax = 0x4100;
  regs.ebx = 0x55aa;
  regs.edx = drive & 0xff;
  
  /* Do it. */
  if (LRMI_int (0x13, &regs) == 0) {
    return NULL;
  }
  
  /* Check for successful return. */
  if(regs.ebx == 0xaa55) {
    /* Supported, report capabilities */
    EDDCapability *ec = malloc (sizeof (EDDCapability));
    memset (ec, 0, sizeof (EDDCapability));

    if (ec == NULL) {
      fprintf (stderr, "out of memory\n");
      abort();
    }
    
    if ((regs.eax & 0xff00) == 0x0100) {
      ec->version.major = 1;
      ec->version.minor = 0;
    } else if ((regs.eax & 0xff00) == 0x2000) {
      ec->version.major = 2;
      ec->version.minor = 0;
    } else if ((regs.eax & 0xff00) == 0x2100) {
      ec->version.major = 2;
      ec->version.minor = 1;
    } else if ((regs.eax & 0xff00) == 0x3000) {
      ec->version.major = 3;
      ec->version.minor = 0;
    } else {
      fprintf (stderr, "WARNING: Unknown EDD version 0x%x supported\n",
	       regs.eax & 0xff00);
    }
    if (regs.ecx & EDD_CAPABILITY_EDA)
      ec->eda = 1;

    if (regs.ecx & EDD_CAPABILITY_REMOVABLE)
      ec->removable = 1;

    if (regs.ecx & EDD_CAPABILITY_EDD)
      ec->edd = 1;

    ec->drive = drive;

    return ec;
  } else {
    /* Not supported. */
    return NULL;
  }
}

#ifdef TESTING
int
main (void)
{
  int i;
  EDDCapability *ec;
  EDDParameters *ep;
  
  for (i = 0x80; i < 0x90; i++) {
    if ((ec = edd_supported(i))) {
      printf ("edd version %d.%d supported on 0x%x\n", ec->version.major, 
	      ec->version.minor, i);
      printf ("    extended disk access %s\n",
	      ec->eda ? "supported" : "not supported");
      printf ("    removable media functions %s\n",
	      ec->removable ? "supported" : "not supported");
      printf ("    edd functions %s\n",
	      ec->edd ? "supported" : "not supported");
      ep = edd_get_parameters (ec);
      if (ep) {
	printf ("heads: %d   cyl: %d   sec/track: %d\n",
		ep->heads, ep->cyls, ep->sectors);
	free (ep);
      } else
	printf ("get_parameters call failed\n");
      free (ec);
    } else
      printf ("edd not supported on 0x%x\n", i);
  }

  return 0;
}
#endif




