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
#include "bioscall.h"
#ident "$Id$"

int main(int argc, char **argv)
{
	struct vbe_info *vbe_info = NULL;
	struct vbe_mode_info *mode_info = NULL;
	u_int16_t *mode_list = NULL;
	float vesa_version;

	/* Interpret results. */
	vbe_info = vbe_get_vbe_info();

	if(vbe_info == NULL) {
		printf("VESA BIOS Extensions not detected.\n");
		exit(0);
	}

	/* Signature. */
	printf("%c%c%c%c %d.%d detected.\n",
	       vbe_info->signature[0], vbe_info->signature[1],
	       vbe_info->signature[2], vbe_info->signature[3],
	       vbe_info->version[1], vbe_info->version[0]);
	vesa_version =  (vbe_info->version[1]) + (vbe_info->version[0]) / 10.0;

	/* List supported standard modes. */
	mode_list = vbe_info->mode_list.list;
	if(*mode_list != 0xffff) {
		printf("Supported standard modes:\n");
	}
	for(;*mode_list != 0xffff; mode_list++) {
		int j;
		printf("0x%03x\t", *mode_list);
		for(j = 0; known_vesa_modes[j].x != 0; j++) {
		if(known_vesa_modes[j].number == *mode_list) {
			printf("%dx%d, %d colors",
			       known_vesa_modes[j].x,
			       known_vesa_modes[j].y,
			       known_vesa_modes[j].colors);
		}}
		printf("\n");
		mode_info = vbe_get_mode_info(*mode_list);
		if(mode_info == NULL) {
			printf("Get mode information not supported.\n");
			exit(0);
		}

		if(mode_info->w && mode_info->h && mode_info->bpp) {
			printf("\tBIOS reports %dx%d, %d bpp",
			       mode_info->w, mode_info->h,
			       mode_info->bpp);
		}
		if(mode_info->bytes_per_scanline) {
			printf(", %d bytes per scanline.",
			       mode_info->bytes_per_scanline);
		}
		printf("\n");
		printf("\t%s, ", mode_info->mode_attributes & 0x01 ?
		       "Supported" : "Not supported");
		printf("%s ", mode_info->mode_attributes & 0x08 ?
		       "Color" : "Monochrome");
		printf("%s.\n", mode_info->mode_attributes & 0x10 ?
		       "Graphics" : "Text");
		if(vesa_version >= 2.0) {
			printf("\tLFB mode %s.\n",
			       mode_info->mode_attributes & 0x80 ?
			       "supported" : "not supported");
			printf("\t%sVGA compatible.\n",
			       mode_info->mode_attributes & 0x20 ?
			       "" : "Not ");
		}
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
