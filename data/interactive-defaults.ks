# Kickstart defaults file for an interative install.
# This is not loaded if a kickstart file is provided on the command line.
auth --enableshadow --passalgo=sha512
firstboot --enable

# Default password policies
pwpolicy root --strict --minlen=8 --minquality=50 --changesok --notempty
pwpolicy user --strict --minlen=8 --minquality=50 --changesok --emptyok
pwpolicy luks --strict --minlen=10
