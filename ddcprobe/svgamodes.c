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
	struct vm86_struct info;
	struct vbe_info *vbe_info = NULL;
	struct mode_info *mode_info = NULL;
	unsigned char *memory = NULL;
	u_int16_t *mode_list = NULL;
	float vesa_version;

	/* Get a copy of the low megabyte for use as an address space. */
	memory = vm86_ram_alloc();
	if(memory == MAP_FAILED) {
		printf("Couldn't allocate needed memory!\n");
		exit(0);
	}

	/* Set up registers for a real-mode interrupt call. */
	memset(&info, 0, sizeof(info));
	info.regs.eax = 0x4f00;
	info.regs.es  = 0x4000;
	info.regs.edi = 0x0000;
	info.regs.ss  = 0x9000;
	info.regs.esp = 0x0000;
	info.flags    = 0;

	/* Call the BIOS. */
	memset(&memory[info.regs.es * 16 + info.regs.edi], 0, 1024);
	bioscall(0x10, &info.regs, memory);

	/* Interpret results. */
	vbe_info = (struct vbe_info*) &memory[info.regs.es*16 + info.regs.edi];

	if((info.regs.eax & 0xff) != 0x4f) {
		printf("VESA BIOS Extensions not detected.\n");
		vm86_ram_free(memory);
		exit(0);
	}

	if((info.regs.eax & 0xffff) != 0x004f) {
		printf("VESA Get SuperVGA Information request failed.\n");
		vm86_ram_free(memory);
		exit(0);
	}

	/* Signature. */
	printf("%c%c%c%c %d.%d detected.\n",
	       vbe_info->signature[0], vbe_info->signature[1],
	       vbe_info->signature[2], vbe_info->signature[3],
	       vbe_info->version[1], vbe_info->version[0]);
	vesa_version =  (vbe_info->version[1]) + (vbe_info->version[0]) / 10.0;

	/* List supported standard modes. */
	mode_list = (u_int16_t*) &memory[vbe_info->mode_list.addr.seg * 16 +
					 vbe_info->mode_list.addr.ofs];
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
		memset(&info, 0, sizeof(info));
		info.regs.eax = 0x4f01;
		info.regs.ecx = *mode_list;
		info.regs.es  = 0x5000;
		info.regs.edi = 0x0000;
		info.regs.ss  = 0x9000;
		info.regs.esp = 0x0000;
		info.flags    = 0;
		memset(&memory[info.regs.es * 16 + info.regs.edi], 0, 1024);
		bioscall(0x10, &info.regs, memory);
		mode_info = (struct mode_info*) &memory[info.regs.es * 16 +
							info.regs.edi];
		if((info.regs.eax & 0xff) != 0x4f) {
			printf("Get mode information not supported.\n");
			vm86_ram_free(memory);
			exit(0);
		}

		if((info.regs.eax & 0xffff) == 0x004f) {
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
					printf("direct color (24-bit).\n");
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
	}

	return 0;
}
