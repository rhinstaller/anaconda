/*
  FPSWA Version
    Parse the FPSWA.efi executable to find the version information.
    The output may be used to compare multiple executables to determine
    the newest version.

  Copyright 2002 Intel Corporation
  Copyright 2002 Jenna Hall <jenna.s.hall@intel.com>

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2, or (at your option)
  any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
*/

#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include <bfd.h>
#include <errno.h>
#include <fcntl.h>
#include <malloc.h>

#define SEARCH_STRING		"FileVersion"
#define FILENAME_DESCRIPTOR	"InternalName"
#define FILENAME		"fpswa.efi"
#define MAX_VERSION_LENGTH	8

/* Static declarations  */

static off_t rsrc_offset = 0;	/* rc info offset - found in header */
static size_t rsrc_size = 0;	/* rc info size - found in header */
static int exit_status = 0;
static char *default_target = NULL;	/* default at runtime */

static void
parse_section_header (bfd *, asection *, PTR);

static void
parse_bfd (bfd *);

static void
parse_file (char *, char *);

static void
extract_offset (char **);

static void
parse_unicode(ssize_t, unsigned short *);

static void
locate_file_version (char **);


/* Definitions */

static void
parse_section_header (bfd *abfd, asection *section, PTR ignored ATTRIBUTE_UNUSED)
{
	unsigned int opb = bfd_octets_per_byte(abfd);

	if (!strcmp(bfd_get_section_name(abfd, section), ".rsrc")) {
		rsrc_offset = section->filepos;
		rsrc_size = (bfd_section_size(abfd, section) / opb);
	}
}

static void
parse_bfd (bfd *abfd)
{
	char **matching;

	if (bfd_check_format_matches (abfd, bfd_object, &matching)) {
		bfd_map_over_sections (abfd, parse_section_header, (PTR) NULL);
		return;
	}
	else {
		fprintf(stderr, "Error: not an object file!\n");
		return;
	}
}

static void
parse_file (char *filename, char *target)
{
	bfd *file;

	file = bfd_openr (filename, target);
	if (file == NULL) {
		fprintf(stderr, "BFD library error!\n");
		exit_status = 1;
		return;
	}

	parse_bfd (file);

	bfd_close (file);
}

/*
 * Parse the executable to find the .rsrc header offset
 */
static void
extract_offset (char **argv)
{
	char *target = default_target;

	bfd_init ();

	parse_file (argv[1], target);
}

/*
 * Parse the unicode-encoded rc section of the FPSWA file to find the
 * version string
 */
static void
parse_unicode(ssize_t rc_section_size, unsigned short *buf)
{
	unsigned int i= 0;
	char version_string[MAX_VERSION_LENGTH];
	char *temp_ptr;
	unsigned short *buffer_ptr = buf;

	temp_ptr = SEARCH_STRING;

	/* locate the version search string within the Unicode buffer */
	while (buffer_ptr && (temp_ptr[0] != '\0')) {
		if (*buffer_ptr == temp_ptr[0]) {
			temp_ptr++;
		}
		else		// reset
			temp_ptr = SEARCH_STRING;
		buffer_ptr++;
	}

	/* parse past the Unicode NULL characters */
	while (*buffer_ptr == 0) {
		buffer_ptr++;
	}

	/* capture the version number string */
	while (*buffer_ptr != '\0') {
		version_string[i] = *buffer_ptr;
		buffer_ptr++; i++;
	}
	/* NULL terminate the string */
	version_string[i] = '\0';

	/* output version string to user */
	printf("%s\n", version_string);

}

/*
 * Locate the rc info at that offset in the executable,
 * then parse that section to locate the FileVersion string
 */
static void
locate_file_version (char **argv)
{
	int fd;
	ssize_t bytes_read = 0;
	unsigned short *buf = malloc(rsrc_size);

	if (buf == NULL) {
		fprintf(stderr, "Malloc failed!  Exiting...\n");
		free(buf);
		exit(1);
	}

	if ((fd = open(argv[1], O_RDONLY)) < 0) {
		fprintf(stderr, "Open failed:  %s\n", sys_errlist[errno]);
		free(buf);
		exit(1);
	}

	/* first search to the beginning of the rc info section */
	if (lseek(fd, rsrc_offset, SEEK_SET) < 0) {
		/* seek error; exit */
		fprintf(stderr, "Seek failed:  %s\n", sys_errlist[errno]);
		close(fd);
		free(buf);
		exit(1);
	}

	/* next load the rc info section into the buffer for parsing */
	if ((bytes_read = read(fd, buf, rsrc_size)) < 0) {
		/* read error; exit */
		fprintf(stderr, "Read failed:  %s\n", sys_errlist[errno]);
		close(fd);
		free(buf);
		exit(1);
	}

	/* now parse the rc info section for the FileVersion string */
	parse_unicode(bytes_read, buf);

	free(buf);
	close(fd);
}

int
main (int argc, char **argv)
{
	if (argc != 2) {
		fprintf(stderr, "Usage: %s FPSWA.efi\n", argv[0]);
		exit(1);
	}

	/* parse the executable to find the .rsrc header offset */
	extract_offset(argv);

	/* locate the rc info at that offset in the executable,
	   then parse that section to locate the FileVersion string */
	locate_file_version(argv);

	return exit_status;
}
