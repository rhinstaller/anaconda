#include <sys/types.h>
#include <sys/vm86.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <assert.h>
#include "bioscall.h"
#include "vbe.h"

struct mode_info *vbe_get_mode_info(u_int16_t mode)
{
	struct vm86_regs regs;
	unsigned char *ram;
	struct mode_info *ret = NULL;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f01;
	regs.ecx = mode;
	regs.es = 0x3000;
	regs.edi = 0x3000;

	/* Just to be sure... */
	assert(regs.es != BIOSCALL_START_SEG);

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return NULL;
	}

	/* Do it. */
	bioscall(0x10, &regs, ram);

	/* Check for successful return. */
	if((regs.eax & 0xffff) != 0x004f) {
		return NULL;
	}

	/* Get memory for return. */
	ret = malloc(sizeof(struct mode_info));
	if(ret == NULL) {
		return NULL;
	}

	/* Copy the buffer for return. */
	memcpy(ret, &ram[regs.es * 16 + regs.edi], sizeof(struct mode_info));

	/* Clean up and return. */
	vm86_ram_free(ram);
	return ret;
}

struct vbe_info *vbe_get_vbe_info()
{
	struct vm86_regs regs;
	unsigned char *ram;
	struct vbe_info *ret = NULL;
	u_int16_t *modes;
	int mode_count = 0;

	memset(&regs, 0, sizeof(regs));
	regs.eax = 0x4f00;
	regs.es = 0x3000;
	regs.edi = 0x3000;

	/* Just to be sure... */
	assert(regs.es != BIOSCALL_START_SEG);

	/* Get memory for the bios call. */
	ram = vm86_ram_alloc();
	if(ram == MAP_FAILED) {
		return NULL;
	}

	/* Do it. */
	bioscall(0x10, &regs, ram);

	/* Check for successful return code. */
	if((regs.eax & 0xffff) != 0x004f) {
		return NULL;
	}

	/* Count the number of supported video modes. */
	ret = (struct vbe_info*) &ram[regs.es * 16 + regs.edi];
	modes = (u_int16_t*) &ram[ret->mode_list.addr.seg * 16 +
				  ret->mode_list.addr.ofs];
	for(mode_count = 0; (*modes != 0xffff); modes++) {
		mode_count++;
	}
	modes = (u_int16_t*) &ram[ret->mode_list.addr.seg * 16 +
				  ret->mode_list.addr.ofs];

	/* Get enough memory to hold the mode list, too. */
	ret = malloc(sizeof(struct vbe_info) +
		     (mode_count + 1) * sizeof(u_int16_t) +
		     strlen(&ram[ret->oem_name.addr.seg * 16 +
				 ret->oem_name.addr.ofs]));
	if(ret == NULL) {
		return NULL;
	}

	/* Copy the static parts of the buffer out. */
	memcpy(ret, &ram[regs.es * 16 + regs.edi], sizeof(struct vbe_info));

	/* Copy the modes list and set the pointer to it. */
	memcpy(ret + 1, modes, (mode_count + 1) * sizeof(u_int16_t));
	ret->mode_list.list = (u_int16_t*) (ret + 1);
	memcpy(&ret->mode_list.list[mode_count],
	       &ram[ret->oem_name.addr.seg * 16 + ret->oem_name.addr.ofs],
	       strlen(&ram[ret->oem_name.addr.seg*16+ret->oem_name.addr.ofs]));

	vm86_ram_free(ram);
	return ret;
}
