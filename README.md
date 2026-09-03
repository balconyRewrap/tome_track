# TomeTrack

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-6-green)
![DRF](https://img.shields.io/badge/DRF-3.16-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Redis](https://img.shields.io/badge/Redis-7-red)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![License](https://img.shields.io/badge/License-MIT-green)

**TomeTrack** is a production-deployed REST API for a personal book-tracking platform.

The backend handles authentication, personal libraries, reading progress, reviews, full-text book search, caching, asynchronous jobs, rate limiting, and administrative operations. It is built around a modular Django architecture and runs as a containerized production stack behind Nginx and Gunicorn.

**Live application:** https://books.tometrack.de/

---

## Highlights

* Production deployment with **Docker, Nginx, Gunicorn and HTTPS**
* REST API built with **Django REST Framework**
* **PostgreSQL** as the primary database
* **Redis** for caching and Celery message brokering
* Background processing with **Celery**
* Scheduled jobs with **Celery Beat**
* JWT authentication with **refresh-token rotation and blacklisting**
* Role-based access control for administrative endpoints
* Full-text book search
* Redis-backed caching for frequently accessed resources
* API rate limiting for authenticated and anonymous clients
* Token-based asynchronous password recovery
* Consistent API error responses through a custom exception handler
* OpenAPI documentation generated with **drf-spectacular**
* Automated test suite with **pytest and coverage**
* Code quality enforcement with **Ruff**
* Separate development and production settings
* CORS configuration and input sanitization
* Automatic TLS certificate management with **Let's Encrypt / Certbot**

---

## Tech Stack

| Area                 | Technology                  |
| -------------------- | --------------------------- |
| Language             | Python 3.12                 |
| Backend              | Django 6                    |
| REST API             | Django REST Framework 3.16  |
| Database             | PostgreSQL 16               |
| Cache                | Redis 7                     |
| Background jobs      | Celery 5                    |
| Scheduler            | django-celery-beat          |
| Authentication       | Simple JWT                  |
| Filtering            | django-filter               |
| API schema           | drf-spectacular / OpenAPI 3 |
| Application server   | Gunicorn                    |
| Reverse proxy        | Nginx                       |
| TLS                  | Let's Encrypt / Certbot     |
| Containers           | Docker / Docker Compose     |
| Package management   | uv                          |
| Testing              | pytest / coverage           |
| Linting & formatting | Ruff                        |

---

## Architecture

TomeTrack is structured as a modular Django application. Each domain is isolated into a dedicated app while shared infrastructure and reusable behavior live in `common`.

```text
                        ┌─────────────────┐
                        │     Client      │
                        └────────┬────────┘
                                 │ HTTPS
                                 ▼
                        ┌─────────────────┐
                        │      Nginx      │
                        │ TLS / Static    │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Gunicorn     │
                        └────────┬────────┘
                                 │
                                 ▼
                      ┌──────────────────────┐
                      │   Django REST API    │
                      └───────┬──────┬───────┘
                              │      │
                 ┌────────────┘      └────────────┐
                 ▼                                ▼
        ┌─────────────────┐              ┌─────────────────┐
        │   PostgreSQL    │              │      Redis      │
        │ Primary storage │              │ Cache / Broker  │
        └─────────────────┘              └────────┬────────┘
                                                  │
                                      ┌───────────┴───────────┐
                                      ▼                       ▼
                              ┌───────────────┐       ┌───────────────┐
                              │ Celery Worker │       │  Celery Beat  │
                              │  Async tasks  │       │   Scheduler   │
                              └───────────────┘       └───────────────┘
```

### Domain modules

```text
apps/
├── books/          Books, authors, tags and search
├── reviews/        User reviews
├── userbooks/      Personal libraries and reading progress
├── users/          Authentication, profiles and administration
└── common/         Shared infrastructure and utilities
```

---

## Key Design Decisions

### Modular domain structure

Instead of keeping all application logic in a single Django app, the backend is divided by domain:

* `users`
* `books`
* `userbooks`
* `reviews`
* `common`

This keeps models, serializers, views and domain-specific behavior separated as the application grows.

### Stateless JWT authentication

Authentication is based on short-lived JWT access tokens and refresh tokens.

Refresh-token rotation is enabled, and previously issued refresh tokens are blacklisted after rotation or logout.

This allows the API itself to remain stateless while still providing explicit session invalidation.

### Redis caching

Frequently requested resources can be served from Redis instead of repeatedly querying PostgreSQL.

Caching is isolated behind shared helpers so cache behavior does not need to be duplicated across individual API views.

### Asynchronous work

Operations that should not block HTTP requests are delegated to Celery workers.

For example:

```text
Password reset request
        │
        ▼
Django creates reset token
        │
        ▼
Task is sent to Redis
        │
        ▼
Celery worker sends email
```

Periodic tasks are managed separately by Celery Beat using a database-backed scheduler.

### Unified API errors

A custom DRF exception handler normalizes application errors into a predictable JSON response format instead of exposing different error structures depending on their source.

### Environment-specific configuration

Django settings are separated into:

```text
config/settings/
├── base.py
├── local.py
└── production.py
```

Development behavior therefore stays isolated from production security and deployment configuration.

---

## Features

### Authentication & Accounts

* User registration
* JWT login
* Access-token refresh
* Refresh-token rotation
* Token blacklisting
* Logout
* Profile management
* Email change
* Password change
* Password reset by email
* Administrative user management

### Books

* Create, read, update and delete books
* Multiple authors per book
* Tags and categories
* Book and comic types
* Cover image uploads
* Full-text search
* Filtering by supported fields

### Personal Library

Users can maintain their own relationship with every book independently from the global book record.

Tracked information includes:

* Reading status
* Current page
* Current chapter
* Personal rating
* Re-read count
* Masterpiece flag

Available statuses:

```text
reading
completed
dropped
plan_to_read
```

### Reviews

* Create reviews for books
* Update and delete own reviews
* Search reviews
* Browse reviews for a book
* Retrieve all reviews written by the current user

---

## Data Model

The central distinction in TomeTrack is between a global `Book` and the user's personal relationship with that book represented by `UserBook`.

```text
                         ┌──────────────┐
                         │     User     │
                         └──────┬───────┘
                                │
                     ┌──────────┴──────────┐
                     │                     │
                     ▼                     ▼
              ┌────────────┐         ┌────────────┐
              │  UserBook  │         │   Review   │
              └─────┬──────┘         └─────┬──────┘
                    │                      │
                    └──────────┬───────────┘
                               ▼
                         ┌────────────┐
                         │    Book    │
                         └─────┬──────┘
                               │
                     ┌─────────┴─────────┐
                     ▼                   ▼
               ┌──────────┐        ┌──────────┐
               │  Author  │        │   Tag    │
               └──────────┘        └──────────┘
```

| Model                | Responsibility                                               |
| -------------------- | ------------------------------------------------------------ |
| `User`               | Custom account model, roles and authentication-related state |
| `Book`               | Shared bibliographic entry                                   |
| `Author`             | Book author                                                  |
| `Tag`                | Genre or category                                            |
| `UserBook`           | User-specific reading state and progress                     |
| `Review`             | User-created review and rating                               |
| `PasswordResetToken` | Expiring one-time password-reset token                       |

---

## Security

TomeTrack applies security controls at several layers.

### Authentication

* JWT access and refresh tokens
* Refresh-token rotation
* Refresh-token blacklisting
* Explicit logout invalidation

### Authorization

* Authenticated-user permissions
* Object ownership checks
* Administrative routes restricted to staff users

### Request protection

* Anonymous rate limit: `60 requests/minute`
* Authenticated rate limit: `300 requests/minute`
* Explicit CORS allowlist
* Input validation through DRF serializers
* HTML sanitization with `bleach`

### Credentials

Sensitive configuration is supplied through environment variables rather than committed to source control.

### Passwords

Password storage uses Django's password hashing infrastructure.

Password-reset tokens are:

* One-time use
* Expiring
* Delivered asynchronously by email

### Production transport

Production traffic is served through HTTPS.

Nginx terminates TLS, while Certbot manages Let's Encrypt certificate issuance and renewal.

---

## API Overview

Base path:

```text
/api/v1/
```

### Authentication

| Method | Endpoint               | Description                        |
| ------ | ---------------------- | ---------------------------------- |
| `POST` | `/auth/register/`      | Register                           |
| `POST` | `/auth/token/`         | Obtain JWT pair                    |
| `POST` | `/auth/token/refresh/` | Refresh access token               |
| `POST` | `/auth/logout/`        | Logout and blacklist refresh token |

### Current User

| Method        | Endpoint                         | Description                |
| ------------- | -------------------------------- | -------------------------- |
| `GET / PATCH` | `/users/me/`                     | Retrieve or update profile |
| `GET`         | `/users/me/reviews/`             | Current user's reviews     |
| `POST`        | `/users/me/change-email/`        | Change email               |
| `POST`        | `/users/password/change/`        | Change password            |
| `POST`        | `/users/password/reset/`         | Request password reset     |
| `POST`        | `/users/password/reset/confirm/` | Confirm password reset     |

### Books

| Method                       | Endpoint         | Description          |
| ---------------------------- | ---------------- | -------------------- |
| `GET / POST`                 | `/books/`        | List or create books |
| `GET`                        | `/books/search/` | Search books         |
| `GET / PUT / PATCH / DELETE` | `/books/<id>/`   | Book operations      |
| `GET / POST`                 | `/authors/`      | Authors              |
| `GET`                        | `/authors/<id>/` | Author detail        |
| `GET / POST`                 | `/tags/`         | Tags                 |
| `GET`                        | `/tags/<id>/`    | Tag detail           |

### Personal Library

| Method                 | Endpoint           | Description                |
| ---------------------- | ------------------ | -------------------------- |
| `GET / POST`           | `/userbooks/`      | List library or add a book |
| `GET / PATCH / DELETE` | `/userbooks/<id>/` | Manage library entry       |

### Reviews

| Method                 | Endpoint                      | Description            |
| ---------------------- | ----------------------------- | ---------------------- |
| `GET / POST`           | `/books/<id>/reviews/`        | List or create reviews |
| `GET`                  | `/books/<id>/reviews/search/` | Search reviews         |
| `GET / PATCH / DELETE` | `/books/<id>/reviews/<id>/`   | Manage review          |

### Administration

| Method        | Endpoint             | Description |
| ------------- | -------------------- | ----------- |
| `GET`         | `/admin/users/`      | List users  |
| `GET / PATCH` | `/admin/users/<id>/` | Manage user |

---

## API Documentation

The OpenAPI schema is generated automatically with `drf-spectacular`.

When documentation endpoints are enabled in the current environment:

```text
/api/v1/schema/swagger-ui/
/api/v1/schema/redoc/
```

The API schema therefore stays synchronized with the actual serializers and endpoints instead of being maintained manually.

---

## Example Workflow

### 1. Register

```http
POST /api/v1/auth/register/
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "username": "johndoe"
}
```

### 2. Authenticate

```http
POST /api/v1/auth/token/
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

Response:

```json
{
  "access": "<access_token>",
  "refresh": "<refresh_token>"
}
```

### 3. Add a book to the personal library

```http
POST /api/v1/userbooks/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "book": 42,
  "status": "reading",
  "current_page": 64
}
```

### 4. Write a review

```http
POST /api/v1/books/42/reviews/
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "text": "An absolute classic. Every page is a joy.",
  "rating": 9.5
}
```

---

## Pagination & Filtering

List endpoints use paginated responses.

Example:

```http
GET /api/v1/books/?page=2
```

Default page size:

```text
20
```

Response:

```json
{
  "count": 150,
  "next": "http://localhost/api/v1/books/?page=3",
  "previous": "http://localhost/api/v1/books/?page=1",
  "results": []
}
```

Supported resources can also be filtered through `django-filter`.

Examples include filtering books by:

* Author
* Tag
* Book type

---

## Project Structure

```text
tome_track/
├── apps/
│   ├── books/
│   │   └── # Books, authors, tags, search
│   │
│   ├── reviews/
│   │   └── # Reviews and review search
│   │
│   ├── userbooks/
│   │   └── # Personal libraries and reading progress
│   │
│   ├── users/
│   │   └── # Authentication, profiles and administration
│   │
│   └── common/
│       └── # Shared models, mixins, exceptions and utilities
│
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── celery.py
│   └── urls.py
│
├── nginx/
│   └── nginx.conf
│
├── templates/
│   └── emails/
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── manage.py
```

---

# Running the Project

## Prerequisites

For the Docker setup:

* Docker
* Docker Compose

For development without Docker:

* Python 3.12
* uv
* PostgreSQL
* Redis

---

## Docker

Clone the repository:

```bash
git clone https://github.com/balconyRewrap/tome_track.git
cd tome_track
```

Create the production environment:

```bash
cp .env.example .env.production
```

Fill in the required environment variables, then start the stack:

```bash
docker-compose up --build
```

The complete deployment starts:

```text
django
nginx
certbot
db
redis
celery_worker
celery_beat
```

For a detached production deployment:

```bash
docker-compose up --build -d
```

---

## Local Development

Clone the project:

```bash
git clone https://github.com/balconyRewrap/tome_track.git
cd tome_track
```

Install dependencies:

```bash
uv sync
```

Create local configuration:

```bash
cp .env.example .env
```

Set:

```text
DEBUG=True
```

and configure local PostgreSQL and Redis connections.

Apply migrations:

```bash
uv run python manage.py migrate
```

Start Django:

```bash
uv run python manage.py runserver
```

A running Celery worker is required for asynchronous tasks such as password-reset emails.

---

# Production Deployment

The production stack is fully containerized.

```text
Internet
   │
   │ :80 / :443
   ▼
 Nginx
   │
   ▼
Gunicorn
   │
   ▼
Django
 ├──────── PostgreSQL
 └──────── Redis ─────── Celery
                       └ Celery Beat
```

Nginx is responsible for:

* Reverse proxying
* TLS termination
* Static files
* HTTP → HTTPS redirection

Certbot is responsible for:

* Initial certificate issuance
* Automatic certificate renewal

To initialize a deployment:

```bash
cp .env.example .env.production
```

Configure at least:

```dotenv
DOMAIN_NAME=api.your-domain.com
LETSENCRYPT_EMAIL=admin@your-domain.com
LETSENCRYPT_STAGING=1
```

Start the stack:

```bash
docker-compose up --build -d
```

Using the Let's Encrypt staging environment for the first deployment avoids production rate limits during configuration testing.

Once certificate issuance works correctly, switch:

```dotenv
LETSENCRYPT_STAGING=0
```

and redeploy.

After a valid certificate is available, Nginx serves HTTPS traffic and redirects HTTP requests to port `443`.

---

# Environment Variables

Create the appropriate environment file from:

```text
.env.example
```

Important production values include:

```text
SECRET_KEY
DATABASE_URL
REDIS_URL
EMAIL_HOST
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
```

| Variable                 | Purpose                                   |
| ------------------------ | ----------------------------------------- |
| `SECRET_KEY`             | Django cryptographic secret               |
| `DEBUG`                  | Development / production mode             |
| `ALLOWED_HOSTS`          | Allowed HTTP hostnames                    |
| `DJANGO_SETTINGS_MODULE` | Active Django settings module             |
| `DATABASE_URL`           | PostgreSQL connection                     |
| `POSTGRES_DB`            | PostgreSQL database                       |
| `POSTGRES_USER`          | PostgreSQL user                           |
| `POSTGRES_PASSWORD`      | PostgreSQL password                       |
| `REDIS_URL`              | Redis connection                          |
| `CORS_ALLOWED_ORIGINS`   | Permitted frontend origins                |
| `FRONTEND_URL`           | Frontend base URL                         |
| `EMAIL_HOST`             | SMTP server                               |
| `EMAIL_PORT`             | SMTP port                                 |
| `EMAIL_USE_TLS`          | SMTP TLS setting                          |
| `EMAIL_HOST_USER`        | SMTP username                             |
| `EMAIL_HOST_PASSWORD`    | SMTP password                             |
| `DEFAULT_FROM_EMAIL`     | Default sender                            |
| `SERVER_EMAIL`           | Django server-error sender                |
| `ADMIN_ERROR_EMAILS`     | Recipients for server error notifications |
| `DOMAIN_NAME`            | Production domain                         |
| `LETSENCRYPT_EMAIL`      | Let's Encrypt registration email          |
| `LETSENCRYPT_STAGING`    | Use Let's Encrypt staging environment     |

---

# Testing

Run the complete test suite with coverage:

```bash
uv run coverage run -m pytest
```

Display coverage:

```bash
uv run coverage report
```

Generate an HTML report:

```bash
uv run coverage html
```

The generated report is available under:

```text
htmlcov/index.html
```

---

# Code Quality

Ruff is used for linting and formatting.

Run checks:

```bash
uv run ruff check .
```

Run the formatter:

```bash
uv run ruff format .
```

---

# Contributing

Contributions are welcome.

For significant changes, please open an issue before submitting a pull request so the proposed behavior can be discussed first.

Before opening a PR, make sure the test suite passes:

```bash
uv run coverage run -m pytest
```

and verify code quality:

```bash
uv run ruff check .
```

---

# License

TomeTrack is released under the [MIT License](LICENSE).
