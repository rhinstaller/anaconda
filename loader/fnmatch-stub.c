#include <stdio.h>
#include <string.h>
#include <fnmatch.h>

/* A very simplified fnmatch which just supports one
   * in the string and no [, ? or { */
int fnmatch(const char *pattern, const char *string, int flags)
{
  const char *p, *q, *r;

  if (flags == (FNM_PATHNAME | FNM_PERIOD)
      && strpbrk (pattern, "[?{") == NULL
      && (p = strchr (pattern, '*')) != NULL
      && strchr (p + 1, '*') == NULL)
    {
      if (strncmp (string, pattern, p - pattern))
	return FNM_NOMATCH;
      q = strstr (string + (p - pattern), p + 1);
      r = strchr (string + (p - pattern), '/');
      if (q == NULL || strlen (q) != strlen (p + 1)
	  || (r != NULL && r < q))
	return FNM_NOMATCH;
      return 0;
    }
  fprintf (stderr, "fnmatch stub does not support '%s' patterns\n", pattern);
  exit (1);
}
