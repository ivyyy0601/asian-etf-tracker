# Deploy on Hetzner (auto daily updates)

A single Hetzner VPS runs everything:

```
Hetzner VPS (Ubuntu, timezone = Asia/Hong_Kong)
├── systemd service : streamlit dashboard   (always on, port 8501)
└── systemd timer   : data collection       (Mon–Fri 08:00 HKT, incremental)
        ↑ both read/write the same ./data folder — no shared-disk tricks needed
```

**Schedule:** runs every weekday morning at **08:00 Hong Kong time**. The market is
still closed then, so it fetches the *previous* trading day's full close — which by
08:00 HKT is available for all 5 markets (Asian closes from the afternoon before, US
close from overnight). Mon–Fri covers all 5 weekday closes; Friday's close is picked
up Monday morning.

Access model: **public** — anyone with `http://<server-ip>:8501` can view it.

---

## 1. Create the server

In the Hetzner Cloud console:
- **Image:** Ubuntu 24.04
- **Type:** CX22 (2 vCPU / 4 GB) is plenty — ~€4/mo
- Add your SSH key, create, note the **public IP**

SSH in:
```bash
ssh root@<server-ip>
```

## 2. Get the code onto the server

Either `git clone` your repo, or copy this folder up from your Mac:
```bash
# from your Mac, in the `new/` folder:
rsync -a --exclude venv --exclude 'data*' ./ root@<server-ip>:/root/etf-tracker/
```

## 3. Run the one-shot installer

```bash
ssh root@<server-ip>
cd /root/etf-tracker
sudo bash deploy/setup.sh
```

That script sets the server timezone to Hong Kong, installs Python, creates the `etf`
user + `/opt/etf-tracker`, builds the virtualenv, installs the systemd dashboard
service + collection timer, and kicks off the **first full data collection** (20–40
min — fine to let it run).

When it finishes it prints the URL: `http://<server-ip>:8501`.

## 4. Open the firewall for port 8501

Hetzner Cloud Firewall (recommended) → add inbound rule **TCP 8501** from `0.0.0.0/0`.
Or on the box itself if you use ufw:
```bash
sudo ufw allow 8501/tcp
```

Done. The dashboard is live and refreshes itself every Tue–Sat.

---

## Day-to-day operations

```bash
# Dashboard status / logs
systemctl status etf-dashboard
journalctl -u etf-dashboard -f

# Force a data update right now
sudo systemctl start etf-collector
journalctl -u etf-collector -f

# When does the collector run next?
systemctl list-timers etf-collector.timer

# After you change code (re-pull / re-rsync into /opt/etf-tracker), restart:
sudo systemctl restart etf-dashboard
```

## Changing the schedule

Edit `OnCalendar=` in `/etc/systemd/system/etf-collector.timer`, then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart etf-collector.timer
```

## Notes

- **DATA_ROOT** is set to `/opt/etf-tracker` in both units, so CSVs land next to the
  app. The `data*/` folders are gitignored — they only ever live on the server.
- Collection is **incremental**: each run only fetches days missing since last time,
  so a daily run is quick after the initial backfill.
- Want a domain + HTTPS later? Put Nginx (or Caddy) in front of `localhost:8501` and
  point an A record at the server IP. Not required for the public-IP setup above.
