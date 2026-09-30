# Öffentlich erreichbar machen

Damit Mitspieler die Karte von unterwegs öffnen können, gehört sie hinter einen **Reverse Proxy mit HTTPS**.
Den Port 8050 nicht direkt ins Internet freigeben.

## Was öffentlich ist
- **Lesen** ist für alle offen, die die Adresse kennen (Positionen, Fabrik, Spielernamen, Notizen).
- **Schreiben** (Notizen, Fabriknamen und -status) verlangt `MAP_PIN_PASSWORD`. Nach 10 Fehlversuchen ist die IP
  10 Minuten gesperrt. Ohne gesetztes Passwort ist Schreiben komplett aus.
- Der Spielserver selbst ist von der Karte aus nicht erreichbar; Zugangsdaten zur Save-Quelle verlassen den Dienst nie.

Wer die Karte nur für die eigene Gruppe will, setzt davor eine Anmeldung (Basic Auth im Proxy, Authelia, Cloudflare Access …).

## Caddy (am einfachsten, HTTPS automatisch)
`Caddyfile`:
```
karte.example.de {
    reverse_proxy 127.0.0.1:8050
}
```
Mit Passwortschutz davor:
```
karte.example.de {
    basic_auth {
        gruppe $2a$14$…   # caddy hash-password
    }
    reverse_proxy 127.0.0.1:8050
}
```

## nginx
```nginx
server {
    listen 443 ssl http2;
    server_name karte.example.de;
    ssl_certificate     /etc/letsencrypt/live/karte.example.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/karte.example.de/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8050;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Traefik (Docker-Labels)
In `docker-compose.yml` beim Dienst `map` statt `ports:`:
```yaml
    labels:
      - traefik.enable=true
      - traefik.http.routers.karte.rule=Host(`karte.example.de`)
      - traefik.http.routers.karte.entrypoints=websecure
      - traefik.http.routers.karte.tls.certresolver=letsencrypt
      - traefik.http.services.karte.loadbalancer.server.port=8050
    networks: [traefik]
```

## Cloudflare
Funktioniert ohne Sonderregeln: Die Website-Dateien tragen einen Hash im Namen, die API-Antworten sind
`no-cache` mit ETag — Cloudflare liefert also nie veraltete Daten aus.

## Hinweis zur Sperre nach Fehlversuchen
Die Sperre gilt je Besucher-IP. Die Karte liest sie aus `CF-Connecting-IP` (Cloudflare) oder `X-Forwarded-For`
(nginx-Beispiel oben, Caddy und Traefik setzen den Header automatisch). Fehlt beides, sieht sie nur die IP des Proxys —
dann teilen sich alle Besucher eine Sperre.
