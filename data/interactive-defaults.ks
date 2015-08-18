# Kickstart defaults file for an interative install.
# This is not loaded if a kickstart file is provided on the command line.
auth --enableshadow --passalgo=sha512
firstboot --enable

%anaconda
# Default password policies
pwpolicy root --strict --nochanges --emptyok
pwpolicy user --strict --nochanges --emptyok
pwpolicy luks --strict --nochanges --emptyok
%end
