%post --nochroot

if [ ! -d /tmp/anaconda-screenshots ]; then
    exit 0
fi

mkdir -m 0750 -p $ANA_INSTALL_PATH/root/anaconda-screenshots
cp -a /tmp/anaconda-screenshots/*.png $ANA_INSTALL_PATH/root/anaconda-screenshots/

%end
