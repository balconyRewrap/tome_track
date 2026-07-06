# Host Nginx Deployment

Use this mode when TLS is terminated by one server-level Nginx that also serves
other projects.

Build/copy the frontend into `tome_track/dist`, then run:

```bash
docker compose -f docker-compose.host-nginx.yml up -d --build
```

The project Nginx will listen only on `127.0.0.1:18081` by default. The host
Nginx should proxy `books.tometrack.de` to that port; see
`deploy/host-nginx-books.conf.example`.

Required `.env` values for this mode:

```env
ALLOWED_HOSTS=books.tometrack.de
CORS_ALLOWED_ORIGINS=https://books.tometrack.de
FRONTEND_URL=https://books.tometrack.de
DOMAIN_NAME=books.tometrack.de
```

Do not run the project `certbot` service in this mode. Certificates are managed
by the host Nginx/Certbot.
