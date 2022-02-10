#!/bin/sh
# (Re-)generate all deploy keys on https://github.com/rhinstaller/anaconda/settings/environments

set -eux

ORG=rhinstaller
THIS=anaconda

cd ui/webui

[ -e bots ] || make -f Makefile.am bots

# for workflows pushing to our own repo: npm-update.yml
bots/github-upload-secrets --receiver "${ORG}/${THIS}" --env self --ssh-keygen DEPLOY_KEY --deploy-to "${ORG}/${THIS}"
