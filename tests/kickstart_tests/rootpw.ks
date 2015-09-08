url --mirror=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-rawhide&arch=$basearch

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

# Something ought to pull in python for %post, but ask for it just in case
%packages
python3
%end

%post --interpreter=/usr/bin/python3
import sys
import crypt

with open("/root/RESULT", "w") as result:
    # Test that the root password is what we expect it to be
    with open("/etc/shadow", "r") as f:
        for line in f:
            if line.startswith("root:"):
                shadow_fields = line.strip().split(":")
                break
        else:
            print("Unable to find root password", file=result)
            sys.exit(0)

    if crypt.crypt("qweqwe", shadow_fields[1]) != shadow_fields[1]:
        print("Root password is not correct: %s" % shadow_fields[1], file=result)
        sys.exit(0)

    if shadow_fields[2] != "":
        print("Date of last password change is not empty: %s" % shadow_fields[2], file=result)
        sys.exit(0)

    print("SUCCESS", file=result)
%end
