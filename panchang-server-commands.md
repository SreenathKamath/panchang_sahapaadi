# Panchang Server — Command Reference

Everyday commands for operating the live backend, grouped in the order
you'd actually reach for them. `# On your PC` = type this in your own
PowerShell. `# On the server` = type this after you've SSH'd in.

Your server's address: `16.113.105.153` (or your DuckDNS name,
`panchang-api.duckdns.org`). Adjust the key path if it's different from
what's shown here.

---

## 1. Connect to the server

```powershell
# On your PC
ssh -i "PATH_TO_YOUR_KEY\panchang-key.pem" ubuntu@16.113.105.153
```

You'll know it worked when the prompt changes to `ubuntu@ip-172-31-...:~$`.
Everything below (until "Disconnect" at the end) runs **on the server**.

---

## 2. Look around — what's actually running right now

```bash
# See running containers (this is your main "is it alive" check)
docker ps

# See ALL containers, including stopped ones
docker ps -a

# See what images you have built, and their size
docker images

# List files in the current folder
ls
ls -la          # includes hidden files like .env

# Which folder am I in?
pwd
```

`docker ps` is the one you'll run most — if `panchang-backend` shows up
with a `STATUS` of `Up X hours`, the app is alive.

---

## 3. Logs — see what the app is actually doing

```bash
# Watch logs live (like "tail -f") -- Ctrl+C to stop watching, container keeps running
docker logs -f panchang-backend

# Just the last 100 lines, no live-follow
docker logs --tail 100 panchang-backend

# Logs with timestamps, useful when debugging something that happened earlier
docker logs -t panchang-backend
```

Caddy (the HTTPS reverse proxy) has its own logs, separate from Docker:

```bash
# Caddy's live logs
sudo journalctl -u caddy -f

# Caddy's last 50 log lines
sudo journalctl -u caddy -n 50 --no-pager
```

---

## 4. Check the environment config the container is using

```bash
# See the actual .env file on disk (be careful, this shows your real API keys)
cat .env

# See what env vars the RUNNING container was actually started with
docker inspect panchang-backend --format '{{range .Config.Env}}{{println .}}{{end}}'
```

If you ever change `.env`, the running container does **not** pick it up
automatically — you have to restart it (Section 5) for the new values to
take effect.

---

## 5. Restart / stop / start the app

```bash
# Restart -- use this after editing .env, or if the app seems stuck
docker restart panchang-backend

# Stop it (container exists but isn't running)
docker stop panchang-backend

# Start it again after stopping
docker start panchang-backend

# Stop AND permanently remove the container (you'll need to `docker run` again after this)
docker stop panchang-backend && docker rm panchang-backend
```

Since it was created with `--restart unless-stopped`, a plain `docker
restart` or a full server reboot brings it back automatically — you only
need `docker start` if you deliberately `docker stop`'d it first.

---

## 6. Deploy a code update

Whenever you push new code (a bug fix, next year's data, etc.) to GitHub:

```bash
cd ~/panchang_sahapaadi
git pull
docker build -t panchang-backend .
docker stop panchang-backend && docker rm panchang-backend
docker run -d --name panchang-backend --restart unless-stopped \
  -p 127.0.0.1:7860:7860 --env-file .env panchang-backend
docker logs -f panchang-backend
```

Watch the logs at the end to confirm it started cleanly before moving on.

---

## 7. Check server health (memory, disk)

```bash
# Memory usage -- watch "available" isn't near zero
free -h

# Disk usage -- watch this doesn't fill up (Docker images/builds eat space over time)
df -h /

# Live resource usage per container (Ctrl+C to exit)
docker stats

# Was anything ever killed for using too much memory?
dmesg | grep -i oom
```

---

## 8. Free up disk space (if `df -h /` looks tight)

```bash
# Remove old/unused Docker images and build cache -- safe, only removes unused stuff
docker system prune -f

# See exactly what's taking up space in Docker
docker system df
```

---

## 9. Stop or start the whole server (not just the app)

Only do this from the **AWS Console** (EC2 → Instances → select
`panchang-backend` → Instance state):

- **Stop**: pauses billing for the compute hours, but the 30GB EBS disk
  still bills (~$2.40/month) the whole time it's stopped. Your Elastic IP
  will also start costing a small amount if left attached to a *stopped*
  instance — either release it or accept that small charge.
- **Start**: boots back up with everything intact (same disk, same
  Elastic IP, same DNS). The Docker container and Caddy both start
  automatically since they're set up as system services / `--restart
  unless-stopped`.
- **Terminate**: permanently deletes the instance *and* its disk. Only do
  this if you're actually done with it for good — there's no undo.

---

## 10. Disconnect

```bash
exit
```

Takes you back to your own PC's prompt. The server and your container keep
running in the background — closing the SSH window does not stop
anything.
