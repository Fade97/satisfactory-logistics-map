# Public access

To let other players open the map from anywhere, put it behind a **reverse proxy with HTTPS**.
Do not expose port 8050 directly to the internet.

## What is public
- **Reading** is open to anyone who knows the address (positions, factory, player names, notes).
- **Writing** (notes, factory names and status) requires `MAP_PIN_PASSWORD`. After 10 failed attempts the IP is
  blocked for 10 minutes. Without a password set, writing is disabled completely.
- The game server itself cannot be reached through the map; credentials for the save source never leave the service.

If you want the map only for your own group, put a login in front of it (basic auth in the proxy, Authelia, Cloudflare Access …).

## Caddy (easiest, automatic HTTPS)
`Caddyfile`:
```
map.example.com {
    reverse_proxy 127.0.0.1:8050
}
```
With password protection in front:
```
map.example.com {
    basic_auth {
        group $2a$14$…   # caddy hash-password
    }
    reverse_proxy 127.0.0.1:8050
}
```

## nginx
```nginx
server {
    listen 443 ssl http2;
    server_name map.example.com;
    ssl_certificate     /etc/letsencrypt/live/map.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/map.example.com/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8050;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Traefik (Docker labels)
In `docker-compose.yml`, for the `map` service, instead of `ports:`:
```yaml
    labels:
      - traefik.enable=true
      - traefik.http.routers.map.rule=Host(`map.example.com`)
      - traefik.http.routers.map.entrypoints=websecure
      - traefik.http.routers.map.tls.certresolver=letsencrypt
      - traefik.http.services.map.loadbalancer.server.port=8050
    networks: [traefik]
```

## Cloudflare
Works without special rules: the website files carry a hash in their names, and the API responses are
`no-cache` with an ETag — so Cloudflare never serves stale data.

## Note on blocking after failed attempts
The block applies per visitor IP. The map reads it from `CF-Connecting-IP` (Cloudflare) or `X-Forwarded-For`
(nginx example above; Caddy and Traefik set the header automatically). If both are missing, it only sees the proxy's IP —
then all visitors share one block.
