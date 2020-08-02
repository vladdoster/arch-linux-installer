#!/usr/bin/env bash
set -e

rm -f install.conf
rm -f install.sh

curl -O https://raw.githubusercontent.com/vladdoster/arch-linux-installer/master/install.sh
curl -O https://raw.githubusercontent.com/vladdoster/arch-linux-installer/master/install.conf
curl -O https://raw.githubusercontent.com/vladdoster/dotfiles-installer/master/linux-install
curl -O https://raw.githubusercontent.com/vladdoster/dotfiles-installer/master/shared-functions

chmod +x linux-install
chmod +x install.conf
chmod +x install.sh
chmod +x shared-functions
