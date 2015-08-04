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

shutdown

%pre-install
# TEST setting up /etc/passwd before package installation
mkdir $ANA_INSTALL_PATH/etc
cat > $ANA_INSTALL_PATH/etc/passwd << EOF
root:x:0:0:root:/root:/bin/bash
bin:x:1:1:bin:/bin:/sbin/nologin
daemon:x:2:2:daemon:/sbin:/sbin/nologin
adm:x:3:4:adm:/var/adm:/sbin/nologin
lp:x:4:7:lp:/var/spool/lpd:/sbin/nologin
sync:x:5:0:sync:/sbin:/bin/sync
shutdown:x:6:0:shutdown:/sbin:/sbin/shutdown
halt:x:7:0:halt:/sbin:/sbin/halt
mail:x:8:12:mail:/var/spool/mail:/sbin/nologin
operator:x:11:0:operator:/root:/sbin/nologin
games:x:12:100:games:/usr/games:/sbin/nologin
ftp:x:14:50:FTP User:/var/ftp:/sbin/nologin
nobody:x:99:99:Nobody:/:/sbin/nologin
polipo:x:600:600:Polipo Web Proxy:/var/cache/polipo:/sbin/nologin
lighttpd:x:601:601:lighttpd web server:/var/www/lighttpd:/sbin/nologin
EOF
%end

%packages
polipo
lighttpd
%end

%post
## TEST pre-install
grep "polipo:x:600:600" /etc/passwd
if [[ $? -ne 0 ]]; then
    echo "*** pre-install failed, wrong polipo entry ***" >> /root/RESULT
fi

grep "lighttpd:x:601:601" /etc/passwd
if [[ $? -ne 0 ]]; then
    echo "*** pre-install failed, wrong lighttpd entry ***" >> /root/RESULT
fi

# Final check
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
