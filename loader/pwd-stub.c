#include <sys/types.h>
#include <errno.h>
#include <pwd.h>
#include <string.h>

static struct passwd pw_root = {
  pw_name: "root",
  pw_passwd: "",
  pw_uid: 0,
  pw_gid: 0,
  pw_gecos: "root",
  pw_dir: "/",
  pw_shell: "/bin/bash"
};

struct passwd *getpwuid(uid_t u)
{
  if (u) return NULL;
  return &pw_root;
}

int __getpwnam_r(const char *name, struct passwd *result_buf, char *buf,
		 size_t buflen, struct passwd **result)
{
  if (strcmp (name, "root")) {
    errno = 0;
    *result = NULL;
    return -1;
  }
  memcpy(result_buf, &pw_root, sizeof(struct passwd));
  *result = result_buf;
  return 0;
}
