/*
 * gptsync/gptsync.c
 * Platform-independent code for syncing GPT and MBR
 *
 * Copyright (c) 2006 Christoph Pfisterer
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the
 *    distribution.
 *
 *  * Neither the name of Christoph Pfisterer nor the names of the
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "gptsync.h"

#include "syslinux_mbr.h"

// types

typedef struct {
    UINT8   flags;
    UINT8   start_chs[3];
    UINT8   type;
    UINT8   end_chs[3];
    UINT32  start_lba;
    UINT32  size;
} MBR_PARTITION_INFO;

typedef struct {
    UINT8   type;
    CHARN   *name;
} MBR_PARTTYPE;

typedef struct {
    UINT64  signature;
    UINT32  spec_revision;
    UINT32  header_size;
    UINT32  header_crc32;
    UINT32  reserved;
    UINT64  header_lba;
    UINT64  alternate_header_lba;
    UINT64  first_usable_lba;
    UINT64  last_usable_lba;
    UINT8   disk_guid[16];
    UINT64  entry_lba;
    UINT32  entry_count;
    UINT32  entry_size;
    UINT32  entry_crc32;
} GPT_HEADER;

typedef struct {
    UINT8   type_guid[16];
    UINT8   partition_guid[16];
    UINT64  start_lba;
    UINT64  end_lba;
    UINT64  attributes;
    CHAR16  name[36];
} GPT_ENTRY;

#define GPT_KIND_SYSTEM     (0)
#define GPT_KIND_DATA       (1)
#define GPT_KIND_BASIC_DATA (2)
#define GPT_KIND_FATAL      (3)

typedef struct {
    UINT8   guid[16];
    UINT8   mbr_type;
    CHARN   *name;
    UINTN   kind;
} GPT_PARTTYPE;

typedef struct {
    UINTN   index;
    UINT64  start_lba;
    UINT64  end_lba;
    UINTN   mbr_type;
    UINT8   gpt_type[16];
    GPT_PARTTYPE *gpt_parttype;
    BOOLEAN active;
} PARTITION_INFO;

// variables

UINT8           empty_guid[16] = { 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 };

PARTITION_INFO  mbr_parts[4];
UINTN           mbr_part_count = 0;
PARTITION_INFO  gpt_parts[128];
UINTN           gpt_part_count = 0;

PARTITION_INFO  new_mbr_parts[4];
UINTN           new_mbr_part_count = 0;

UINT8           sector[512];

MBR_PARTTYPE    mbr_types[] = {
    { 0x01, STR("FAT12") },
    { 0x04, STR("FAT16 <32M") },
    { 0x05, STR("DOS Extended") },
    { 0x06, STR("FAT16") },
    { 0x07, STR("NTFS") },
    { 0x0b, STR("FAT32") },
    { 0x0c, STR("FAT32 (LBA)") },
    { 0x0e, STR("FAT16 (LBA)") },
    { 0x0f, STR("Win95 Extended (LBA)") },
    { 0x11, STR("Hidden FAT12") },
    { 0x14, STR("Hidden FAT16 <32M") },
    { 0x16, STR("Hidden FAT16") },
    { 0x17, STR("Hidden NTFS") },
    { 0x1b, STR("Hidden FAT32") },
    { 0x1c, STR("Hidden FAT32 (LBA)") },
    { 0x1e, STR("Hidden FAT16 (LBA)") },
    { 0x82, STR("Linux swap / Solaris") },
    { 0x83, STR("Linux") },
    { 0x85, STR("Linux Extended") },
    { 0x86, STR("NTFS volume set") },
    { 0x87, STR("NTFS volume set") },
    { 0x8e, STR("Linux LVM") },
    { 0xa5, STR("FreeBSD") },
    { 0xa6, STR("OpenBSD") },
    { 0xa7, STR("NeXTSTEP") },
    { 0xa9, STR("NetBSD") },
    { 0xaf, STR("Mac OS X HFS+") },
    { 0xeb, STR("BeOS") },
    { 0xee, STR("EFI Protective") },
    { 0xef, STR("EFI System (FAT)") },
    { 0xfd, STR("Linux RAID") },
    { 0, NULL },
};

GPT_PARTTYPE    gpt_types[] = {
    { "\x28\x73\x2A\xC1\x1F\xF8\xD2\x11\xBA\x4B\x00\xA0\xC9\x3E\xC9\x3B", 0xef, STR("EFI System (FAT)"), GPT_KIND_SYSTEM },
    { "\x41\xEE\x4D\x02\xE7\x33\xD3\x11\x9D\x69\x00\x08\xC7\x81\xF3\x9F", 0x00, STR("MBR partition scheme"), GPT_KIND_FATAL },
    { "\x16\xE3\xC9\xE3\x5C\x0B\xB8\x4D\x81\x7D\xF9\x2D\xF0\x02\x15\xAE", 0x00, STR("MS Reserved"), GPT_KIND_SYSTEM },
    { "\xA2\xA0\xD0\xEB\xE5\xB9\x33\x44\x87\xC0\x68\xB6\xB7\x26\x99\xC7", 0x00, STR("Basic Data"), GPT_KIND_BASIC_DATA },
    { "\xAA\xC8\x08\x58\x8F\x7E\xE0\x42\x85\xD2\xE1\xE9\x04\x34\xCF\xB3", 0x00, STR("MS LDM Metadata"), GPT_KIND_FATAL },
    { "\xA0\x60\x9B\xAF\x31\x14\x62\x4F\xBC\x68\x33\x11\x71\x4A\x69\xAD", 0x00, STR("MS LDM Data"), GPT_KIND_FATAL },
    { "\x0F\x88\x9D\xA1\xFC\x05\x3B\x4D\xA0\x06\x74\x3F\x0F\x84\x91\x1E", 0xfd, STR("Linux RAID"), GPT_KIND_DATA },
    { "\x6D\xFD\x57\x06\xAB\xA4\xC4\x43\x84\xE5\x09\x33\xC8\x4B\x4F\x4F", 0x82, STR("Linux Swap"), GPT_KIND_DATA },
    { "\x79\xD3\xD6\xE6\x07\xF5\xC2\x44\xA2\x3C\x23\x8F\x2A\x3D\xF9\x28", 0x8e, STR("Linux LVM"), GPT_KIND_DATA },
    { "\x39\x33\xA6\x8D\x07\x00\xC0\x60\xC4\x36\x08\x3A\xC8\x23\x09\x08", 0x00, STR("Linux Reserved"), GPT_KIND_SYSTEM },
    { "\x00\x53\x46\x48\x00\x00\xAA\x11\xAA\x11\x00\x30\x65\x43\xEC\xAC", 0xaf, STR("Mac OS X HFS+"), GPT_KIND_DATA },
    { { 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 }, 0, NULL, 0 },
};
GPT_PARTTYPE    gpt_dummy_type =
    { { 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 }, 0, STR("Unknown"), GPT_KIND_FATAL };

//
// MBR functions
//

static CHARN * mbr_parttype_name(UINT8 type)
{
    int i;
    
    for (i = 0; mbr_types[i].name; i++)
        if (mbr_types[i].type == type)
            return mbr_types[i].name;
    return STR("Unknown");
}

static UINTN read_mbr(VOID)
{
    UINTN               status;
    UINTN               i;
    BOOLEAN             used;
    MBR_PARTITION_INFO  *table;
    
    Print(L"\nCurrent MBR partition table:\n");
    
    // read MBR data
    status = read_sector(0, sector);
    if (status != 0)
        return status;
    
    // check for validity
    if (*((UINT16 *)(sector + 510)) != 0xaa55) {
        Print(L" No MBR partition table present!\n");
        return 1;
    }
    table = (MBR_PARTITION_INFO *)(sector + 446);
    for (i = 0; i < 4; i++) {
        if (table[i].flags != 0x00 && table[i].flags != 0x80) {
            Print(L" MBR partition table is invalid!\n");
            return 1;
        }
    }
    
    // check if used
    used = FALSE;
    for (i = 0; i < 4; i++) {
        if (table[i].start_lba > 0 && table[i].size > 0) {
            used = TRUE;
            break;
        }
    }
    if (!used) {
        Print(L" No partitions defined\n");
        return 0;
    }
    
    // dump current state & fill internal structures
    Print(L" # A    Start LBA      End LBA  Type\n");
    for (i = 0; i < 4; i++) {
        if (table[i].start_lba == 0 || table[i].size == 0)
            continue;
        
        mbr_parts[mbr_part_count].index     = i;
        mbr_parts[mbr_part_count].start_lba = (UINT64)table[i].start_lba;
        mbr_parts[mbr_part_count].end_lba   = (UINT64)table[i].start_lba + (UINT64)table[i].size - 1;
        mbr_parts[mbr_part_count].mbr_type  = table[i].type;
        mbr_parts[mbr_part_count].active    = (table[i].flags == 0x80) ? TRUE : FALSE;
        
        Print(L" %d %s %12lld %12lld  %02x  %s\n",
              mbr_parts[mbr_part_count].index + 1,
              mbr_parts[mbr_part_count].active ? STR("*") : STR(" "),
              mbr_parts[mbr_part_count].start_lba,
              mbr_parts[mbr_part_count].end_lba,
              mbr_parts[mbr_part_count].mbr_type,
              mbr_parttype_name(mbr_parts[mbr_part_count].mbr_type));
        
        mbr_part_count++;
    }
    
    return 0;
}

static UINTN check_mbr(VOID)
{
    UINTN       i, k;
    
    // check each entry
    for (i = 0; i < mbr_part_count; i++) {
        // check for overlap
        for (k = 0; k < mbr_part_count; k++) {
            if (k != i && !(mbr_parts[i].start_lba > mbr_parts[k].end_lba || mbr_parts[k].start_lba > mbr_parts[i].end_lba)) {
                Print(L"Status: MBR partition table is invalid, partitions overlap.\n");
                return 1;
            }
        }
        
        // check for extended partitions
        if (mbr_parts[i].mbr_type == 0x05 || mbr_parts[i].mbr_type == 0x0f || mbr_parts[i].mbr_type == 0x85) {
            Print(L"Status: Extended partition found in MBR table, will not touch this disk.\n",
                  gpt_parts[i].gpt_parttype->name);
            return 1;
        }
    }
    
    return 0;
}

static UINTN write_mbr(VOID)
{
    UINTN               status;
    UINTN               i, k;
    UINT8               active;
    UINT64              lba;
    MBR_PARTITION_INFO  *table;
    BOOLEAN             have_bootcode;
    
    Print(L"\nWriting new MBR...\n");
    
    // read MBR data
    status = read_sector(0, sector);
    if (status != 0)
        return status;
    
    // write partition table
    *((UINT16 *)(sector + 510)) = 0xaa55;
    
    table = (MBR_PARTITION_INFO *)(sector + 446);
    active = 0x80;
    for (i = 0; i < 4; i++) {
        for (k = 0; k < new_mbr_part_count; k++) {
            if (new_mbr_parts[k].index == i)
                break;
        }
        if (k >= new_mbr_part_count) {
            // unused entry
            table[i].flags        = 0;
            table[i].start_chs[0] = 0;
            table[i].start_chs[1] = 0;
            table[i].start_chs[2] = 0;
            table[i].type         = 0;
            table[i].end_chs[0]   = 0;
            table[i].end_chs[1]   = 0;
            table[i].end_chs[2]   = 0;
            table[i].start_lba    = 0;
            table[i].size         = 0;
        } else {
            if (new_mbr_parts[k].active) {
                table[i].flags        = active;
                active = 0x00;
            } else
                table[i].flags        = 0x00;
            table[i].start_chs[0] = 0xfe;
            table[i].start_chs[1] = 0xff;
            table[i].start_chs[2] = 0xff;
            table[i].type         = new_mbr_parts[k].mbr_type;
            table[i].end_chs[0]   = 0xfe;
            table[i].end_chs[1]   = 0xff;
            table[i].end_chs[2]   = 0xff;
            
            lba = new_mbr_parts[k].start_lba;
            if (lba > 0xffffffffULL) {
                Print(L"Warning: Partition %d starts beyond 2 TiB limit\n", i+1);
                lba = 0xffffffffULL;
            }
            table[i].start_lba    = (UINT32)lba;
            
            lba = new_mbr_parts[k].end_lba + 1 - new_mbr_parts[k].start_lba;
            if (lba > 0xffffffffULL) {
                Print(L"Warning: Partition %d extends beyond 2 TiB limit\n", i+1);
                lba = 0xffffffffULL;
            }
            table[i].size         = (UINT32)lba;
        }
    }
    
    // add boot code if necessary
    have_bootcode = FALSE;
    for (i = 0; i < MBR_BOOTCODE_SIZE; i++) {
        if (sector[i] != 0) {
            have_bootcode = TRUE;
            break;
        }
    }
    if (!have_bootcode) {
        // no boot code found in the MBR, add the syslinux MBR code
        SetMem(sector, MBR_BOOTCODE_SIZE, 0);
        CopyMem(sector, syslinux_mbr, SYSLINUX_MBR_SIZE);
    }
    
    // write MBR data
    status = write_sector(0, sector);
    if (status != 0)
        return status;
    
    Print(L"MBR updated successfully!\n");
    
    return 0;
}

//
// GPT functions
//

static GPT_PARTTYPE * gpt_parttype(UINT8 *type_guid)
{
    int i;
    
    for (i = 0; gpt_types[i].name; i++)
        if (guids_are_equal(gpt_types[i].guid, type_guid))
            return &(gpt_types[i]);
    return &gpt_dummy_type;
}

static UINTN read_gpt(VOID)
{
    UINTN       status;
    GPT_HEADER  *header;
    GPT_ENTRY   *entry;
    UINT64      entry_lba;
    UINTN       entry_count, entry_size, i;
    
    Print(L"\nCurrent GPT partition table:\n");
    
    // read GPT header
    status = read_sector(1, sector);
    if (status != 0)
        return status;
    
    // check signature
    header = (GPT_HEADER *)sector;
    if (header->signature != 0x5452415020494645ULL) {
        Print(L" No GPT partition table present!\n");
        return 0;
    }
    if (header->spec_revision != 0x00010000UL) {
        Print(L" Warning: Unknown GPT spec revision 0x%08x\n", header->spec_revision);
    }
    if ((512 % header->entry_size) > 0 || header->entry_size > 512) {
        Print(L" Error: Invalid GPT entry size (misaligned or more than 512 bytes)\n");
        return 0;
    }
    
    // read entries
    entry_lba   = header->entry_lba;
    entry_size  = header->entry_size;
    entry_count = header->entry_count;
    
    Print(L" #      Start LBA      End LBA  Type\n");
    for (i = 0; i < entry_count; i++) {
        if (((i * entry_size) % 512) == 0) {
            status = read_sector(entry_lba, sector);
            if (status != 0)
                return status;
            entry_lba++;
        }
        entry = (GPT_ENTRY *)(sector + ((i * entry_size) % 512));
        
        if (guids_are_equal(entry->type_guid, empty_guid))
            continue;
        
        gpt_parts[gpt_part_count].index     = i;
        gpt_parts[gpt_part_count].start_lba = entry->start_lba;
        gpt_parts[gpt_part_count].end_lba   = entry->end_lba;
        gpt_parts[gpt_part_count].mbr_type  = 0;
        copy_guid(gpt_parts[gpt_part_count].gpt_type, entry->type_guid);
        gpt_parts[gpt_part_count].gpt_parttype = gpt_parttype(gpt_parts[gpt_part_count].gpt_type);
        gpt_parts[gpt_part_count].active    = FALSE;
        
        Print(L" %d   %12lld %12lld  %s\n",
              gpt_parts[gpt_part_count].index + 1,
              gpt_parts[gpt_part_count].start_lba,
              gpt_parts[gpt_part_count].end_lba,
              gpt_parts[gpt_part_count].gpt_parttype->name);
        
        gpt_part_count++;
    }
    
    return 0;
}

static UINTN check_gpt(VOID)
{
    UINTN       i, k;
    BOOLEAN     found_data_parts;
    
    if (gpt_part_count == 0) {
        Print(L"Status: No GPT partition table, no need to sync.\n");
        return 1;
    }
    
    // check each entry
    found_data_parts = FALSE;
    for (i = 0; i < gpt_part_count; i++) {
        // check sanity
        if (gpt_parts[i].end_lba < gpt_parts[i].start_lba) {
            Print(L"Status: GPT partition table is invalid.\n");
            return 1;
        }
        // check for overlap
        for (k = 0; k < gpt_part_count; k++) {
            if (k != i && !(gpt_parts[i].start_lba > gpt_parts[k].end_lba || gpt_parts[k].start_lba > gpt_parts[i].end_lba)) {
                Print(L"Status: GPT partition table is invalid, partitions overlap.\n");
                return 1;
            }
        }
        
        // check for partitions kind
        if (gpt_parts[i].gpt_parttype->kind == GPT_KIND_FATAL) {
            Print(L"Status: GPT partition of type '%s' found, will not touch this disk.\n",
                  gpt_parts[i].gpt_parttype->name);
            return 1;
        }
        if (gpt_parts[i].gpt_parttype->kind == GPT_KIND_DATA ||
            gpt_parts[i].gpt_parttype->kind == GPT_KIND_BASIC_DATA)
            found_data_parts = TRUE;
    }
    
    if (!found_data_parts) {
        Print(L"Status: GPT partition table has no data partitions, no need to sync.\n");
        return 1;
    }
    
    return 0;
}

//
// compare GPT and MBR tables
//

#define ACTION_NONE        (0)
#define ACTION_NOP         (1)
#define ACTION_REWRITE     (2)

static UINTN analyze(VOID)
{
    UINTN   action = ACTION_NONE;
    UINTN   i, k, iter;
    UINT64  min_start_lba;
    BOOLEAN have_active;
    
    new_mbr_part_count = 0;
    
    // check for common scenarios
    if (mbr_part_count == 0) {
        // current MBR is empty
        action = ACTION_REWRITE;
    } else if (mbr_part_count == 1 && mbr_parts[0].mbr_type == 0xee) {
        // MBR has just the EFI Protective partition (i.e. untouched)
        action = ACTION_REWRITE;
    }
    if (action == ACTION_NONE && mbr_part_count > 0) {
        if (mbr_parts[0].mbr_type == 0xee &&
            gpt_parts[0].gpt_parttype->mbr_type == 0xef &&
            mbr_parts[0].start_lba == 1 &&
            mbr_parts[0].end_lba == gpt_parts[0].end_lba) {
            // The Apple Way, "EFI Protective" covering the tables and the ESP
            action = ACTION_NOP;
            if ((mbr_part_count != gpt_part_count && gpt_part_count <= 4) ||
                (mbr_part_count != 4              && gpt_part_count > 4)) {
                // number of partitions has changed
                action = ACTION_REWRITE;
            } else {
                // check partition ranges and types
                for (i = 1; i < mbr_part_count; i++) {
                    if (mbr_parts[i].start_lba != gpt_parts[i].start_lba ||
                        mbr_parts[i].end_lba   != gpt_parts[i].end_lba ||
                        (gpt_parts[i].gpt_parttype->mbr_type && mbr_parts[i].mbr_type != gpt_parts[i].gpt_parttype->mbr_type))
                        // position or type has changed
                        action = ACTION_REWRITE;
                }
            }
        }
    }
    if (action == ACTION_NONE && mbr_part_count > 0 && mbr_parts[0].mbr_type == 0xef) {
        // The XOM Way, all partitions mirrored 1:1
        action = ACTION_REWRITE;
        // check partition ranges and types
        for (i = 0; i < mbr_part_count; i++) {
            if (mbr_parts[i].start_lba != gpt_parts[i].start_lba ||
                mbr_parts[i].end_lba   != gpt_parts[i].end_lba ||
                (gpt_parts[i].gpt_parttype->mbr_type && mbr_parts[i].mbr_type != gpt_parts[i].gpt_parttype->mbr_type))
                // position or type has changed -> better don't touch
                action = ACTION_NONE;
        }
    }
    
    if (action == ACTION_NOP) {
        Print(L"Status: Tables are synchronized, no need to sync.\n");
        return 0;
    } else if (action == ACTION_REWRITE) {
        Print(L"Status: MBR table must be updated.\n");
    } else {
        Print(L"Status: Analysis inconclusive, will not touch this disk.\n");
        return 1;
    }
    
    // generate the new table
    
    // first entry: EFI Protective
    new_mbr_parts[0].index     = 0;
    new_mbr_parts[0].start_lba = 1;
    new_mbr_parts[0].mbr_type  = 0xee;
    new_mbr_part_count = 1;
    
    if (gpt_parts[0].gpt_parttype->mbr_type == 0xef) {
        new_mbr_parts[0].end_lba = gpt_parts[0].end_lba;
        i = 1;
    } else {
        min_start_lba = gpt_parts[0].start_lba;
        for (k = 0; k < gpt_part_count; k++) {
            if (min_start_lba > gpt_parts[k].start_lba)
                min_start_lba = gpt_parts[k].start_lba;
        }
        new_mbr_parts[0].end_lba = min_start_lba - 1;
        i = 0;
    }
    
    // add other GPT partitions until the table is full
    for (; i < gpt_part_count && new_mbr_part_count < 4; i++) {
        new_mbr_parts[new_mbr_part_count].index     = new_mbr_part_count;
        new_mbr_parts[new_mbr_part_count].start_lba = gpt_parts[i].start_lba;
        new_mbr_parts[new_mbr_part_count].end_lba   = gpt_parts[i].end_lba;
        new_mbr_parts[new_mbr_part_count].mbr_type  = gpt_parts[i].gpt_parttype->mbr_type;
        new_mbr_parts[new_mbr_part_count].active    = FALSE;
        
        // find matching partition in the old MBR table
        for (k = 0; k < mbr_part_count; k++) {
            if (mbr_parts[k].start_lba == gpt_parts[i].start_lba) {
                if (new_mbr_parts[new_mbr_part_count].mbr_type == 0)
                    new_mbr_parts[new_mbr_part_count].mbr_type = mbr_parts[k].mbr_type;
                new_mbr_parts[new_mbr_part_count].active = mbr_parts[k].active;
                break;
            }
        }
        
        if (new_mbr_parts[new_mbr_part_count].mbr_type == 0) {
            // TODO: detect the actual file system on the partition
            
            // fallback: use linux native
            //if (gpt_parts[i].gpt_parttype->kind == GPT_KIND_BASIC_DATA) {
            new_mbr_parts[new_mbr_part_count].mbr_type = 0x83;
        }
        
        new_mbr_part_count++;
    }
    
    // if no partition is active, pick one
    for (iter = 0; iter < 3; iter++) {
        // check
        have_active = FALSE;
        for (i = 0; i < new_mbr_part_count; i++)
            if (new_mbr_parts[i].active)
                have_active = TRUE;
        if (have_active)
            break;
        
        // set active on the first matching partition
        for (i = 0; i < new_mbr_part_count; i++) {
            if ((iter >= 0 && (new_mbr_parts[i].mbr_type == 0x07 ||
                               new_mbr_parts[i].mbr_type == 0x0b ||
                               new_mbr_parts[i].mbr_type == 0x0c)) ||
                (iter >= 1 && (new_mbr_parts[i].mbr_type == 0x83)) ||
                (iter >= 2 && i > 0)) {
                new_mbr_parts[i].active = TRUE;
                break;
            }
        }
    }
    
    // dump table
    Print(L"\nProposed new MBR partition table:\n");
    Print(L" # A    Start LBA      End LBA  Type\n");
    for (i = 0; i < new_mbr_part_count; i++) {
        Print(L" %d %s %12lld %12lld  %02x  %s\n",
              new_mbr_parts[i].index + 1,
              new_mbr_parts[i].active ? STR("*") : STR(" "),
              new_mbr_parts[i].start_lba,
              new_mbr_parts[i].end_lba,
              new_mbr_parts[i].mbr_type,
              mbr_parttype_name(new_mbr_parts[i].mbr_type));
    }
    
    return 0;
}

//
// sync algorithm entry point
//

UINTN gptsync(VOID)
{
    UINTN   status = 0;
    UINTN   status_gpt, status_mbr;
    //    BOOLEAN proceed = FALSE;
    
    // get full information from disk
    status_gpt = read_gpt();
    status_mbr = read_mbr();
    if (status_gpt != 0 || status_mbr != 0)
        return (status_gpt || status_mbr);
    
    // cross-check current situation
    Print(L"\n");
    status = check_gpt();   // check GPT for consistency
    if (status != 0)
        return status;
    status = check_mbr();   // check MBR for consistency
    if (status != 0)
        return status;
    status = analyze();     // analyze the situation
    if (status != 0)
        return status;
    if (new_mbr_part_count == 0)
        return status;
    
    // offer user the choice what to do
    //    status = input_boolean(STR("\nMay I update the MBR as printed above? [y/N] "), &proceed);
    //    if (status != 0 || proceed != TRUE)
    //        return status;
    
    // adjust the MBR and write it back
    status = write_mbr();
    if (status != 0)
        return status;
    
    return status;
}
