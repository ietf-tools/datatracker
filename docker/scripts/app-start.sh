#!/bin/bash

sudo service rsyslog start &>/dev/null

# Run nginx

echo "Starting nginx..."
pidof nginx >/dev/null && echo "nginx is already running [ OK ]" || sudo nginx

# Run memcached

echo "Starting memcached..."
pidof memcached >/dev/null && echo "memcached is already running [ OK ]" || /usr/bin/memcached -u dev -d

echo "-----------------------------------------------------------------"
echo "Ready!"
echo "-----------------------------------------------------------------"
