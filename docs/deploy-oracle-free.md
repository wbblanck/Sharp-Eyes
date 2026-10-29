# Set up Sharp-Eyes on Oracle Cloud Always Free ($0)

Sharp-Eyes (the capture worker and its PostgreSQL database) runs on one free
Oracle Cloud ARM server, around the clock. Your own computer only needs a web
browser, and it can be off once setup is done.

There are five steps. Two of them are a single pasted command each, and the
scripts do the fiddly parts:

1. Create an Oracle account (browser)
2. Open Cloud Shell and make an SSH key
3. Create the server with one command (it retries "Out of capacity" for you)
4. Log in to the server and install Sharp-Eyes with one command
5. Check that it's running

**Cloud Shell** is a free terminal built into the Oracle website. Commands in
steps 2 to 4 are typed there. Paste with Ctrl+Shift+V (or right-click >
Paste) and press Enter.

## What's free

Oracle's Always Free tier currently allows, at no charge:

* ARM (Ampere A1) servers totalling **2 OCPUs and 12 GB of memory**. Oracle
  halved this from 4 OCPUs / 24 GB in June 2026; older guides still show the
  old numbers.
* **200 GB** of disk in total.

This guide uses exactly that: one server with 2 OCPUs, 12 GB and a 200 GB
disk. Don't create a second server, or you'll go over the free limit.

## 1. Create the Oracle account [browser]

1. Go to <https://www.oracle.com/cloud/free/> and click **Start for free**.
2. Oracle asks for a credit card to prove identity. Always Free resources are
   not charged, and the account stays free unless you choose to upgrade it.
3. **Home region**: pick **US East (Ashburn)** if you can, since most venue
   APIs are served from the US East coast. This can't be changed later. Any
   US region works if Ashburn isn't offered.
4. Wait for the "your account is ready" email (minutes, sometimes an hour or
   two), then sign in at <https://cloud.oracle.com>.

## 2. Open Cloud Shell and make an SSH key

1. In the top bar of the Oracle console, at the right, click the terminal
   icon (**>_**). If you see a **</>** (Developer tools) icon instead, click
   it and choose **Cloud Shell**. A black terminal opens at the bottom of
   the page; the first time it takes about a minute.
2. Paste this and press Enter:

   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
   ```

   It prints a small box of random characters when it's done. If it asks
   "Overwrite (y/n)?", type `n`: you already have a key, which is fine.

The key stays in Cloud Shell, so later steps use it automatically. You
don't need to copy or paste it anywhere.

## 3. Create the server [Cloud Shell]

Paste this and press Enter:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/wbblanck/Sharp-Eyes/main/scripts/oracle-create-server.sh)
```

The script creates the network, then asks Oracle for the free server (2 OCPUs,
12 GB, 200 GB disk, Ubuntu 24.04). Free ARM servers are often sold out, so
when Oracle answers "out of capacity" the script waits 90 seconds and asks
again, trying every zone in your region. Leave the tab open. It can take
minutes or, on a busy day, several hours.

When it works, it prints:

```
Got it! Server is running. Public IP: 129.153.x.x
Next: ssh ubuntu@129.153.x.x
```

Write the IP address down.

**If Cloud Shell closes** (it times out when left alone for a while), open
it again and paste the same command. It picks up where it left off and won't
create a second server.

**If it stops with an error**, copy what it printed and send it to Claude.

## 4. Install Sharp-Eyes on the server [Cloud Shell, then server]

Log in to the server, using your IP from step 3:

```bash
ssh ubuntu@129.153.x.x
```

The first time it asks "Are you sure you want to continue connecting?". Type
`yes`. The prompt changes to something like `ubuntu@sharp-eyes:~$`, which
means you're on the server.

Now paste:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/wbblanck/Sharp-Eyes/main/scripts/server-setup.sh)
```

This installs Docker, downloads Sharp-Eyes, creates a random database
password, and starts everything. The first build takes 5 to 10 minutes. It
ends with "Done. Sharp-Eyes is running".

Sharp-Eyes now runs as a service. It restarts by itself after a crash or a
server reboot, and you can close Cloud Shell and your browser.

If Cloud Shell disconnects during the install, log in again with `ssh` and
paste the same command; it's safe to run twice.

## 5. Check it's running [server]

Log out and back in once first (type `exit`, then `ssh ubuntu@<your-ip>`) so
the `docker` command works without `sudo`. Then:

```bash
cd ~/Sharp-Eyes
docker compose ps                                  # worker "healthy" after ~10 min; migrate "exited (0)" is normal
docker compose exec worker sharp-eyes status       # rows captured per venue
docker compose logs --tail 50 worker               # recent log lines
df -h /                                            # disk use
```

After a day or so of capture:

```bash
docker compose exec worker sharp-eyes latency-report --hours 24
docker compose exec worker sharp-eyes copyability-report --hours 72
```

## Updating later

When new code is merged on GitHub, log in to the server and run:

```bash
cd ~/Sharp-Eyes && git pull && docker compose up -d --build
```

Database changes apply automatically before the worker restarts.

## Troubleshooting

### Out of capacity for hours

The script in step 3 keeps trying, and that's normally all you need. To ask
for a smaller server, which is sometimes easier to get (Sharp-Eyes runs on
1 OCPU / 6 GB), run:

```bash
OCPUS=1 MEMORY_GB=6 bash <(curl -fsSL https://raw.githubusercontent.com/wbblanck/Sharp-Eyes/main/scripts/oracle-create-server.sh)
```

Upgrading the account to **Pay As You Go** (Billing > Upgrade) usually ends
capacity errors. Free resources stay free on it, but anything beyond the free
limits would be charged to your card, so this guide doesn't rely on it. If
you ever do it, set a $1 budget alert first (Billing > Budgets).

### "Permission denied (publickey)" on ssh

You're logging in from somewhere other than the Cloud Shell where you made the
key in step 2, or the key was made after the server was created. Log in from
Cloud Shell. If it still fails, ask Claude.

### Oracle emails that the server is idle

Oracle may stop an Always Free server that looks idle for 7 days (CPU,
network and memory all under 10%). PostgreSQL's memory use normally keeps it
above that. If it happens, start it again from the console (Menu > Compute >
Instances > sharp-eyes > Start). Everything comes back up by itself.

### Creating the server by hand (instead of step 3)

Menu (top left) > **Compute** > **Instances** > **Create instance**. Choose
image **Canonical Ubuntu 24.04** (not Minimal), shape **Ampere** >
**VM.Standard.A1.Flex** with 2 OCPUs and 12 GB, keep "assign a public IPv4
address" on, paste your public key (`cat ~/.ssh/id_rsa.pub` in Cloud Shell)
under SSH keys, and set the boot volume to 200 GB. Oracle's screens change
often, so labels may differ.

## Disk budget

Book rows are written only when a book changes, so growth depends on how
active the markets are; it is highest on Sundays. In the first 45-minute test
(a quiet Saturday morning, most games 1 to 8 days out) book rows grew about
120 MB an hour, roughly 3 GB a day. About two thirds of book rows were
Polymarket markets other than full-game moneyline, spread and total. At that
pace the 200 GB disk lasts about two months. Check `df -h` weekly for the
first few weeks. If the disk gets tight, narrow `book_scope` for Polymarket
in `config/default.yaml` from `game` to `core`, which keeps only full-game
moneyline, spread and total and roughly halves growth.
