# 📋 Backend API — Технический план разработки

> Проект: Book & Comic Reading Progress Tracker  
> Стек: Django, DRF, PostgreSQL, Redis, JWT, Docker

---

## 🏗 Архитектурные решения и рекомендации

### Django Apps (структура монолита)

```
project/
├── config/           # settings, urls, wsgi
├── apps/
│   ├── users/        # пользователи, авторизация
│   ├── books/        # книги, авторы, теги
│   ├── userbooks/    # UserBook, прогресс
│   ├── reviews/      # рецензии
│   └── common/       # базовые классы, утилиты
├── media/            # локальные изображения
└── logs/
```

### Поиск — рекомендация

**Выбор: `pg_trgm` (trigram similarity) + `unaccent`**

Обоснование:

- Не требует внешних сервисов (Elasticsearch избыточен для малого проекта)
- Поддерживает нечёткий поиск и опечатки
- Встроен в PostgreSQL, включается расширением
- `GIN`-индекс по trigram даёт приемлемую скорость
- `unaccent` устраняет проблемы с диакритикой

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE INDEX books_title_trgm_idx ON books_book USING GIN (title gin_trgm_ops);
CREATE INDEX books_title_en_trgm_idx ON books_book USING GIN (title_en gin_trgm_ops);
```

### Хранение изображений — рекомендация

**Текущий этап:** `django.core.files.storage.FileSystemStorage` + `MEDIA_ROOT`  
**Рекомендуемый путь эволюции:**

1. Сейчас — локально, достаточно для MVP
2. Далее — S3-совместимое хранилище (AWS S3, MinIO, Cloudflare R2) через `django-storages`

Ограничения для обложек:

- Максимальный размер: **5 MB**
- Форматы: `JPEG`, `PNG`, `WEBP`
- Валидация: `Pillow` + кастомный validator

### Кэширование (Redis, cache-aside)

|Что кэшируем|TTL|Инвалидация|
|---|---|---|
|Список книг (paginated)|5 мин|При добавлении/изменении книги|
|Детальная страница книги|10 мин|При изменении книги|
|Средний рейтинг книги|10 мин|При изменении UserBook.rating|
|Публичные рецензии книги|5 мин|При создании/изменении/удалении рецензии|
|Результаты поиска|3 мин|По ключу запроса|

Стратегия: **cache-aside** — читаем из кэша, при промахе — из БД, пишем в кэш.

### Лимиты / Ограничения

|Поле|Лимит|
|---|---|
|`Book.description`|5000 символов|
|`Review.body`|10 000 символов|
|`Book.authors`|до 10 авторов (M2M)|
|Тегов на книгу|до 20|
|Обложка|5 MB, JPEG/PNG/WEBP|
|Payload запроса|10 MB (nginx/django)|

### Нефункциональные решения

|Аспект|Решение|Обоснование|
|---|---|---|
|Rate limiting|DRF Throttling (AnonRateThrottle, UserRateThrottle)|Встроено в DRF, достаточно для малого трафика|
|Brute-force защита|Throttling на `/auth/token/` (5/min anon)|django-axes — избыточно на данном этапе|
|Refresh token rotation|simplejwt `ROTATE_REFRESH_TOKENS=True`|Снижает риск компрометации токена|
|JWT Blacklist|simplejwt `blacklist` app|Нужен для logout и смены пароля|
|CORS|`django-cors-headers`|Обязателен, т.к. frontend отдельно|
|Django Admin|**Да**, нужен|Для управления книгами, пользователями, тегами без API|
|API Versioning|URL-based `/api/v1/`|Просто, явно, стандартно|
|Logging|Python `logging` + RotatingFileHandler|Structured logging в файл + stderr|
|Error handling|DRF exception handler (кастомный)|Единый формат ошибок|
|Pagination|`PageNumberPagination`, default 20|Стандартно, предсказуемо|
|OpenAPI|`drf-spectacular`|Указано в требованиях|
|Индексы БД|Описаны в каждой модели ниже|—|
|Миграции|Django migrations, squash при необходимости|—|

---

## 📦 Ограничения и лимиты моделей

```python
# Сводка лимитов
BOOK_DESCRIPTION_MAX_LEN = 5000
REVIEW_BODY_MAX_LEN = 10_000
BOOK_AUTHORS_MAX = 10
BOOK_TAGS_MAX = 20
COVER_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_COVER_TYPES = ['image/jpeg', 'image/png', 'image/webp']
RATING_MIN = 0
RATING_MAX = 10
```

---

---

# EPICS

---

## EPIC-1: Инфраструктура и базовая конфигурация проекта

---

### US-1.1: Настройка Django проекта и Docker окружения

**Как разработчик**, я хочу иметь воспроизводимое окружение через Docker, чтобы разработка была стандартизирована.

#### Technical Tasks

**TT-1.1.1: Инициализация Django проекта** - готово

- Создать Django проект со структурой apps/
- Настроить `config/settings/` (base.py, local.py, production.py)
- Настроить `django-environ` для `.env`
- Создать базовую структуру приложений: users, books, userbooks, reviews, common

**TT-1.1.2: Docker и docker-compose** - готово

- `Dockerfile` для Django (python:3.12-slim)
- `docker-compose.yml`: django, postgresql, redis
- `.env.example` с документацией всех переменных
- Volume для media и logs
- Health checks для postgres и redis

**TT-1.1.3: Базовая конфигурация Django** - готово

- `INSTALLED_APPS`, `MIDDLEWARE` базовые
- Настроить `DATABASES` (PostgreSQL)
- Настроить `CACHES` (Redis, django-redis)
- Настроить `MEDIA_ROOT`, `MEDIA_URL`
- Настроить `DEFAULT_AUTO_FIELD = BigAutoField`
- Настроить `TIME_ZONE = 'UTC'`

**TT-1.1.4: Зависимости (requirements)** - готово

- `requirements/base.txt`: django, djangorestframework, psycopg2-binary, redis, django-redis, djangorestframework-simplejwt, drf-spectacular, Pillow, django-cors-headers, django-filter
- `requirements/local.txt`: + pytest-django, factory-boy, faker, coverage
- Зафиксировать версии

#### Acceptance Criteria

- [ ] `docker-compose up` поднимает все сервисы без ошибок
- [ ] Django runserver успешно стартует внутри контейнера
- [ ] `.env.example` документирует все обязательные переменные
- [ ] `python manage.py check` проходит без ошибок

#### Definition of Done

- Код в репозитории, docker-compose работает на чистой машине
- README содержит инструкцию запуска

---

### US-1.2: Конфигурация безопасности и cross-cutting concerns

**Как архитектор**, я хочу чтобы базовые механизмы безопасности и сквозные функции были настроены с первого дня.

#### Technical Tasks

**TT-1.2.1: CORS настройка**

- Установить `django-cors-headers`
- `CORS_ALLOWED_ORIGINS` из env
- `CORS_ALLOW_CREDENTIALS = True` (для refresh token в cookie — опция)

**TT-1.2.2: DRF базовая конфигурация**

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'apps.common.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '60/min', 'user': '300/min'},
    'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

**TT-1.2.3: JWT настройка (simplejwt)**

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
}
```

- Добавить `rest_framework_simplejwt.token_blacklist` в INSTALLED_APPS
- Мигрировать blacklist таблицы

**TT-1.2.4: Кастомный exception handler**

```python
# Единый формат: {"error": {"code": "...", "message": "...", "details": {...}}}
def custom_exception_handler(exc, context): ...
```

**TT-1.2.5: Logging конфигурация**

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {'class': 'logging.handlers.RotatingFileHandler', 'filename': 'logs/app.log', 'maxBytes': 10MB, 'backupCount': 5},
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {'handlers': ['file', 'console'], 'level': 'WARNING'},
        'apps': {'handlers': ['file', 'console'], 'level': 'DEBUG'},
    }
}
```

**TT-1.2.6: drf-spectacular настройка**

- `SPECTACULAR_SETTINGS`: title, version, description
- URL: `/api/schema/`, `/api/docs/` (Swagger UI), `/api/redoc/`
- Только для DEBUG или по флагу

**TT-1.2.7: Django Admin настройка**

- Кастомный заголовок (`Book Tracker Admin`)
- Доступ только для `is_staff=True`
- В будущем — ограничить по IP через middleware (опционально)

#### Acceptance Criteria

- [ ] Запрос с невалидным JWT возвращает `401` с единым форматом ошибки
- [ ] `/api/docs/` отображает Swagger UI
- [ ] CORS headers присутствуют в ответах для разрешённых origins
- [ ] Throttling возвращает `429` при превышении лимита
- [ ] Ошибки логируются в файл

#### Definition of Done

- Все cross-cutting concerns работают и протестированы
- Swagger UI доступен и показывает схему

---

### US-1.3: Базовые абстракции и утилиты (common app)

#### Technical Tasks

**TT-1.3.1: Базовые классы моделей**

```python
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: abstract = True
```

**TT-1.3.2: Стандартная пагинация**

```python
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
```

**TT-1.3.3: Утилиты кэширования**

- `cache_key(prefix, *args)` — генерация ключей
- `invalidate_pattern(pattern)` — инвалидация по паттерну (redis `SCAN + DEL`)
- Декоратор `@cached_view(timeout, key_func)`

**TT-1.3.4: Валидаторы изображений**

```python
def validate_cover_image(image):
    # проверка size <= 5MB
    # проверка content_type in ALLOWED_COVER_TYPES
    # проверка через Pillow что файл реально изображение
```

#### Acceptance Criteria

- [ ] Все модели проекта наследуют `TimestampedModel`
- [ ] Пагинация возвращает `count`, `next`, `previous`, `results`
- [ ] Валидатор отклоняет файлы > 5MB и неверных форматов

#### Definition of Done

- Утилиты покрыты unit-тестами

---

---

## EPIC-2: Аутентификация и управление пользователями

---

### US-2.1: Регистрация пользователя

**Как новый пользователь**, я хочу зарегистрироваться через email и пароль, чтобы получить доступ к сервису.

#### Technical Tasks

**TT-2.1.1: Custom User Model**

```python
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)
    role = models.CharField(choices=[('user','user'),('admin','admin')], default='user')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
```

- `UserManager` с `create_user`, `create_superuser`
- `AUTH_USER_MODEL = 'users.User'`
- Миграция 0001

**TT-2.1.2: Registration Endpoint**

- `POST /api/v1/auth/register/`
- Serializer: `email`, `username`, `password`, `password_confirm`
- Валидации:
    - email формат (EmailValidator)
    - password: min 8 символов, не только цифры (Django validators)
    - password == password_confirm
    - уникальность email (handled by model)
- Ответ: `201` + `{id, email, username}`
- **Throttle**: `RegisterThrottle: 10/hour` для anon

**TT-2.1.3: Индексы**

- `email` — unique index (автоматически)
- `username` — unique index (автоматически)

#### Acceptance Criteria

- [ ] `POST /api/v1/auth/register/` с валидными данными возвращает `201`
- [ ] Повторная регистрация с тем же email возвращает `400` с понятным сообщением
- [ ] Слабый пароль возвращает `400` с описанием требований
- [ ] Более 10 запросов/час с одного IP — `429`

#### Definition of Done

- Endpoint реализован и задокументирован в Swagger
- Написаны тесты: успех, дубль email, слабый пароль, throttle

---

### US-2.2: Авторизация (получение JWT токенов)

**Как пользователь**, я хочу войти по email/паролю и получить JWT токены.

#### Technical Tasks

**TT-2.2.1: Login Endpoint**

- `POST /api/v1/auth/token/` — simplejwt `TokenObtainPairView` (кастомизированный)
- Добавить в ответ: `user_id`, `email`, `role`
- Кастомный `TokenObtainPairSerializer`

**TT-2.2.2: Refresh Endpoint**

- `POST /api/v1/auth/token/refresh/` — simplejwt `TokenRefreshView`
- Rotation включён — старый refresh инвалидируется

**TT-2.2.3: Logout Endpoint**

- `POST /api/v1/auth/logout/`
- Принимает `refresh_token`
- Добавляет в blacklist через `RefreshToken(token).blacklist()`
- Требует аутентификации

**TT-2.2.4: Throttle на login**

- Кастомный `LoginRateThrottle`: `5/min` для anon (защита от brute-force)

#### Acceptance Criteria

- [ ] Успешный логин возвращает `access`, `refresh`, `user_id`, `email`, `role`
- [ ] Невалидные credentials — `401`
- [ ] Refresh с невалидным токеном — `401`
- [ ] После logout refresh токен не работает
- [ ] 5 неудачных попыток/мин — `429`

#### Definition of Done

- Все endpoints задокументированы
- Тесты: успех, невалид, logout, rotation

---

### US-2.3: Управление профилем пользователя

**Как пользователь**, я хочу просматривать и редактировать свой профиль.

#### Technical Tasks

**TT-2.3.1: Profile Endpoints**

- `GET /api/v1/users/me/` — получить свой профиль
- `PATCH /api/v1/users/me/` — обновить username

**TT-2.3.2: Email Change**

- `POST /api/v1/users/me/change-email/`
- Поля: `new_email`, `password` (подтверждение)
- Валидация: новый email уникален, пароль верен
- После смены — инвалидировать все refresh токены (blacklist всех токенов пользователя)
    - Реализация: добавить поле `token_version` (int) к User, инкрементировать при смене email/пароля, включить в JWT claims, проверять в custom authentication backend

**TT-2.3.3: Password Reset**

- `POST /api/v1/auth/password/reset/` — запрос сброса (принимает email, генерирует токен, **пока просто возвращает токен в ответе** — т.к. email verification не реализован)
    - Хранить токен сброса: `PasswordResetToken(user, token, created_at, used)`
    - TTL токена: 1 час
- `POST /api/v1/auth/password/reset/confirm/` — подтверждение (токен + новый пароль)
    - После — инкрементировать `token_version`, занести токен сброса как `used`

**TT-2.3.4: Password Change**

- `POST /api/v1/users/me/change-password/`
- Поля: `current_password`, `new_password`, `new_password_confirm`
- После — инкрементировать `token_version`

#### Acceptance Criteria

- [ ] `GET /api/v1/users/me/` возвращает данные текущего пользователя
- [ ] Смена email с неверным паролем — `400`
- [ ] После смены email старые access токены недействительны (token_version mismatch)
- [ ] Password reset token истекает через 1 час
- [ ] Использованный токен сброса не принимается повторно

#### Definition of Done

- Все endpoints реализованы и задокументированы
- Тесты для каждого сценария

---

### US-2.4: Права доступа и роли

#### Technical Tasks

**TT-2.4.1: Permission классы**

```python
class IsOwnerOrAdmin(BasePermission):
    """Владелец объекта или admin"""
    
class IsAdminRole(BasePermission):
    """Пользователь с role='admin'"""
    
class IsOwner(BasePermission):
    """Только владелец"""
```

**TT-2.4.2: Admin user management**

- `GET /api/v1/admin/users/` — список пользователей (IsAdminRole)
- `GET /api/v1/admin/users/{id}/` — детали пользователя
- `PATCH /api/v1/admin/users/{id}/` — изменить role, is_active
- Фильтрация по role, is_active

#### Acceptance Criteria

- [ ] Обычный пользователь не может обращаться к `/api/v1/admin/*` — `403`
- [ ] Admin может деактивировать пользователя
- [ ] Деактивированный пользователь не может получить токен

#### Definition of Done

- Permission классы покрыты тестами
- Admin endpoints реализованы

---

---

## EPIC-3: Книги и комиксы (глобальный каталог)

---

### US-3.1: Модели книг, авторов, тегов

**Как архитектор**, я хочу спроектировать правильную схему данных для книг.

#### Technical Tasks

**TT-3.1.1: Модель Author**

```python
class Author(TimestampedModel):
    name = models.CharField(max_length=255, unique=True)
    # Индекс: name (unique автоматически)
```

**TT-3.1.2: Модель Tag (жанры)**

```python
class Tag(TimestampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
```

**TT-3.1.3: Модель Book**

```python
class Book(TimestampedModel):
    title = models.CharField(max_length=500)
    title_en = models.CharField(max_length=500)
    cover = models.ImageField(upload_to='covers/', null=True, blank=True, validators=[validate_cover_image])
    authors = models.ManyToManyField(Author, related_name='books')  # max 10 через validator
    description = models.TextField(max_length=5000)
    tags = models.ManyToManyField(Tag, related_name='books')  # max 20 через validator
    book_type = models.CharField(choices=[('book','book'),('comic','comic')])
    country = models.CharField(max_length=100)
    pages_total = models.PositiveIntegerField(null=True, blank=True)
    chapters_total = models.PositiveIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=255, blank=True)  # для вариантов изданий
    parent_book = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='editions')
    
    class Meta:
        unique_together = [['title', 'authors']]  # реализовать через validate()
        indexes = [
            GinIndex(fields=['title'], name='book_title_trgm', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['title_en'], name='book_title_en_trgm', opclasses=['gin_trgm_ops']),
            models.Index(fields=['book_type']),
            models.Index(fields=['country']),
        ]
```

**TT-3.1.4: Валидатор кол-ва авторов и тегов**

```python
# В serializer.validate():
if len(authors) > 10: raise ValidationError("Максимум 10 авторов")
if len(tags) > 20: raise ValidationError("Максимум 20 тегов")
```

**TT-3.1.5: Бизнес-валидация**

- Если `book_type='book'` → `pages_total` обязателен
- Если `book_type='comic'` → `chapters_total` обязателен
- В сериализаторе через `validate()`

**TT-3.1.6: Миграции с расширениями PostgreSQL**

```python
# migration:
from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
class Migration(migrations.Migration):
    operations = [TrigramExtension(), UnaccentExtension(), ...]
```

#### Acceptance Criteria

- [ ] Модели созданы, миграции применяются
- [ ] GIN индексы созданы в БД
- [ ] Расширения `pg_trgm` и `unaccent` активированы

#### Definition of Done

- Модели в БД, миграции применены
- `python manage.py check` проходит

---

### US-3.2: CRUD книг (Admin)

**Как администратор**, я хочу управлять глобальным каталогом книг через API.

#### Technical Tasks

**TT-3.2.1: Book CRUD Endpoints**

- `GET /api/v1/books/` — список книг (публичный, с кэшем)
- `POST /api/v1/books/` — создать книгу (IsAdminRole)
- `GET /api/v1/books/{id}/` — детали книги (публичный, с кэшем)
- `PUT/PATCH /api/v1/books/{id}/` — обновить (IsAdminRole)
- `DELETE /api/v1/books/{id}/` — удалить (IsAdminRole, hard delete)

**TT-3.2.2: BookSerializer**

```python
class BookSerializer(serializers.ModelSerializer):
    authors = AuthorSerializer(many=True, read_only=True)
    author_ids = serializers.PrimaryKeyRelatedField(many=True, write_only=True, queryset=Author.objects.all(), source='authors')
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(many=True, write_only=True, queryset=Tag.objects.all(), source='tags')
    average_rating = serializers.FloatField(read_only=True)  # annotated
    ratings_count = serializers.IntegerField(read_only=True)  # annotated
```

**TT-3.2.3: Аннотация среднего рейтинга**

```python
Book.objects.annotate(
    average_rating=Avg('userbooks__rating', filter=Q(userbooks__rating__isnull=False)),
    ratings_count=Count('userbooks__rating', filter=Q(userbooks__rating__isnull=False))
)
```

**TT-3.2.4: Пагинация списка книг**

- Стандартная пагинация, 20/страница

**TT-3.2.5: Author и Tag CRUD (Admin)**

- `GET/POST /api/v1/authors/`
- `GET/PUT/PATCH/DELETE /api/v1/authors/{id}/`
- Аналогично для `/api/v1/tags/`
- Создание — IsAdminRole, чтение — публичное

**TT-3.2.6: Кэширование списка и деталей книги**

- Кэш ключ: `books:list:page:{n}:size:{s}`, TTL 5 мин
- Кэш ключ: `books:detail:{id}`, TTL 10 мин
- Инвалидация при POST/PUT/PATCH/DELETE книги

#### Acceptance Criteria

- [ ] Неавторизованный пользователь может читать список и детали книг
- [ ] Создание/изменение/удаление без роли admin — `403`
- [ ] Книга с `type=book` без `pages_total` — `400`
- [ ] Средний рейтинг корректно вычисляется
- [ ] Список книг возвращается из кэша при повторном запросе

#### Definition of Done

- Все endpoints реализованы, задокументированы
- Unit + integration тесты
- Кэширование работает

---

### US-3.3: Поиск книг

**Как пользователь**, я хочу найти книгу по названию с поддержкой опечаток и фильтрами.

#### Technical Tasks

**TT-3.3.1: Search Endpoint**

- `GET /api/v1/books/search/?q=...&author=...&tag=...&type=...&country=...`

**TT-3.3.2: Trigram Search реализация**

```python
from django.contrib.postgres.search import TrigramSimilarity, TrigramWordSimilarity
from django.db.models.functions import Greatest

queryset = Book.objects.annotate(
    similarity=Greatest(
        TrigramSimilarity('title', query),
        TrigramSimilarity('title_en', query),
    )
).filter(similarity__gte=0.2).order_by('-similarity')
```

**TT-3.3.3: Фильтрация через django-filter**

```python
class BookFilter(FilterSet):
    author = filters.ModelMultipleChoiceFilter(field_name='authors', queryset=Author.objects.all())
    tag = filters.ModelMultipleChoiceFilter(field_name='tags', queryset=Tag.objects.all())
    book_type = filters.ChoiceFilter(choices=BOOK_TYPE_CHOICES)
    country = filters.CharFilter(lookup_expr='icontains')
```

**TT-3.3.4: Кэш поиска**

- Ключ: `search:{hash(q+filters)}`, TTL 3 мин
- Инвалидация: при изменении любой книги (или TTL-based, приемлемо)

#### Acceptance Criteria

- [ ] `GET /books/search/?q=гарри` находит "Гарри Поттер" и варианты с опечатками
- [ ] Фильтр по автору, тегу, типу, стране работает независимо и в комбинации
- [ ] Пустой `q` без фильтров возвращает все книги (с пагинацией)
- [ ] Результаты кэшируются

#### Definition of Done

- Поиск работает с опечатками
- Тесты на поиск и фильтрацию

---

---

## EPIC-4: UserBook — пользовательская связь с книгой

---

### US-4.1: CRUD UserBook

**Как пользователь**, я хочу добавлять книги в свою библиотеку, указывать статус и прогресс.

#### Technical Tasks

**TT-4.1.1: Модель UserBook**

```python
class UserBook(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='userbooks')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='userbooks')
    status = models.CharField(choices=STATUS_CHOICES)  # reading|completed|dropped|plan_to_read
    current_page = models.PositiveIntegerField(null=True, blank=True)
    current_chapter = models.PositiveIntegerField(null=True, blank=True)
    is_masterpiece = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True,
                                  validators=[MinValueValidator(0), MaxValueValidator(10)])
    
    class Meta:
        unique_together = [['user', 'book']]
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['book']),
        ]
```

**TT-4.1.2: Бизнес-валидации**

- `is_masterpiece=True` только если `status='completed'`
- `current_page` только для `book_type='book'`
- `current_chapter` только для `book_type='comic'`
- `current_page <= book.pages_total` (если задано)
- `rating` разрешён при любом статусе (но логично при completed — оставить на усмотрение)

**TT-4.1.3: UserBook Endpoints**

- `GET /api/v1/userbooks/` — список UserBook текущего пользователя (с пагинацией)
- `POST /api/v1/userbooks/` — добавить книгу (создать связь)
- `GET /api/v1/userbooks/{id}/` — детали
- `PATCH /api/v1/userbooks/{id}/` — обновить статус/прогресс/рейтинг
- `DELETE /api/v1/userbooks/{id}/` — удалить связь (hard delete)

**TT-4.1.4: Права доступа**

- Пользователь видит только свои UserBook
- Admin видит все (через `/api/v1/admin/userbooks/`)

**TT-4.1.5: Фильтрация UserBook**

- По status: `?status=reading`
- По book_type: `?type=comic`

**TT-4.1.6: Обновление кэша рейтинга при изменении**

- При сохранении/удалении UserBook с рейтингом — инвалидировать `books:detail:{book_id}` и `books:rating:{book_id}`

#### Acceptance Criteria

- [ ] Нельзя создать две UserBook для одной книги — `400`
- [ ] `is_masterpiece=True` при `status=reading` — `400`
- [ ] `current_page > pages_total` — `400`
- [ ] Удаление UserBook удаляет связь, но не книгу
- [ ] Средний рейтинг книги обновляется при изменении рейтинга

#### Definition of Done

- Все endpoints реализованы и задокументированы
- Тесты бизнес-валидаций

---

---

## EPIC-5: Рецензии

---

### US-5.1: CRUD рецензий

**Как пользователь**, я хочу писать рецензии на книги и управлять их видимостью.

#### Technical Tasks

**TT-5.1.1: Модель Review**

```python
class Review(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    body = models.TextField(max_length=10_000)
    is_public = models.BooleanField(default=True)
    
    class Meta:
        unique_together = [['user', 'book']]
        indexes = [
            models.Index(fields=['book', 'is_public']),
            models.Index(fields=['user']),
        ]
```

**TT-5.1.2: Review Endpoints**

- `GET /api/v1/books/{book_id}/reviews/` — публичные рецензии книги (публичный доступ, пагинация)
- `POST /api/v1/books/{book_id}/reviews/` — создать рецензию (IsAuthenticated)
- `GET /api/v1/books/{book_id}/reviews/{id}/` — детали (публичная или своя)
- `PATCH /api/v1/books/{book_id}/reviews/{id}/` — изменить (IsOwnerOrAdmin)
- `DELETE /api/v1/books/{book_id}/reviews/{id}/` — удалить (IsOwnerOrAdmin)

**TT-5.1.3: Видимость рецензий**

- `GET reviews/` — фильтровать `is_public=True` для чужих рецензий
- Авторизованный пользователь видит свои рецензии независимо от `is_public`
- Логика в QuerySet: `Q(is_public=True) | Q(user=request.user)`

**TT-5.1.4: Кэш публичных рецензий**

- Ключ: `reviews:book:{book_id}:page:{n}`, TTL 5 мин
- Инвалидация при CUD операциях с рецензиями книги

**TT-5.1.5: Собственные рецензии пользователя**

- `GET /api/v1/users/me/reviews/` — все свои рецензии (в т.ч. приватные)

#### Acceptance Criteria

- [ ] Анонимный пользователь видит только публичные рецензии
- [ ] Нельзя создать вторую рецензию на ту же книгу — `400`
- [ ] Рецензия > 10000 символов — `400`
- [ ] Владелец может скрыть рецензию (`is_public=False`)
- [ ] Скрытая рецензия не видна другим пользователям

#### Definition of Done

- Все endpoints реализованы и задокументированы
- Тесты: видимость, ограничения, CRUD

---

---

## EPIC-6: Django Admin

---

### US-6.1: Admin панель для управления каталогом

**Как администратор**, я хочу управлять книгами, пользователями и тегами через Django Admin.

#### Technical Tasks

**TT-6.1.1: UserAdmin**

```python
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active']
    search_fields = ['email', 'username']
    actions = ['deactivate_users']
```

**TT-6.1.2: BookAdmin**

```python
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'book_type', 'country', 'created_at']
    list_filter = ['book_type', 'country', 'tags']
    search_fields = ['title', 'title_en']
    filter_horizontal = ['authors', 'tags']
    readonly_fields = ['created_at', 'updated_at']
```

**TT-6.1.3: ReviewAdmin**

```python
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'is_public', 'created_at']
    list_filter = ['is_public']
    actions = ['make_private', 'make_public']
```

**TT-6.1.4: AuthorAdmin, TagAdmin** — базовые

#### Acceptance Criteria

- [ ] Admin доступен только staff пользователям
- [ ] Все модели зарегистрированы в admin
- [ ] Поиск по книгам, пользователям работает

#### Definition of Done

- Admin настроен для всех ключевых моделей

---

---

## EPIC-7: Нефункциональные требования и финализация

---

### US-7.1: Индексы БД и оптимизация запросов

#### Technical Tasks

**TT-7.1.1: Аудит N+1 запросов**

- Использовать `select_related`, `prefetch_related` во всех ViewSet
- Проверить через `django-debug-toolbar` (local) или логирование SQL

**TT-7.1.2: Индексы (сводный список)**

- `User.email` — unique (auto)
- `Book` — GIN trgm на title, title_en; index на book_type, country
- `UserBook` — composite (user, status), index on book
- `Review` — composite (book, is_public), index on user
- `PasswordResetToken` — index on (user, used, created_at)

**TT-7.1.3: Explain Analyze на ключевых запросах**

- Поиск книг
- Список UserBook пользователя
- Публичные рецензии книги

#### Acceptance Criteria

- [ ] Нет N+1 запросов на основных endpoints (проверено через SQL логи)
- [ ] EXPLAIN ANALYZE показывает использование индексов на поиске

#### Definition of Done

- Все критичные запросы оптимизированы

---

### US-7.2: Тестирование

#### Technical Tasks

**TT-7.2.1: Тестовая инфраструктура**

- pytest-django, factory-boy, faker
- Фабрики для: User, Book, Author, Tag, UserBook, Review
- `conftest.py`: фикстуры user, admin_user, authenticated_client

**TT-7.2.2: Покрытие**

- Unit тесты: serializers, validators, permissions, utils
- Integration тесты: все endpoints (happy path + error cases)
- Цель: 80%+ покрытие

**TT-7.2.3: Тест кэширования**

- Проверить что повторный запрос идёт из кэша (mock Redis или django.test.TestCase с cache.clear())

#### Acceptance Criteria

- [ ] `pytest` проходит без ошибок
- [ ] Coverage >= 80%

#### Definition of Done

- CI может быть добавлен позже; тесты запускаются локально через `pytest`

---

### US-7.3: OpenAPI документация

#### Technical Tasks

**TT-7.3.1: Аннотации drf-spectacular**

- `@extend_schema` для нестандартных endpoints
- Описание `responses`, `request`, `parameters` там где auto-схема неточна
- `@extend_schema_view` для ViewSet

**TT-7.3.2: Проверка схемы**

- `python manage.py spectacular --validate` — без ошибок
- Swagger UI отображает все endpoints корректно

#### Acceptance Criteria

- [ ] Все endpoints видны в Swagger UI
- [ ] Request/response схемы корректны
- [ ] Схема валидна по OpenAPI 3.0

#### Definition of Done

- Swagger UI полностью покрывает API

---

---

# 🔍 Что стоит уточнить

1. **Email verification**: указано "пока не реализуется" — когда планируется? Это повлияет на флоу регистрации и сброса пароля.
2. **Варианты изданий**: как клиент будет отображать связь `parent_book` → `editions`? Нужен ли специальный endpoint для получения всех изданий книги?
3. **Публичность профиля**: пользователи могут смотреть библиотеки других пользователей? Сейчас предполагается нет.
4. **Удаление аккаунта**: не упомянуто — нужно ли?
5. **Токен сброса пароля**: пока возвращается в ответе API. Как только появится email — схема изменится. Заложить абстракцию.
6. **Статистика пользователя**: нужна ли страница типа "прочитано X книг, X комиксов"? Легко добавить позже.

---

# ⚠️ Потенциально проблемные решения

1. **`unique_together = [['title', 'authors']]`** — M2M уникальность нельзя задать через `unique_together`. Нужна валидация в `clean()` / сериализаторе. Это не автоматически на уровне БД.
2. **Инвалидация кэша по паттерну** (`SCAN + DEL`) — на больших БД Redis может быть медленной. Для малого трафика приемлемо, но стоит знать об ограничении.
3. **`token_version` в JWT** — требует кастомного authentication backend. Добавляет сложность. Альтернатива: принять что access токен живёт 30 мин и после смены пароля/email просто ждать истечения. Для малого проекта — допустимо.
4. **Локальное хранение изображений** — при масштабировании (даже незначительном) или деплое на несколько инстансов — проблема. Стоит сразу заложить абстракцию через `DEFAULT_FILE_STORAGE`.
5. **Hard delete везде** — удаление UserBook удалит рейтинг и повлияет на средний рейтинг книги. Бизнес-логика принята, но стоит задокументировать явно.

---

# ✂️ Что можно упростить

1. **`token_version`** — на данном этапе избыточно. Достаточно blacklist refresh токена при смене пароля/email + короткий access TTL (15-30 мин).
2. **Отдельный `/search/` endpoint** — можно встроить в `GET /books/?q=...` через django-filter + trigram. Меньше endpoints, проще документирование.
3. **`parent_book` / `editions`** — если реального сценария для UI нет — пока оставить поле, но не делать отдельного endpoint. Добавить по требованию.
4. **Admin API** (`/api/v1/admin/*`) — для большинства операций Django Admin достаточен. Отдельные API для admin нужны только если admin будет работать через тот же SPA frontend.
5. **Rate limiting**: DRF Throttling достаточно для малого трафика. `django-axes` или nginx rate limiting — добавить при необходимости.

---

# 📊 Сводная таблица Epics и оценка

|Epic|Stories|Примерная трудоёмкость|
|---|---|---|
|EPIC-1: Инфраструктура|US-1.1, 1.2, 1.3|3-4 дня|
|EPIC-2: Auth & Users|US-2.1, 2.2, 2.3, 2.4|4-5 дней|
|EPIC-3: Книги|US-3.1, 3.2, 3.3|4-5 дней|
|EPIC-4: UserBook|US-4.1|2-3 дня|
|EPIC-5: Рецензии|US-5.1|2 дня|
|EPIC-6: Admin|US-6.1|1 день|
|EPIC-7: NFR & QA|US-7.1, 7.2, 7.3|3-4 дня|
|**Итого**||**~20-25 дней**|

---

_Документ готов для переноса в Jira: каждый US — это Epic Story, TT — Tasks, Acceptance Criteria и DoD — поля в карточке._