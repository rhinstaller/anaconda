install
liveimg --url=LIVEIMG_URL --checksum=LIVEIMG_CHECKSUM

network --bootproto=dhcp

bootloader --timeout=1
zerombr

clearpart --all --initlabel
autopart

keyboard us
lang en
timezone America/New_York

rootpw qweqwe

%post
if [[ ! -e /etc/passwd ]]; then
    echo "*** liveimg installation failed ***" > /root/RESULT
fi

# Final check
if [[ ! -e /root/RESULT ]]; then
    echo SUCCESS > /root/RESULT
fi
%end
