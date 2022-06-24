#!/bin/bash

# Scripts in this directory will be executed by cloud-init on the first boot of droplets
# created from your image.  Things ike generating passwords, configuration requiring IP address
# or other items that will be unique to each instance should be done in scripts here.

docker start db
docker start datatracker
