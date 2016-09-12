# Kickstart defaults file for an interative install.
# This is not loaded if a kickstart file is provided on the command line.
auth --enableshadow --passalgo=sha512
firstboot --enable

%anaconda
# Default password policies
pwpolicy root --notstrict --minlen=8 --minquality=50 --nochanges --notempty
pwpolicy user --notstrict --minlen=8 --minquality=50 --nochanges --notempty
pwpolicy luks --notstrict --minlen=8 --minquality=50 --nochanges --notempty
# NOTE: This applies only to *fully* interactive installations, partial kickstart
#       installations use defaults specified in pyanaconda/pwpolicy.py.
#       Automated kickstart installs simply ignore the password policy as the policy
#       only applies to the UI, not for passwords specified in kickstart.
%end
