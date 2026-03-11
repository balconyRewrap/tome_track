# TomeTrack

![Python](https://img.shields.io/badge/python-3.12-blue)
![Django](https://img.shields.io/badge/django-6-green)
![DRF](https://img.shields.io/badge/DRF-3.16-red)
![Docker](https://img.shields.io/badge/docker-ready-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**TomeTrack** is a REST API backend for a personal book-tracking application. It lets users manage their reading library, track progress and statuses, write reviews, and get book recommendations — all through a clean, documented API.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Data Model Overview](#data-model-overview)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [Pagination & Filtering](#pagination--filtering)
- [Security](#security)
- [Running Tests](#running-tests)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Authentication** — Registration, JWT access/refresh tokens with rotation and blacklisting, logout
- **Password management** — Change password, reset via email (token-based, async via Celery)
- **Books** — CRUD, full-text search, cover image uploads, book types (book / comic)
- **Authors & Tags** — Separate resources linked to books
- **Personal library (UserBook)** — Track reading status, current page/chapter, re-read count, rating (0–10), masterpiece flag
- **Reviews** — Per-book reviews with search; list your own reviews via `/users/me/reviews/`
- **Admin endpoints** — List and manage users via protected admin-only routes
- **Caching** — Redis-backed caching for frequently accessed data
- **Rate limiting** — 60 req/min for anonymous users, 300 req/min for authenticated
- **API docs** — Auto-generated Swagger UI and ReDoc (available in DEBUG mode)

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Django 6 + Django REST Framework |
| Database | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| Task queue | Celery 5 + django-celery-beat |
| Auth | djangorestframework-simplejwt |
| API docs | drf-spectacular (OpenAPI 3) |
| Web server | Gunicorn + Nginx |
| Containerization | Docker + Docker Compose |
| Package manager | uv |
| Linter / Formatter | Ruff |
| Testing | pytest + coverage |

## Project Structure

```
tome_track/
├── apps/
│   ├── books/        # Books, Authors, Tags
│   ├── reviews/      # Book reviews
│   ├── userbooks/    # Personal reading library
│   ├── users/        # Auth, registration, profile, admin views
│   └── common/       # Shared models, mixins, exceptions, pagination
├── config/
│   ├── settings/     # base.py / local.py / production.py
│   ├── celery.py
│   └── urls.py
├── nginx/
│   └── nginx.conf
├── requirements/
├── templates/
│   └── emails/       # Password reset email templates
├── docker-compose.yml
├── Dockerfile
└── manage.py
```

## Architecture

The project follows a modular Django app structure where each domain is isolated into its own app:

- **users** — authentication, profile management, password reset, admin endpoints
- **books** — books, authors, tags and full-text search
- **userbooks** — personal reading library with progress tracking
- **reviews** — book reviews with search
- **common** — shared utilities: pagination, mixins, exceptions, validators, cache helpers

### Key architectural decisions

- **JWT authentication** with token rotation and blacklisting on logout
- **Modular Django apps** — clear separation of domain concerns
- **Caching layer** (Redis + django-redis) on high-traffic list endpoints
- **Async email tasks** via Celery — password reset emails are dispatched as background jobs
- **Rate limiting** — `60 req/min` for anonymous, `300 req/min` for authenticated users
- **Custom exception handler** — all errors return a consistent JSON shape
- **OpenAPI schema** auto-generated via drf-spectacular, available as Swagger UI and ReDoc

## Data Model Overview

Core entities and their relationships:

```
User
  │
  │ 1..*
  ▼
UserBook ◄──────── Book
                    │
                    │ *..*
                    ▼
                  Author
                    │
                    │ *..*   (also)
                  Tag ◄──────Book

User
  │
  │ 1..*
  ▼
Review ──────────► Book
```

| Model | Description |
|---|---|
| `User` | Custom user model with roles (`user` / `admin`) and JWT token versioning |
| `Book` | Book entry with title, cover, description, type (`book` / `comic`), authors, tags |
| `Author` | Author with name and slug |
| `Tag` | Genre / category tag with name and slug |
| `UserBook` | User–Book relation: reading status, current page/chapter, rating (0–10), re-read count, masterpiece flag |
| `Review` | User review for a book: text content and rating |
| `PasswordResetToken` | Secure one-time token for password reset flow |

## Production Deployment

The application runs fully containerised. The request flow is:

```
Client → Nginx (port 80) → Gunicorn → Django → PostgreSQL
                                         │
                                       Redis
                                         │
                                    Celery Worker / Beat
```

- **Nginx** serves static files directly and proxies API requests to Gunicorn
- **Gunicorn** runs 3 workers by default (configurable)
- **Celery Worker** handles async tasks (e.g. password reset emails)
- **Celery Beat** manages periodic/scheduled tasks using `django-celery-beat` and a database scheduler

To deploy:

```bash
cp .env.example .env_production
# fill in all required production values
docker-compose up --build -d
```

## Getting Started

### Prerequisites

- **Docker & Docker Compose** — for the containerised setup
- **Python 3.12 + uv** — for local development without Docker

---

### Option 1: Docker (recommended)

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/tome_track.git
cd tome_track

# 2. Create the environment file
cp .env.example .env.production
# Edit .env_production and fill in all required values

# 3. Build and start all services
docker-compose up --build
```

The API will be available at **http://localhost**.

Services started:
- `django` — application server (Gunicorn)
- `nginx` — reverse proxy on port 80
- `db` — PostgreSQL 16
- `redis` — Redis 7
- `celery_worker` — async task worker
- `celery_beat` — periodic task scheduler

---

### Option 2: Local development

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/tome_track.git
cd tome_track

# 2. Install dependencies
uv sync

# 3. Set up environment
cp .env.example .env
# Edit .env — set DEBUG=True, and point DATABASE_URL / REDIS_URL to local services

# 4. Apply migrations and run
uv run python manage.py migrate
uv run python manage.py runserver
```

> You will also need a running PostgreSQL and Redis instance for full functionality (email tasks require Celery + Redis).

## Environment Variables

Copy `.env.example` and fill in the values.

**Required for production:**
`SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`

**All variables:**

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames |
| `DJANGO_SETTINGS_MODULE` | Settings module (e.g. `config.settings.production`) |
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `REDIS_URL` | Redis connection string |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of allowed frontend origins |
| `FRONTEND_URL` | Base URL of the frontend (used in password reset emails) |
| `EMAIL_HOST` | SMTP host |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_USE_TLS` | `True` / `False` |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password / app password |
| `DEFAULT_FROM_EMAIL` | Sender address for outgoing emails |

## API Overview

Interactive docs (DEBUG mode only):
- Swagger UI: `GET /api/v1/schema/swagger-ui/`
- ReDoc: `GET /api/v1/schema/redoc/`

### Endpoints

#### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register/` | Register a new user |
| `POST` | `/api/v1/auth/token/` | Obtain JWT token pair |
| `POST` | `/api/v1/auth/token/refresh/` | Refresh access token |
| `POST` | `/api/v1/auth/logout/` | Logout (blacklist refresh token) |

#### Users
| Method | Endpoint | Description |
|---|---|---|
| `GET / PATCH` | `/api/v1/users/me/` | Get or update own profile |
| `GET` | `/api/v1/users/me/reviews/` | List own reviews |
| `POST` | `/api/v1/users/me/change-email/` | Change email address |
| `POST` | `/api/v1/users/password/change/` | Change password |
| `POST` | `/api/v1/users/password/reset/` | Request password reset email |
| `POST` | `/api/v1/users/password/reset/confirm/` | Confirm password reset |

#### Books
| Method | Endpoint | Description |
|---|---|---|
| `GET / POST` | `/api/v1/books/` | List or create books |
| `GET` | `/api/v1/books/search/` | Full-text search |
| `GET / PUT / PATCH / DELETE` | `/api/v1/books/<id>/` | Book detail |
| `GET / POST` | `/api/v1/authors/` | List or create authors |
| `GET` | `/api/v1/authors/<id>/` | Author detail |
| `GET / POST` | `/api/v1/tags/` | List or create tags |
| `GET` | `/api/v1/tags/<id>/` | Tag detail |

#### Personal Library
| Method | Endpoint | Description |
|---|---|---|
| `GET / POST` | `/api/v1/userbooks/` | List or add book to library |
| `GET / PATCH / DELETE` | `/api/v1/userbooks/<id>/` | Get, update or remove entry |

Reading statuses: `reading`, `completed`, `dropped`, `plan_to_read`

#### Reviews
| Method | Endpoint | Description |
|---|---|---|
| `GET / POST` | `/api/v1/books/<id>/reviews/` | List or create reviews for a book |
| `GET` | `/api/v1/books/<id>/reviews/search/` | Search within book reviews |
| `GET / PATCH / DELETE` | `/api/v1/books/<id>/reviews/<id>/` | Review detail |

#### Admin
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/admin/users/` | List all users (admin only) |
| `GET / PATCH` | `/api/v1/admin/users/<id>/` | Manage a user (admin only) |

### Example: Register and authenticate

```bash
# Register
POST /api/v1/auth/register/
{
  "email": "user@example.com",
  "password": "securepassword",
  "username": "johndoe"
}

# Obtain tokens
POST /api/v1/auth/token/
{
  "email": "user@example.com",
  "password": "securepassword"
}
# → { "access": "<token>", "refresh": "<token>" }
```

### Example: Add a book and track it

```bash
# Create a book (admin/staff)
POST /api/v1/books/
Authorization: Bearer <access_token>
{
  "title": "The Hobbit",
  "title_en": "The Hobbit",
  "authors": [1],
  "tags": [3, 5],
  "book_type": "book",
  "description": "A fantasy novel by J.R.R. Tolkien."
}
# → { "id": 42, "title": "The Hobbit", ... }

# Add to personal library
POST /api/v1/userbooks/
Authorization: Bearer <access_token>
{
  "book": 42,
  "status": "reading",
  "current_page": 64
}
```

### Example: Write a review

```bash
POST /api/v1/books/42/reviews/
Authorization: Bearer <access_token>
{
  "text": "An absolute classic. Every page is a joy.",
  "rating": 9.5
}
```

## Pagination & Filtering

All list endpoints support pagination:

```
GET /api/v1/books/?page=2
```

Default page size is **20** items. The response envelope:

```json
{
  "count": 150,
  "next": "http://localhost/api/v1/books/?page=3",
  "previous": "http://localhost/api/v1/books/?page=1",
  "results": [...]
}
```

Filtering is available via `django-filter` on supported endpoints (e.g. filter books by tag, author, or type).

## Security

The project implements several security measures:

- **JWT token rotation and blacklisting** — refresh tokens are invalidated on logout and after each rotation
- **Rate limiting** — protects public endpoints from abuse
- **Password hashing** — handled by Django's built-in PBKDF2 hasher
- **CORS protection** — only explicitly allowed origins can make cross-origin requests
- **Admin endpoints restricted** to users with `is_staff=True`
- **Secure password reset** — one-time tokens with expiry, delivered via email
- **Input sanitisation** — user-supplied HTML is sanitised with `bleach`

## Running Tests

```bash
# Run the full test suite with coverage
uv run coverage run -m pytest

# View coverage report in the terminal
uv run coverage report

# Generate HTML report
uv run coverage html
# then open htmlcov/index.html
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure tests pass before submitting a PR:

```bash
uv run coverage run -m pytest
```

## License

This project is licensed under the [MIT License](LICENSE).
