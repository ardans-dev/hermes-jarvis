#!/bin/bash
echo '⚡ Updating Hermes Jarvis...'
git pull origin main
pm2 restart hermes-jarvis
pm2 logs hermes-jarvis --lines 20
