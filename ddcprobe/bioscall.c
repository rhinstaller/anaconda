#include <sys/types.h>
#include <sys/io.h>
#include <sys/stat.h>
#include <sys/vm86.h>
#include <sys/syscall.h>
#include <sys/mman.h>
#include <ctype.h>
#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>
#include <netinet/in.h>
#include "bioscall.h"
#ident "$Id$"

#ifndef SYS_vm86old
#ifdef SYS_vm86
#define SYS_vm86old SYS_vm86
#endif
#endif

/* Dump some of the interesting parts of a register struct to stdout. */
void dump_regs(struct vm86_regs *regs)
{
	printf("ax = 0x%04lx\n", regs->eax & 0xffff);
	printf("bx = 0x%04lx\n", regs->ebx & 0xffff);
	printf("cx = 0x%04lx\n", regs->ecx & 0xffff);
	printf("dx = 0x%04lx\n", regs->edx & 0xffff);
	printf("cs = 0x%04x\n", regs->cs  & 0xffff);
	printf("ip = 0x%08lx\n", regs->eip & 0xffffffff);
	printf("ss = 0x%04x\n", regs->ss  & 0xffff);
	printf("sp = 0x%08lx\n", regs->esp & 0xffffffff);
	printf("%04x:%08lx = (%ld)\n",
	       regs->cs & 0xffff, regs->eip,
	       regs->cs * 16 + regs->eip);
}

/* Call vm86, but do I/O that gets trapped. We could skip vm86() altogether,
   but then I'm not trying to emulate an entire CPU here.  Luckily, none of
   the I/O instructions (or push/pop) affect the flags, so we can leave them
   alone and just deal with performing the I/O operation that caused a return
   to 32-bit mode. */
void do_vm86(struct vm86_struct *vm, char *memory, unsigned stop_eip) {
	int ret;
	unsigned start_cs, start_eip;
	unsigned char *ip = NULL;

	/* Save the starting instruction address. */
	start_cs = vm->regs.cs;
	start_eip = vm->regs.eip;

	/* We'll need to pass I/O through.  PCI devices have higher addresses
	   than we can get access to with ioperm(). */
	if(iopl(3) != 0) {
		return;
	}

	/* Do it. */
	ret = syscall(SYS_vm86old, vm);
	while((vm->regs.cs * 16 + vm->regs.eip) != (start_cs * 16 + stop_eip)) {
		ip = &memory[vm->regs.cs * 16 + vm->regs.eip];
#ifdef DEBUG
		printf("Unexpected return:\n");
		dump_regs(&vm->regs);
		printf("Offending instructions: %02x %02x %02x %02x\n",
		       ip[0], ip[1], ip[2], ip[3]);
#endif
		switch(ip[0]) {
			case 0xe4: { /* in al, literal */
				vm->regs.eax &= 0xffffff00;
				vm->regs.eax |= inb(ip[1]);
				vm->regs.eip += 2;
				break;
			}
			case 0xe6: { /* out al, literal */
				outb(vm->regs.eax & 0xff, ip[1]);
				vm->regs.eip += 2;
				break;
			}
			case 0xec: { /* in al, dx */
				vm->regs.eax &= 0xffffff00;
				vm->regs.eax |= inb(vm->regs.edx & 0xffff);
				vm->regs.eip++;
				break;
			}
			case 0xed: { /* in ax, dx */
				vm->regs.eax &= 0xffff0000;
				vm->regs.eax |= inw(vm->regs.edx & 0xffff);
				vm->regs.eip++;
				break;
			}
			case 0xee: { /* out al, dx */
				outb(vm->regs.eax & 0xff,
				     vm->regs.edx & 0xffff);
				vm->regs.eip++;
				break;
			}
			case 0xef: { /* out ax, dx */
				outw(vm->regs.eax & 0xffff,
				     vm->regs.edx & 0xffff);
				vm->regs.eip++;
				break;
			}
			case 0xfa: { /* cli */
				vm->regs.eflags &= ~(0x0200);
				vm->regs.eip++;
				break;
			}
			case 0xfb: { /* sti */
				vm->regs.eflags |= ~(0x0200);
				vm->regs.eip++;
				break;
			}
			case 0x9c: { /* pushf */
				vm->regs.esp -= 2;
				*(u_int16_t*) &memory[vm->regs.ss * 16 +
						      vm->regs.esp]
						    = vm->regs.eflags & 0xffff;
				vm->regs.eip++;
				break;
			}
			case 0x9d: { /* popf */
				vm->regs.esp += 2;
				vm->regs.eflags &= 0xffff0000;
				vm->regs.eflags |= 
				*(u_int16_t*) &memory[vm->regs.ss * 16 +
						      vm->regs.esp];
				vm->regs.eip++;
				break;
			}
			case 0xf0: { /* lock prefix */
				/* ignore it */
				vm->regs.eip++;
				break;
			}
			case 0x66: {
				/* 32-bit extension prefix.  Valid, even in
				   v86 mode.  Weird. */
				vm->regs.eip++;
				ip++;
				switch(ip[0]) {
					case 0xed: { /* in eax, dx */
						vm->regs.eax =
						inl(vm->regs.edx & 0xffff);
						vm->regs.eip++;
						break;
					}
					case 0xef: { /* out eax, dx */
						outl(vm->regs.eax,
						     vm->regs.edx & 0xffff);
						vm->regs.eip++;
						break;
					}
					default: {
						fprintf(stderr, "unhandled "
							"32-bit opcode\n");
						exit(1);
					}
				}
				break;
			}
			case 0x55: { /* push bp */
				vm->regs.esp -= 2;
				*(u_int16_t*) &memory[vm->regs.ss * 16 +
						      vm->regs.esp]
						    = vm->regs.ebp & 0xffff;
				vm->regs.eip++;
				break;
			}
			case 0x5d: { /* pop bp */
				vm->regs.ebp &= 0xffff0000;
				vm->regs.ebp |= *(u_int16_t*)
					&memory[vm->regs.ss*16 + vm->regs.esp];
				vm->regs.esp += 2;
				vm->regs.eip++;
				break;
			}
			case 0xc3: { /* ret near, just pop ip */
				vm->regs.eip &= 0xffff0000;
				vm->regs.eip |= *(u_int16_t*)
					&memory[vm->regs.ss*16 + vm->regs.esp];
				vm->regs.esp += 2;
				break;
			}
			case 0xcb: { /* ret far, pop both ip and cs */
				vm->regs.eip &= 0xffff0000;
				vm->regs.eip |= *(u_int16_t*)
					&memory[vm->regs.ss*16 + vm->regs.esp];
				vm->regs.esp += 2;
				vm->regs.cs = *(u_int16_t*)
					&memory[vm->regs.ss*16 + vm->regs.esp];
				vm->regs.esp += 2;
				break;
			}
			default: {
				fprintf(stderr, "Unexpected stop!\n");
				dump_regs(&vm->regs);
				printf("Offending instructions: %02x %02x %02x %02x\n",
				       ip[0], ip[1], ip[2], ip[3]);
				exit(1);
			}
		}
		ip = &memory[vm->regs.cs * 16 + vm->regs.eip];
#ifdef DEBUG
		printf("Resuming execution:\n");
		dump_regs(&vm->regs);
		printf("Offending instructions: %02x %02x %02x %02x\n",
		       ip[0], ip[1], ip[2], ip[3]);
#endif
		ret = syscall(SYS_vm86old, vm);
	}
#ifdef DEBUG
	printf("Reached stopping point, returning.\n");
#endif
	return;
}

/* Get a snapshot of the first megabyte of memory for use with vm86. */
unsigned char *vm86_ram_alloc()
{
	unsigned char *memory;
	int fd;

	/* Grab address 0 for this process.  mmap() 1 megabyte + 64k HMA */
	memory = mmap(0, 0x110000, PROT_READ | PROT_EXEC | PROT_WRITE,
		      MAP_PRIVATE | MAP_FIXED | MAP_ANON, -1, 0x00000);
	if(memory == MAP_FAILED) {
		perror("error mmap()ing memory for the BIOS");
		return MAP_FAILED;
	}

	/* Copy the low megabyte to our mmap()'ed buffer. */
	fd = open("/dev/mem", O_RDONLY);
	if(fd == -1) {
		perror("reading kernel memory");
		return MAP_FAILED;
	}
	read(fd, memory, 0x110000);
	close(fd);

	return memory;
}

void vm86_ram_free(unsigned char *ram)
{
	munmap(ram, 0x110000);
}

void bioscall(unsigned char int_no, struct vm86_regs *regs, unsigned char *mem)
{
	unsigned char call[] = {0xcd, int_no, 0xcd, 0x09};
	struct vm86_struct vm;
	memset(&vm, 0, sizeof(vm));
	memcpy(&vm.regs, regs, sizeof(vm.regs));
	vm.regs.cs  = BIOSCALL_START_SEG;
	vm.regs.eip = BIOSCALL_START_OFS;
	vm.flags = VM_MASK | IOPL_MASK;
	memcpy(&mem[BIOSCALL_START_SEG * 16 + BIOSCALL_START_OFS], call,
	       sizeof(call));
	do_vm86(&vm, mem, BIOSCALL_START_OFS + sizeof(call));
	memcpy(regs, &vm.regs, sizeof(vm.regs));
}
