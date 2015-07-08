url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/"

install

network --bootproto=dhcp

bootloader --timeout=1
zerombr

clearpart --all --initlabel
autopart

keyboard us
lang en
timezone America/New_York

rootpw qweqwe

## TEST CREATE USER
# Create specific user group
group --name=kosygroup --gid=5001

# Create specific user
user --name=kosieh --gecos="Kosieh Barter" --homedir=/home/kbarter --password="$6$QsJCB9E6geIjWNvn$UZLEtnHYgKmFgrPo0fY1qNBc/aRi9b01f19w9mpdFm9.MPblckUuFYvpRLSzeYeR/6lO/2uY4WtjhbryC0k2L/" --iscrypted --shell=/bin/bash --uid=4001 --gid=5001

shutdown

%packages
%end

%post

## TEST CREATE USER CHECK
# Check group
cat /etc/group | grep 5001
if [[ $? -ne 0 ]]; then
    echo "*** Group failed to create." >> /root/RESULT
fi

# Check group name
cat /etc/group | grep kosygroup
if [[ $? -ne 0 ]]; then
    echo "*** Group name not present." >> /root/RESULT
fi

# Check find username
cat /etc/passwd | grep kosieh
if [[ $? -ne 0 ]]; then
    echo "*** User is not present in system." >> /root/RESULT
fi

# Check GEDOS: real name
cat /etc/passwd | grep kosieh | grep "Kosieh Barter"
if [[ $? -ne 0 ]]; then
    echo "*** User is present, but not all details: REAL NAME (GEDOS)" >> /root/RESULT
fi

# Check if the user has his/her bash
cat /etc/passwd | grep kosieh | grep "/bin/bash"
if [[ $? -ne 0 ]]; then
    echo "*** User is present, but /bin/bash is not set" >> /root/RESULT
fi

# Check if the user has encrypted password
cat /etc/shadow | grep kosieh | grep "$6$QsJCB9E6geIjWNvn$UZLEtnHYgKmFgrPo0fY1qNBc/aRi9b01f19w9mpdFm9.MPblckUuFYvpRLSzeYeR/6lO/2uY4WtjhbryC0k2L/"
if [[ $? -ne 0 ]]; then
    echo "*** User is present, passwords DO NOT match" >> /root/RESULT
fi

# Check if the user is in correct group
cat /etc/passwd | grep kosieh |  grep 5001
if [[ $? -ne 0 ]]; then
    echo "*** User is present, group assignment" >> /root/RESULT
fi

# Check if the user has PHYSICAL home dir
ls /home/ | grep kbarter
if [[ $? -ne 0 ]]; then
    echo "*** Home directory not found" >> /root/RESULT
fi

# Check for home dir in /etc/passwd
cat /etc/passwd | grep kosieh | grep /home/kbarter
if [[ $? -ne 0 ]]; then
    echo "*** Home directory not in passwd file" >> /root/RESULT
fi

# Final check
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
