# Deploy the capture worker on Oracle Cloud Always Free ($0)

The worker and its PostgreSQL run together under Docker Compose on one Oracle
Cloud "Always Free" Ampere (ARM) server. Within the Always Free limits this
costs nothing. The same steps work on any Linux box with Docker.

Total time is about 45 minutes, most of it waiting. Everything happens in
your web browser; nothing is installed on your own computer. The steps run in
three places, marked at the start of each step:

* **[Browser]**: the Oracle Cloud console.
* **[Cloud Shell]**: a free terminal built into the Oracle console. Click the
  **>_** icon at the top right (Developer tools > **Cloud Shell**) and it
  opens at the bottom of the page.
* **[Server]**: the Oracle server, after you `ssh` into it from Cloud Shell.
  The prompt changes to `ubuntu@sharp-eyes`.

Your own computer only needs a browser, and it can be off once setup is done.
The worker runs on the server around the clock.

## 1. Create the Oracle account [Browser]

1. Go to <https://www.oracle.com/cloud/free/> and click **Start for free**.
2. A credit card is required to prove identity. Always Free resources are not
   charged, and the account stays on the free tier unless you upgrade it.
3. **Home region**: pick **US East (Ashburn)**, since most venue APIs are
   served from the US East coast. It cannot be changed later.
4. Wait for the "your account is ready" email (minutes, sometimes an hour or
   two), then sign in at <https://cloud.oracle.com>.

## 2. Make an SSH key [Cloud Shell]

The server lets in only someone holding this key. Open Cloud Shell and run:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""   # no questions asked
cat ~/.ssh/id_rsa.pub                              # copy the whole line it prints
```

The line starts with `ssh-rsa AAAA` and is safe to paste into Oracle. The key
stays in Cloud Shell's home folder, so later logins from Cloud Shell just
work. Never share `~/.ssh/id_rsa` (the file without `.pub`).

## 3. Create the server [Browser]

Menu (top left) > **Compute** > **Instances** > **Create instance**.

1. **Name**: `sharp-eyes`.
2. **Placement**: leave the availability domain as is for now (see "Out of
   capacity" below).
3. **Image and shape** > **Edit**:
   * **Change image** > **Ubuntu** > **Canonical Ubuntu 24.04** (not the
     "Minimal" one).
   * **Change shape** > **Ampere** > `VM.Standard.A1.Flex`, then set
     **4 OCPUs** and **24 GB memory**. The "Always Free-eligible" label should
     show next to it.
4. **Networking**: leave **Create new virtual cloud network** and **Create new
   public subnet** selected, and make sure **Assign a public IPv4 address** is
   on.
5. **Add SSH keys**: choose **Paste public keys** and paste the line from
   step 2.
6. **Boot volume**: tick **Specify a custom boot volume size** and enter
   **200** GB (the whole Always Free storage allowance). Leave the
   performance setting at its default.
7. Click **Create**. After a minute or two the state turns **Running**. Copy
   the **Public IP address** from the instance page.

Leave the firewall (security list) as it is. Only SSH is open, and nothing
else needs to be reachable from the internet.

### Out of capacity

Free ARM servers are popular and Ashburn often answers "Out of capacity for
shape VM.Standard.A1.Flex". In order of preference:

1. Go back to **Placement** and try another availability domain (AD-1, AD-2,
   AD-3), then click **Create** again.
2. Retry at a different time of day; capacity frees up through the day.
3. Make a smaller server: 2 OCPUs and 12 GB is enough for this worker.
4. Upgrading the account to **Pay As You Go** (Billing > Upgrade) usually
   ends the capacity errors. Always Free resources stay free on it, but
   anything outside the free limits would be billed, so only do this with a
   $1 budget alert set (Billing > Budgets > Create budget).

## 4. Log in and install Docker [Cloud Shell, then Server]

```bash
ssh ubuntu@<public-ip>           # in Cloud Shell; type "yes" the first time
```

You are now on the server. Install Docker, Compose and git:

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker        # start Docker now and at every boot
sudo usermod -aG docker ubuntu
exit
```

Log in again with `ssh ubuntu@<public-ip>` so the `docker` group applies,
then check that `docker ps` prints an empty table rather than "permission
denied".

## 5. Get the code and start it [Server]

```bash
git clone https://github.com/wbblanck/Sharp-Eyes.git
cd Sharp-Eyes
cp .env.example .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
docker compose up -d --build
```

The first build takes 5 to 10 minutes. Compose then starts PostgreSQL,
applies database migrations, and starts the worker. The database and the
worker restart on their own after a crash or a reboot, so this is already
running as a service; you can close Cloud Shell and the browser.

Cloud Shell disconnects after about 20 minutes of no typing. If that happens
during the build, open it again, `ssh ubuntu@<public-ip>`, `cd Sharp-Eyes` and
run `docker compose up -d --build` once more; it picks up where it stopped.

## 6. Check it [Server]

```bash
cd ~/Sharp-Eyes
docker compose ps                                    # worker should be "healthy" after ~10 min
docker compose logs -f worker                        # live log, Ctrl-C to stop watching
docker compose exec worker sharp-eyes status         # counts and recent polls per venue
docker compose exec worker sharp-eyes latency-report --hours 24
docker compose exec worker sharp-eyes copyability-report --hours 72
df -h /                                              # disk use
```

`migrate` shows as "exited (0)" in `docker compose ps`. That is expected: it
runs once at start-up and stops.

A good test that everything survives a restart: `sudo reboot`, wait a minute,
log in again and run `docker compose ps`.

## 7. Update [Server]

When a pull request is merged on GitHub:

```bash
cd ~/Sharp-Eyes && git pull && docker compose up -d --build
```

New database migrations run automatically before the worker restarts.

## Idle reclamation

Oracle may stop an Always Free instance it considers idle: over 7 days, CPU
(95th percentile), network and memory all under 10%. This worker's CPU and
network use are low, but the Compose file gives PostgreSQL a 4 GB buffer pool,
which keeps memory above 10% of 24 GB once the data is warm. If Oracle
emails that the instance is idle, restart it from the console (Instances >
sharp-eyes > Start); Compose brings everything back up. Pay As You Go
accounts are not reclaimed (see "Out of capacity" for its trade-off).

## Disk budget

Book rows are written only when a book changes, so growth depends on how
active the markets are; it is highest on Sundays. In the first 45-minute test
(a quiet Saturday morning, most games 1 to 8 days out) book rows grew about
120 MB an hour, roughly 3 GB a day. About two thirds of book rows were Polymarket
markets other than full-game moneyline, spread and total (unclassified
markets, halves, quarters, team totals). At that pace the 200 GB disk lasts
about two months. Check `df -h` weekly for the
first few weeks. If the disk ever gets tight, narrow `book_scope` for
Polymarket in `config/default.yaml` from `game` to `core`, which keeps only
full-game moneyline, spread and total and roughly halves growth.
