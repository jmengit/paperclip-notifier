# Unraid installation checklist

1. Install the published `paperclip-notifier` template from **Docker → Add Container → Template repositories** using:
   `https://raw.githubusercontent.com/jmengit/paperclip-notifier/main/unraid-template.xml`
2. Create `/mnt/user/appdata/paperclip-notifier/config` and `/mnt/user/appdata/paperclip-notifier/data`.
3. Copy `config.example.yaml` to `/mnt/user/appdata/paperclip-notifier/config/config.yaml`.
4. Set `paperclip.company_id` and enable only the destinations you intend to use.
5. Create protected secret files for the Paperclip API key and enabled destinations. Mount them read-only at `/run/secrets/` and keep them out of GitHub and screenshots.
6. Confirm the Paperclip API address. The template default is `http://192.168.86.201:3200`; use `http://<paperclip-container>:3100` only when both containers share a user-defined Docker network.
7. Set the host health port to an unused LAN-only port, normally `8080`. Do not publish it through Cloudflare or a reverse proxy.
8. Pin the image tag or digest. Start the container.
9. Check **Logs** for a successful poll and no configuration error.
10. Verify `http://UNRAID-IP:8080/readyz` reports `ok: true` and inspect `/status` for outbox state.
11. Create one controlled Paperclip test activity and confirm only the intended destination receives it with a link beginning `https://paperclip.tcjacobyco.com/`.
12. Keep `/mnt/user/appdata/paperclip-notifier/data` when upgrading. Do not delete `state.sqlite3` unless you intentionally want to re-baseline.

## Important limitation

The Unraid template can describe secret-file paths but cannot safely create Docker secrets or inject real credentials. Secret files must be provisioned by the operator or by an existing secret-management workflow. Never put API keys, bot tokens, webhook URLs, or authorization headers in the public repository, template defaults, or image.

## Rollback

Stop the container, select the previous pinned image tag, and restart with the same `/config` and `/data` mounts. Do not remove the data directory during rollback.

## Connectivity options

- **Simplest:** bridge networking with `PAPERCLIP_BASE_URL=http://192.168.86.201:3200`.
- **Preferred when available:** attach to the Paperclip user-defined network and use Paperclip's service DNS name on port `3100`.
- **Do not assume:** `paperclip:3100` is not a universal hostname; it works only if the selected network provides that alias.

The notifier is read-only against Paperclip and never needs the Paperclip database or Docker socket.
