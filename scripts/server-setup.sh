#!/usr/bin/env bash
# Installs Docker on a fresh Ubuntu server and starts Sharp-Eyes (database +
# capture worker) as always-on services. Safe to run again: it updates the
# code and restarts. See docs/deploy-oracle-free.md.
set -euo pipefail

REPO=${REPO:-https://github.com/wbblanck/Sharp-Eyes.git}
BRANCH=${BRANCH:-main}
DIR="$HOME/Sharp-Eyes"

echo "== Installing Docker and git"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io docker-compose-v2 git openssl
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "== Getting the code"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --branch "$BRANCH" "$REPO" "$DIR"
fi
cd "$DIR"

if [ ! -f .env ]; then
  echo "== Writing .env (database password and memory settings)"
  cp .env.example .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
  # Size PostgreSQL to this server: a quarter of RAM for its buffers (1-4 GB),
  # two thirds as the planner's cache estimate.
  mem_gb=$(awk '/MemTotal/ {print int($2 / 1048576 + 0.5)}' /proc/meminfo)
  buffers=$((mem_gb / 4)); [ "$buffers" -lt 1 ] && buffers=1; [ "$buffers" -gt 4 ] && buffers=4
  cache=$((mem_gb * 2 / 3)); [ "$cache" -lt 1 ] && cache=1
  printf 'PG_SHARED_BUFFERS=%sGB\nPG_EFFECTIVE_CACHE_SIZE=%sGB\n' "$buffers" "$cache" >> .env
fi

echo "== Building and starting (first time takes 5-10 minutes)"
sudo docker compose up -d --build
sudo docker compose ps

echo
echo "Done. Sharp-Eyes is running and restarts by itself after crashes and reboots."
echo "Log out and back in once (type: exit, then ssh again) so 'docker' works without sudo."
