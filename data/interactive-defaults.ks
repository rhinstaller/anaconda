# Kickstart defaults file for an interative install.
# This is not loaded if a kickstart file is provided on the command line.
auth --enableshadow --passalgo=sha512
firstboot --enable

%anaconda
# Default password policies
pwpolicy root --notstrict --minlen=0 --minquality=1 --nochanges --emptyok
pwpolicy user --notstrict --minlen=0 --minquality=1 --nochanges --emptyok
pwpolicy luks --notstrict --minlen=0 --minquality=1 --nochanges --emptyok
%end
