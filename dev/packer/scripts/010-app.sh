#!/bin/bash

# INSTALL DOCKER

sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# CLONE GIT REPO

mkdir -p /workspace
git clone https://github.com/ietf-tools/datatracker.git /workspace

# FETCH ASSETS

mkdir -p /assets
/rsync-assets.sh

# CREATE CONTAINERS

docker volume create mariadb-data
docker create --name=db \
  -e MYSQL_ROOT_PASSWORD=ietf \
  -e MYSQL_DATABASE=ietf_utf8 \
  -e MYSQL_USER=django \
  -e MYSQL_PASSWORD=RkTkDPFnKpko \
  -v mariadb-data:/var/lib/mysql \
  --restart=unless-stopped \
  -h db \
  --network host \
  ghcr.io/ietf-tools/datatracker-db:latest

docker volume create app-assets
docker create --name=datatracker \
  -v /workspace:/workspace
  -v /assets:/assets \
  --restart=unless-stopped \
  -h wiki \
  --network host \
  ghcr.io/requarks/wiki:2
