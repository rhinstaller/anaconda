url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"
install
network --bootproto=dhcp
# Set hostname for testing
network --hostname=testhostname.example.com

bootloader --timeout=1
zerombr
clearpart --all
autopart

keyboard cz
lang cz
timezone Europe/Prague
rootpw qweqwe

%packages
openssh-server
%end

%post
NEWSSH="Port 22001"
SSHPACKAGE="openssh-server"

## Check if the openssh-server package is installed.
RESULT=`dnf list installed | grep -Eo 'openssh-server'`

if [[ "$RESULT" != "$SSHPACKAGE" ]]; then
	echo "$SSHPACKAGE installation failed" >> /root/RESULT
fi

## Perform sshd_config file check, if it exists..
ls /etc/ssh/sshd_config
if [[ $? != 0 ]]; then
	echo "SSHD_CONFIG file does not exist" >> /root/RESULT
fi

## ...if so, perform appendation to the file...
if [[ "$RESULT" == "$SSHPACKAGE" ]]; then
	echo "$NEWSSH" >> /etc/ssh/sshd_config
fi

## ...and perform appended data check.
RESULTAPPEND=`cat /etc/ssh/sshd_config | grep Port`
if [[ $? != 0 ]]; then
	echo "$NEWSSH check failed" >> /root/RESULT
fi

## If nothing fails, append success statement.
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
