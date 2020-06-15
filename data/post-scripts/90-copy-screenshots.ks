%post --nochroot

echo "Copying screenshots from installation..."

if [ ! -d /tmp/anaconda-screenshots ]; then
    echo "No screenshots found."
    exit 0
fi

mkdir -m 0750 -p $ANA_INSTALL_PATH/root/anaconda-screenshots
cp -a /tmp/anaconda-screenshots/*.png $ANA_INSTALL_PATH/root/anaconda-screenshots/
echo "Screenshots copied successfully."

%end
