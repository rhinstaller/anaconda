#ifndef bioscall_h
#define bioscall_h

/* Print some of the interesting parts of a vm86_regs structure. */
void dump_regs(struct vm86_regs *regs);

/* Call vm86 using the given memory block, stopping if we break at a
   given address. */
void do_vm86(struct vm86_struct *vm, char *memory, unsigned stop_eip);

/* Memory-map a megabyte at address 0, and copy the kernel's low megabyte
   into the memory block, returning the result. */
unsigned char *vm86_ram_alloc();
void vm86_ram_free(unsigned char *ram);

/* Handle everything, using the memory mapped at address 0.  The code that makes
   the actual code to the bios is stored at segment BIOSCALL_START_SEG, offset
   BIOSCALL_START_OFS, so expect that area to be destroyed if you use it. */
#define BIOSCALL_START_SEG 0x8000
#define BIOSCALL_START_OFS 0x0000
void bioscall(unsigned char int_no, struct vm86_regs *regs, unsigned char *mem);

#endif /* bioscall_h */
