#!/bin/bash

HOSTARCH=$(arch)
if [ $HOSTARCH == "x86_64" ]; then
    echo "Installing chrome driver..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
    apt-get update -y
    apt-get install -y google-chrome-stable
    CHROMEVER=$(google-chrome --product-version | grep -o "[^\.]*\.[^\.]*\.[^\.]*")
    DRIVERVER=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMEVER")
    wget -q --continue -P /chromedriver "http://chromedriver.storage.googleapis.com/$DRIVERVER/chromedriver_linux64.zip"
    unzip /chromedriver/chromedriver* -d /chromedriver
    ln -s /chromedriver/chromedriver /usr/local/bin/chromedriver
    ln -s /chromedriver/chromedriver /usr/bin/chromedriver
else
    echo "This architecture doesn't support chromedriver. Skipping installation..."
fi