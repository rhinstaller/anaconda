#include <sys/types.h>
#include <sys/io.h>
#include <sys/stat.h>
#include <sys/vm86.h>
#include <sys/syscall.h>
#include <sys/mman.h>
#include <assert.h>
#include <ctype.h>
#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>
#include <netinet/in.h>
#include "vbe.h"
#include "vesamode.h"
#include "lrmi.h"
#ident "$Id$"

/* Callback for qsort(). */
static int compare_16(const void *i1, const void *i2)
{
	const u_int16_t *I1, *I2;
	I1 = (const u_int16_t*) i1;
	I2 = (const u_int16_t*) i2;
	if(*I1 < *I2) return -1;
	if(*I1 > *I2) return 1;
	return 0;
}

int main(int argc, char **argv)
{
	struct vbe_info *vbe_info = NULL;
	struct vbe_mode_info *mode_info = NULL;
	u_int16_t *mode_list = NULL;
	int mode_count = 0;
	float vesa_version;

	/* Get basic information. */
	vbe_info = vbe_get_vbe_info();
	if(vbe_info == NULL) {
		printf("VESA BIOS Extensions not detected.\n");
		exit(0);
	}

	/* Print the signature, should be "VESA <digit>.<digit>". */
	printf("%c%c%c%c %d.%d detected.\n",
	       vbe_info->signature[0], vbe_info->signature[1],
	       vbe_info->signature[2], vbe_info->signature[3],
	       vbe_info->version[1], vbe_info->version[0]);
	vesa_version =  (vbe_info->version[1]) + (vbe_info->version[0]) / 10.0;

	/* List supported standard modes. */
	mode_list = vbe_info->mode_list.list;
	if(*mode_list != 0xffff) {
		printf("Supported modes:\n");
	}
	/* Count the number of modes. */
	for(;*mode_list != 0xffff; mode_list++) {
		mode_count++;
	}
	/* Sort the mode list, because my ATI doesn't.  Grrr... */
	mode_list = vbe_info->mode_list.list;
	if(*mode_list != 0xffff) {
		qsort(mode_list, mode_count, sizeof(u_int16_t), compare_16);
	}
	/* Dump info about the video mode. */
	for(;*mode_list != 0xffff; mode_list++) {
		int j;
		/* Mode number. */
		printf("0x%03x\t", *mode_list);
		for(j = 0; known_vesa_modes[j].x != 0; j++) {
		/* If it's a standard mode, print info about it. */
		if(known_vesa_modes[j].number == *mode_list) {
			printf("Specs list this as %dx%d, %d colors.",
			       known_vesa_modes[j].x,
			       known_vesa_modes[j].y,
			       known_vesa_modes[j].colors);
		}}
		printf("\n");
		/* Get mode information from the BIOS.  Should never fail. */
		mode_info = vbe_get_mode_info(*mode_list);
		if(mode_info == NULL) {
			printf("Get mode information not supported by BIOS.\n");
			exit(0);
		}

		/* Report what the BIOS says about the mode, should agree
		   with VESA on standard modes. */
		if(mode_info->w && mode_info->h && mode_info->bpp) {
			printf("\tBIOS reports this as %dx%d, %d bpp",
			       mode_info->w, mode_info->h,
			       mode_info->bpp);
		}
		if(mode_info->bytes_per_scanline) {
			printf(", %d bytes per scanline.",
			       mode_info->bytes_per_scanline);
		}
		printf("\n");
		/* Check the 'supported' bit.  Should be set, because this is
		   in the main supported modes list. */
		printf("\t%s, ", mode_info->mode_attributes.supported ?
		       "Supported" : "Not supported");
		/* Color?  Graphics? */
		printf("%s ", mode_info->mode_attributes.color ?
		       "Color" : "Monochrome");
		printf("%s.\n", mode_info->mode_attributes.graphics ?
		       "Graphics" : "Text");
		/* Check for LFB stuff.  Ralf's list says that you need to
		   query with bit 14 set to check if an LFB version of the mode
		   is available, but the ATI always returns true. */
		if(vesa_version >= 2.0) {
			/* Regular info about the current mode. */
			struct vbe_mode_info *info = NULL;
			printf("\t%sVGA compatible.\n",
			       mode_info->mode_attributes.not_vga_compatible ?
			       "Not " : "");
			printf("\tThis is %san LFB mode.\n",
			       mode_info->mode_attributes.lfb ?
			       "" : "not ");
			/* Info about the LFB variant mode (bit 14 set). */
			info = vbe_get_mode_info(*mode_list |
						 VBE_LINEAR_FRAMEBUFFER);
			if(info) {
				if(info->mode_attributes.lfb) {
					printf("\tLFB variant available.\n");
				}
				free(info);
			}
			if((mode_info->mode_attributes.lfb) ||
			   (info && (info->mode_attributes.lfb))) {
				printf("\tLFB at address 0x%8x.\n",
				       mode_info->linear_buffer_address);
			}
		}
		/* Memory model: EGA = icky bit planes, packed-pixel = palette,
		   direct color = LFB compatible but needs bank switches. */
		printf("\tMemory model: ");
		switch(mode_info->memory_model) {
			case memory_model_text: {
				printf("text.\n");
				break;
			}
       			case memory_model_cga: {
				printf("CGA.\n");
				break;
			}
       			case memory_model_hgc: {
				printf("Hercules.\n");
				break;
			}
       			case memory_model_ega16: {
				printf("EGA.\n");
				break;
			}
       			case memory_model_packed_pixel: {
				printf("packed-pixel.\n");
				break;
			}
       			case memory_model_sequ256: {
				printf("sequential 256.\n");
				break;
			}
       			case memory_model_direct_color: {
				printf("direct color.\n");
				break;
			}
       			case memory_model_yuv: {
				printf("YUV.\n");
				break;
			}
			default : {
				printf("unknown/OEM.\n");
			}
		}
	}
	return 0;
}
