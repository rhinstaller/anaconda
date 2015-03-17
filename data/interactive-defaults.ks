# Kickstart defaults file for an interative install.
# This is not loaded if a kickstart file is provided on the command line.
auth --enableshadow --passalgo=sha512
firstboot --enable

%anaconda
# Default password policies
pwpolicy root --strict --minlen=8 --minquality=50 --nochanges --emptyok
pwpolicy user --strict --minlen=8 --minquality=50 --nochanges --emptyok
pwpolicy luks --strict --minlen=8 --minquality=50 --nochanges --emptyok
%end
