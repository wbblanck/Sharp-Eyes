# Deploy the capture worker on Oracle Cloud Always Free ($0)

The worker and its PostgreSQL run together under Docker Compose on one Oracle
Cloud "Always Free" Ampere (ARM) server. Within the Always Free limits this
costs nothing. The same steps work on any Linux box with Docker.

## 1. Create the server

1. Sign up at <https://www.oracle.com/cloud/free/>. A card is required for
   identity; Always Free resources are not charged.
2. Pick a **home region** close to the US East coast (for example US East
   Ashburn), since most venue APIs are served from there. It cannot be changed.
3. Compute > Instances > Create instance:
   * Image: Canonical Ubuntu 24.04.
   * Shape: Ampere, `VM.Standard.A1.Flex`, 4 OCPUs, 24 GB memory (the whole
     Always Free allowance).
   * Boot volume: 200 GB (the Always Free block-storage allowance).
   * Add your SSH public key.
   If you see "Out of capacity", try another availability domain or retry
   later; free ARM capacity comes and goes.
4. Leave inbound rules as they are (SSH only). Nothing else needs to be
   reachable from the internet.

### Idle reclamation

Oracle may stop an Always Free instance it considers idle: over 7 days, CPU
(95th percentile), network and memory all under 10%. This worker's CPU and
network use are low, but the Compose file gives PostgreSQL a 4 GB buffer pool,
which keeps memory above 10% of 24 GB once the data is warm. If Oracle still
flags the instance, upgrading the account to Pay As You Go removes
reclamation; Always Free resources stay free on it. Set a $1 budget alert
(Billing > Budgets) if you do.

## 2. Install Docker

```bash
ssh ubuntu@<server-ip>
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu && exit   # log in again for the group to apply
```

## 3. Get the code and start it

The repository is private, so use a GitHub deploy key or a fine-grained
read-only token.

```bash
git clone https://github.com/wbblanck/Sharp-Eyes.git && cd Sharp-Eyes
cp .env.example .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
docker compose up -d --build
```

Compose starts PostgreSQL, applies migrations, then starts the worker. All
three restart automatically after a crash or a reboot.

## 4. Check it

```bash
docker compose ps                                    # worker should be "healthy" after ~10 min
docker compose logs -f worker                        # live log
docker compose exec worker sharp-eyes status         # counts and recent polls per venue
docker compose exec worker sharp-eyes latency-report --hours 24
df -h /                                              # disk use
```

## 5. Update

```bash
cd Sharp-Eyes && git pull && docker compose up -d --build
```

## Disk budget

Book rows are written only when a book changes, so growth depends on how
active the markets are; it is highest on Sundays. In the first 45-minute test
(a quiet Saturday morning, most games 1 to 8 days out) book rows grew about
120 MB an hour, roughly 3 GB a day, nearly all of it Polymarket half and
quarter markets. At that pace the 200 GB disk lasts about two months. Check `df -h` weekly for the
first few weeks. If the disk ever gets tight, narrow `book_scope` for
Polymarket in `config/default.yaml` from `game` to `core`, which drops half and
quarter markets.
