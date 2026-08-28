# Unraid installation checklist

1. Install the published `paperclip-notifier` template from **Docker → Add Container → Template repositories** using:
   `https://raw.githubusercontent.com/jmengit/paperclip-notifier/main/unraid-template.xml`
2. Create `/mnt/user/appdata/paperclip-notifier/config` and `/mnt/user/appdata/paperclip-notifier/data`.
3. Copy `config.example.yaml` to `/mnt/user/appdata/paperclip-notifier/config/config.yaml`.
4. Set `paperclip.company_id`, enable `destinations.ifttt`, and leave direct Discord/Telegram disabled for the initial deployment.
5. In IFTTT, create a Webhooks → Discord Applet using the exact event name `paperclip_activity`. Map `Value1` to the message summary, `Value2` to event type, and `Value3` to the Paperclip link.
6. Create protected files for the Paperclip API key and IFTTT Webhooks key. Mount them read-only at `/run/secrets/` and keep them out of GitHub and screenshots. The IFTTT key file must be `/run/secrets/ifttt_webhooks_key` unless you change `IFTTT_WEBHOOKS_KEY_FILE`.
7. Confirm the Paperclip API address. The template default is `http://192.168.86.201:3200`; use `http://<paperclip-container>:3100` only when both containers share a user-defined Docker network.
8. Set the host health port to an unused LAN-only port, normally `8080`. Do not publish it through Cloudflare or a reverse proxy.
9. Pin the image tag or digest. Start the container.
10. Check **Logs** for a successful poll and no configuration error.
11. Verify `http://UNRAID-IP:8080/readyz` reports `ok: true` and inspect `/status` for outbox state.
12. Create one controlled Paperclip test activity and confirm IFTTT forwards it to Discord with a link beginning `https://paperclip.tcjacobyco.com/`.
13. Keep `/mnt/user/appdata/paperclip-notifier/data` when upgrading. Do not delete `state.sqlite3` unless you intentionally want to re-baseline.

## Important limitation

The Unraid template can describe secret-file paths but cannot safely create Docker secrets or inject real credentials. Secret files must be provisioned by the operator or by an existing secret-management workflow. Never put API keys, IFTTT keys, bot tokens, webhook URLs, or authorization headers in the public repository, template defaults, or image. This template is only native Unraid container handling; it does not send Unraid notifications.

## Rollback

Stop the container, select the previous pinned image tag, and restart with the same `/config` and `/data` mounts. Do not remove the data directory during rollback.

## Connectivity options

- **Simplest:** bridge networking with `PAPERCLIP_BASE_URL=http://192.168.86.201:3200`.
- **Preferred when available:** attach to the Paperclip user-defined network and use Paperclip's service DNS name on port `3100`.
- **Do not assume:** `paperclip:3100` is not a universal hostname; it works only if the selected network provides that alias.

The notifier is read-only against Paperclip and never needs the Paperclip database or Docker socket.
