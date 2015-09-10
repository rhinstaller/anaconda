# Default settings that work for everyone, but may not be optimal.

# Where's the package repo for tests that don't care about testing the package
# source.  This may be slow (especially for large numbers of tests) and you may
# want to define your own.
export KSTEST_URL='--mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-rawhide\\&arch=$basearch'
