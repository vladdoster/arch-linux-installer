#!/usr/bin/env bash
set -e

rm -f install.conf
rm -f install.sh

curl -O https://raw.githubusercontent.com/vladdoster/arch-linux-installer/master/install.sh
curl -O https://raw.githubusercontent.com/vladdoster/arch-linux-installer/master/install.conf

chmod +x install.conf
chmod +x install.sh
