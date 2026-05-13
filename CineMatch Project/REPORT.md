# CineMatch — Comprehensive Technical Report

> Generated from a complete read of every source file in the project.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Complete File Structure](#2-complete-file-structure)
3. [Database](#3-database)
4. [Flask Web App](#4-flask-web-app)
5. [Kafka](#5-kafka)
6. [ML Service](#6-ml-service)
7. [Full Request Lifecycles](#7-full-request-lifecycles)
8. [Architecture — How the Two Sides Communicate](#8-architecture--how-the-two-sides-communicate)
9. [How to Run](#9-how-to-run)
10. [What Was Learned](#10-what-was-learned)

---

## 1. Project Overview

### What CineMatch Is

CineMatch is a full-stack web application that lets users discover, rate, and track movies — and then receive personalised film recommendations driven by a machine-learning engine.

The problem it solves: most people don't know what to watch next. CineMatch collects their ratings (1–5 stars per movie) and uses **collaborative filtering** — finding users with similar tastes — to predict which unseen films they will enjoy most.

### Why This Architecture

CineMatch is built in two fully independent halves:

| Half | Technology | Responsibility |
|---|---|---|
| Web app | Flask (Python) | Serve pages, handle auth, record ratings, read recommendations |
| ML service | Python standalone | Listen for events, rebuild recommendations in background |

The two halves **never import each other**. They share data through two channels only:
- A **SQLite database** (Flask writes ratings; ML reads ratings and writes recommendations)
- A **Kafka message broker** (Flask publishes events; ML consumes them)

This separation — called *event-driven architecture* — means:
- The ML service can be stopped, restarted, or upgraded with zero impact on the web app.
- The web app never blocks waiting for slow ML computation.
- Each side can be developed and tested in isolation.

### Tech Stack Summary

| Layer | Tool | Version |
|---|---|---|
| Web framework | Flask | 3.1.0 |
| ORM | Flask-SQLAlchemy | 3.1.1 |
| DB migrations | Flask-Migrate (Alembic) | 4.0.7 |
| Authentication | Flask-Login + Flask-Bcrypt | 0.6.3 / 1.0.1 |
| HTTP server | Werkzeug dev server | 3.1.3 |
| Message broker | Apache Kafka (Confluent Docker) | 7.4.0 |
| Kafka Python client | kafka-python-ng | 2.2.3 |
| ML — linear algebra | NumPy | 1.26.4 |
| ML — SVD | SciPy | 1.13.1 |
| Database | SQLite | (built-in) |
| Templates | Jinja2 (via Flask) | — |
| CSS framework | Bootstrap | 5.3.3 (CDN) |

---

## 2. Complete File Structure

```
CineMatch Project/
├── config.py                  # App configuration (secret key, DB URL, Kafka URL)
├── run.py                     # Entry point — calls create_app() and runs dev server
├── seed.py                    # Idempotent data seeder (20 movies, 8+ users, ratings)
├── docker-compose.yml         # Zookeeper + Kafka containers
├── requirements.txt           # Python package pins
├── test_ml.py                 # ML unit tests (no Flask, no Kafka needed)
├── test_live.py               # End-to-end integration test (Flask + Kafka + ML)
├── REPORT.md                  # This file
│
├── instance/
│   └── cinematch.db           # SQLite database (created at first migration)
│
├── migrations/                # Alembic migration history
│   ├── env.py                 # Alembic environment — connects to Flask app
│   ├── alembic.ini            # Alembic configuration
│   └── versions/
│       └── 0da335019721_initial_schema.py   # The one migration (all 6 tables)
│
├── app/                       # Flask application package
│   ├── __init__.py            # Application factory + extension init
│   ├── models.py              # All 6 SQLAlchemy models
│   ├── utils.py               # log_event() — DB write + Kafka produce
│   ├── kafka_producer.py      # Lazy, fail-safe KafkaProducer wrapper
│   └── routes/
│       ├── __init__.py        # Empty — makes routes/ a package
│       ├── auth.py            # Blueprint: /auth/register, /auth/login, /auth/logout
│       ├── movies.py          # Blueprint: /movies/* catalog, search, detail, rate, watchlist
│       └── dashboard.py       # Blueprint: /dashboard/ index, profile, watchlist remove
│
├── app/templates/
│   ├── base.html              # Master layout — navbar, flash messages, footer
│   ├── auth/
│   │   ├── login.html         # Login form
│   │   └── register.html      # Registration form
│   ├── movies/
│   │   ├── catalog.html       # Paginated grid + genre filter + star ratings
│   │   ├── detail.html        # Single movie — star widget, watchlist, similar films
│   │   └── search.html        # Search results grid
│   └── dashboard/
│       ├── index.html         # Recommendations + recently rated + watchlist
│       └── profile.html       # Full rating history + stats
│
└── ml_service/                # Completely independent ML package
    ├── __init__.py            # Empty — makes ml_service/ a package
    ├── db_utils.py            # Raw SQLAlchemy access (no Flask context)
    ├── recommender.py         # SVD collaborative filter + fallback
    └── consumer.py            # Kafka consumer loop — entry point for ML service
```

### Dependency Map (what imports what)

```
run.py
  └── app  (__init__.py → create_app)

app/__init__.py
  ├── flask, flask_sqlalchemy, flask_migrate, flask_login, flask_bcrypt
  ├── app.models  (inside app context)
  ├── app.routes.auth
  ├── app.routes.movies
  └── app.routes.dashboard

app/routes/auth.py
  ├── flask, flask_login
  ├── app  (db, bcrypt)
  └── app.models  (User)

app/routes/movies.py
  ├── flask, flask_login
  ├── app  (db)
  ├── app.models  (Movie, Rating, Watchlist)
  └── app.utils  (log_event)

app/routes/dashboard.py
  ├── flask, flask_login
  ├── app  (db)
  └── app.models  (Recommendation, Rating, Watchlist)

app/utils.py
  ├── app  (db)
  ├── app.models  (EventLog)
  └── app.kafka_producer  (produce_event)  ← imported inside function at call time

app/kafka_producer.py
  ├── json, logging, time
  ├── flask  (current_app)  ← optional, caught if outside request context
  └── kafka  (KafkaProducer)  ← imported lazily

ml_service/consumer.py
  ├── json, logging, os, sys, time
  ├── ml_service.db_utils  (get_movie_title)
  ├── ml_service.recommender  (build_recommendations, build_all_recommendations)
  └── kafka  (KafkaConsumer)

ml_service/recommender.py
  ├── logging, numpy
  ├── scipy.sparse, scipy.sparse.linalg
  └── ml_service.db_utils  (get_all_ratings, get_all_users, get_all_movies,
                             get_user_rated_movies, save_recommendations)

ml_service/db_utils.py
  ├── os, logging, datetime
  └── sqlalchemy  (create_engine, text)
```

**Critical design rule**: `ml_service` never appears anywhere in `app/`. The `app/` package never appears anywhere in `ml_service/`. They are siblings, not parents/children.

---

## 3. Database

### How Flask-Migrate Works

Flask-Migrate is a wrapper around **Alembic**, the database migration tool for SQLAlchemy. Instead of manually writing SQL `CREATE TABLE` statements, you describe your tables in Python (in `models.py`) and let Alembic figure out what SQL to generate.

**Workflow:**

```
flask db init          # Creates the migrations/ folder (run once)
flask db migrate -m "initial schema"   # Compares models to DB, writes a migration file
flask db upgrade       # Runs the migration file against the actual database
```

The migration file (`0da335019721_initial_schema.py`) is a Python script with two functions:
- `upgrade()` — creates tables (runs on `flask db upgrade`)
- `downgrade()` — drops tables (runs on `flask db downgrade`)

Alembic tracks which migrations have been applied in a `alembic_version` table inside the database.

The `migrations/env.py` file connects Alembic to the Flask app: it reads the database URL from `current_app.extensions['migrate'].db.engine`, so the migration always uses the same database the app is configured for.

### All 6 Tables

#### `users`
| Column | Type | Constraint | Purpose |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | Auto-increment user ID |
| username | VARCHAR(80) | UNIQUE, NOT NULL | Display name |
| email | VARCHAR(120) | UNIQUE, NOT NULL | Login identifier |
| password_hash | VARCHAR(256) | NOT NULL | bcrypt hash (never plain text) |
| created_at | DATETIME | default=now | Account creation timestamp |

#### `movies`
| Column | Type | Constraint | Purpose |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | Auto-increment movie ID |
| title | VARCHAR(200) | NOT NULL | Full title |
| genre | VARCHAR(100) | — | Drama, Action, Sci-Fi, etc. |
| year | INTEGER | — | Release year |
| director | VARCHAR(100) | — | Director name |
| description | TEXT | — | Plot summary |
| poster_url | VARCHAR(300) | — | Image URL (empty string if none) |
| avg_rating | FLOAT | default=0.0 | Cached average of all ratings |

The `avg_rating` column is a **denormalisation** — it stores a pre-computed value that could be derived from the `ratings` table. This avoids a `AVG()` query on every page load. It is recalculated after every new rating in the `rate` route.

#### `ratings`
| Column | Type | Constraint | Purpose |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | — |
| user_id | INTEGER | FK → users.id, NOT NULL | Who rated |
| movie_id | INTEGER | FK → movies.id, NOT NULL | What was rated |
| score | INTEGER | NOT NULL | 1–5 stars |
| rated_at | DATETIME | default=now | When rated |
| — | UNIQUE(user_id, movie_id) | name='unique_user_movie_rating' | One rating per user per movie |

The unique constraint ensures a user can only have one rating per movie. The `rate` route uses an **upsert** pattern: query for existing rating, update if found, insert if not.

#### `watchlist`
| Column | Type | Constraint | Purpose |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | — |
| user_id | INTEGER | FK → users.id, NOT NULL | Who added |
| movie_id | INTEGER | FK → movies.id, NOT NULL | What was added |
| added_at | DATETIME | default=now | Timestamp |

A simple join table. The `toggle_watchlist` route deletes the row if it exists, creates it if it doesn't.

#### `events_log`
| Column | Type | Constraint | Purpose |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | — |
| user_id | INTEGER | FK → users.id, NOT NULL | Who triggered the event |
| event_type | VARCHAR(50) | NOT NULL | 'user.rated', 'user.watched', 'user.searched', 'user.clicked' |
| payload | JSON | — | Event-specific data: `{"movie_id": 5, "score": 4}` |
| created_at | DATETIME | default=now | Event timestamp |

This table is a **durable audit log**. Every user action is written here regardless of whether Kafka is running. If Kafka goes down and comes back up, the history is preserved in the DB even though those events were never streamed.

#### `recommendations`
| Column | Type | Constraint | Purpose |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | — |
| user_id | INTEGER | FK → users.id, NOT NULL | For whom |
| movie_id | INTEGER | FK → movies.id, NOT NULL | What is recommended |
| score | FLOAT | — | ML confidence score (predicted rating, 1–5) |
| generated_at | DATETIME | default=now | When the ML built this recommendation |

Written exclusively by the ML service (`ml_service/db_utils.py → save_recommendations`). Read exclusively by Flask (`dashboard.py`). This table is the **shared contract** between the two independent systems.

### All Relationships

```
users ──< ratings >── movies
users ──< watchlist >── movies
users ──< events_log
users ──< recommendations >── movies
```

SQLAlchemy `relationship()` objects are defined on the model, creating backrefs:
- `rating.user` → the User who made this rating
- `rating.movie` → the Movie that was rated
- `rec.movie` → the Movie being recommended (used in templates: `rec.movie.title`)

### Current Row Counts

| Table | Rows |
|---|---|
| users | 11 |
| movies | 20 |
| ratings | 141 |
| watchlist | 2 |
| events_log | 80 |
| recommendations | 78 |

---

## 4. Flask Web App

### The Application Factory Pattern — Why Not a Global App

Many Flask tutorials start with:

```python
app = Flask(__name__)  # global — WRONG for production
```

CineMatch uses the **Application Factory** pattern instead:

```python
# app/__init__.py
def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    db.init_app(app)
    # ... register blueprints ...
    return app
```

**Why this matters:**

1. **Testing**: You can call `create_app()` multiple times with different configs (test DB, production DB) without one instance polluting another.
2. **Extensions are app-aware, not global**: `db = SQLAlchemy()` is created at module level but only *bound* to an app inside `create_app()` via `db.init_app(app)`. This means `db` can work with multiple apps in the same Python process.
3. **Circular imports are avoided**: Models import `db` from `app/__init__.py`. Routes import from `app/models.py`. If `app` were a global object that also imported routes at module level, Python's import system would deadlock. The factory delays route imports until after all extensions exist.
4. **Alembic compatibility**: Flask-Migrate needs a factory function to discover models. Without it, `flask db migrate` cannot see the table definitions.

The extensions are created *outside* `create_app()` so they can be imported by models and routes without importing the app object:

```python
db = SQLAlchemy()     # created here — importable anywhere
bcrypt = Bcrypt()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    db.init_app(app)   # bound to app here
```

### Blueprints

A **Blueprint** is a reusable component of a Flask application — a group of routes, templates, and static files that can be registered onto an app. CineMatch has three:

| Blueprint | URL Prefix | File |
|---|---|---|
| `auth_bp` | `/auth` | `app/routes/auth.py` |
| `movies_bp` | `/movies` | `app/routes/movies.py` |
| `dashboard_bp` | `/dashboard` | `app/routes/dashboard.py` |

### Every Route

#### Auth Blueprint (`/auth`)

| Method | URL | What It Does |
|---|---|---|
| GET | `/auth/register` | Show registration form |
| POST | `/auth/register` | Validate, hash password, create User, redirect to login |
| GET | `/auth/login` | Show login form |
| POST | `/auth/login` | Verify credentials, call `login_user()`, redirect to dashboard |
| GET | `/auth/logout` | Call `logout_user()`, redirect to login |

#### Movies Blueprint (`/movies`)

| Method | URL | What It Does |
|---|---|---|
| GET | `/movies/` | Paginated catalog (12/page), genre list, user ratings dict |
| GET | `/movies/search` | ILIKE search on title+genre, log `user.searched` if auth |
| GET | `/movies/<id>` | Movie detail, user's rating, watchlist state, similar movies |
| POST | `/movies/<id>/rate` | Upsert rating, recalc avg_rating, log `user.rated`, return JSON |
| POST | `/movies/<id>/watchlist` | Toggle watchlist membership, log `user.watched`, return JSON |

#### Dashboard Blueprint (`/dashboard`)

| Method | URL | What It Does |
|---|---|---|
| GET | `/dashboard/` | Top-10 recommendations, last-5 ratings, last-5 watchlist items |
| GET | `/dashboard/profile` | All ratings (history table) + stat cards |
| POST | `/dashboard/watchlist/<id>/remove` | Delete watchlist row, return `{success: true}` |

### Auth Flow — Register

```
User fills form → POST /auth/register
  1. Extract username, email, password from request.form
  2. Validate: all fields present, password >= 6 chars
  3. Query: User.query.filter_by(email=email).first() → must be None
  4. Query: User.query.filter_by(username=username).first() → must be None
  5. bcrypt.generate_password_hash(password).decode('utf-8')
     → produces a 60-char hash like "$2b$12$..."
     → bcrypt internally generates a random salt and embeds it in the hash
  6. user = User(username=..., email=..., password_hash=hash)
  7. db.session.add(user); db.session.commit()
  8. flash('Registration successful!', 'success')
  9. redirect → GET /auth/login
```

**Why bcrypt?** Bcrypt is a *slow* hash function by design. It takes ~100ms per hash, which is imperceptible to humans but makes brute-force attacks 1000x harder than fast hashes like SHA-256. The salt is embedded in the hash string, so the same password always produces a different hash — preventing rainbow-table attacks.

### Auth Flow — Login

```
User fills form → POST /auth/login
  1. Extract email, password from request.form
  2. user = User.query.filter_by(email=email).first()
  3. If user is None: flash error, re-render form
  4. bcrypt.check_password_hash(user.password_hash, password)
     → True if password matches the hash
  5. If False: flash error, re-render form
  6. login_user(user)
     → Flask-Login writes user.id to the session cookie (encrypted with SECRET_KEY)
  7. next_page = request.args.get('next')
     → If ?next=/dashboard/ was in the URL (set by login_required redirect), go there
  8. redirect → dashboard.index (or next_page)
```

### How Flask-Login Works

Flask-Login manages the **session** — a signed cookie that stores the logged-in user's ID between HTTP requests (HTTP is stateless by itself).

**Key components:**

1. **`UserMixin`**: Added to the `User` model class. Provides four properties Flask-Login needs: `is_authenticated`, `is_active`, `is_anonymous`, `get_id()`. Without `UserMixin`, Flask-Login cannot use the model.

2. **`@login_manager.user_loader`**: A callback that Flask-Login calls on *every request* to reload the user from the database:
   ```python
   @login_manager.user_loader
   def load_user(user_id):
       from app.models import User
       return User.query.get(int(user_id))
   ```
   Flask-Login reads the user ID from the session cookie, calls this function, and makes the result available as `current_user` everywhere in the request.

3. **`login_user(user)`**: Writes the user's ID into the session cookie. Flask signs the cookie with `SECRET_KEY` so it cannot be tampered with.

4. **`logout_user()`**: Clears the session cookie.

5. **`@login_required`**: A decorator that checks `current_user.is_authenticated`. If False (user not logged in), redirects to `login_manager.login_view` (set to `'auth.login'`). The original URL is preserved as `?next=<url>`.

6. **`current_user`**: A thread-local proxy. In any route, template, or utility function, `current_user.id` gives the logged-in user's ID. If not logged in, it's an anonymous user with `is_authenticated = False`.

### log_event() — Phase 3 vs Phase 4

In **Phase 3** (movie catalog, no Kafka), `log_event` only wrote to the database:
```python
# Phase 3 version
def log_event(user_id, event_type, payload):
    event = EventLog(user_id=user_id, event_type=event_type, payload=payload)
    db.session.add(event)
    db.session.commit()
```

In **Phase 4** (Kafka integration), a Kafka produce was added — wrapped in try/except so the Flask app keeps working even if Kafka is down:

```python
# Phase 4+ version (current)
def log_event(user_id, event_type, payload):
    # 1. DB write — always, unconditionally
    event = EventLog(user_id=user_id, event_type=event_type, payload=payload)
    db.session.add(event)
    db.session.commit()

    # 2. Kafka produce — best-effort, silent on failure
    try:
        from app.kafka_producer import produce_event
        produce_event(event_type, {**payload, 'user_id': user_id})
    except Exception as exc:
        logger.warning('log_event: Kafka produce skipped: %s', exc)
```

Note that `user_id` is added to the Kafka payload (`{**payload, 'user_id': user_id}`) but NOT to the DB payload column — it is stored in its own `EventLog.user_id` column. This is important: the ML consumer needs `user_id` in the Kafka message to know whose recommendations to rebuild, without having to query the database.

### kafka_producer.py — Lazy Init and 30-Second Cooldown

The producer is designed around a key requirement: **Flask must work whether or not Kafka is running**.

```python
_producer = None      # No connection yet
_next_retry_at = 0.0  # Retry immediately on first call
_RETRY_INTERVAL = 30  # After a failure, wait 30s before retrying

def _get_producer():
    global _producer, _next_retry_at

    if _producer is not None:           # Already connected — return it
        return _producer

    if time.time() < _next_retry_at:    # Still in cooldown — don't try
        return None

    try:
        _producer = KafkaProducer(...)  # Try to connect
    except Exception:
        _next_retry_at = time.time() + 30  # Failed — wait 30s
        _producer = None
    return _producer
```

**Why lazy?** The producer is only created when the first `produce_event()` call happens (i.e., on the first rating/watchlist action), not at Flask startup. This means starting Flask takes 20ms instead of potentially timing out waiting for Kafka.

**Why 30-second cooldown?** Without it, every rating action while Kafka is down would attempt a new TCP connection (up to `max_block_ms=3000` = 3 second wait). With 30 users rating movies concurrently, that's 90 seconds of blocking. The cooldown makes the second-through-30th requests in that window return `None` immediately and proceed.

**What happens when Kafka goes down mid-run?** If `producer.send()` raises an exception, `_producer` is set to `None`. The next request will attempt a fresh reconnect after the cooldown.

---

## 5. Kafka

### What Kafka Is

Apache Kafka is a distributed **message broker** — a system that sits between a *producer* (who sends messages) and a *consumer* (who reads messages), decoupling them in time and space.

Key concepts:

| Term | Definition |
|---|---|
| **Broker** | The Kafka server process that stores and serves messages |
| **Topic** | A named category of messages (like a queue name) |
| **Producer** | Any process that publishes messages to a topic |
| **Consumer** | Any process that reads messages from a topic |
| **Offset** | An integer position in a topic (0, 1, 2, ...). Each message has a unique offset |
| **Consumer Group** | A named group of consumers. Kafka tracks which offset each group has read up to |
| **Auto-offset-reset** | What to do when a consumer group has no committed offset yet: `latest` (skip old messages) or `earliest` (read from the beginning) |

### docker-compose.yml Explained

```yaml
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181   # Port Kafka connects to Zookeeper on
      ZOOKEEPER_TICK_TIME: 2000     # Heartbeat interval in ms
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    depends_on:
      - zookeeper              # Kafka starts AFTER Zookeeper is up
    ports:
      - "9092:9092"            # Exposed to the host machine
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181   # Internal Docker network name
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092  # Tells clients "reach me here"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1   # Single-node cluster needs factor=1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"     # Topics created automatically on first use
      KAFKA_LOG_RETENTION_HOURS: 24               # Messages kept for 24 hours
```

**Why Zookeeper?** Kafka 7.4.0 (used here) still uses Zookeeper to store cluster metadata: which brokers exist, which partitions belong to which broker, consumer group offsets. Newer Kafka versions (3.x+) have replaced Zookeeper with KRaft, but the Confluent 7.4.0 image requires it.

**Why `KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092`?** When a Kafka client (producer or consumer) first connects to the broker, the broker replies with its *advertised address* — the address clients should use for subsequent connections. Advertising `localhost:9092` means all clients running on the same machine can connect. (In production with multiple machines, this would be a real hostname or IP.)

### All 4 Topics and What Triggers Them

| Topic | Trigger | Payload Example |
|---|---|---|
| `user.rated` | `POST /movies/<id>/rate` | `{"movie_id": 15, "score": 5, "user_id": 2}` |
| `user.watched` | `POST /movies/<id>/watchlist` (add) | `{"movie_id": 7, "action": "add", "user_id": 3}` |
| `user.searched` | `GET /movies/search?q=...` (authenticated) | `{"query": "Nolan", "user_id": 1}` |
| `user.clicked` | `GET /movies/<id>` (authenticated) | `{"movie_id": 12, "user_id": 5}` |

### Producer Flow (Flask → Kafka)

```
User POSTs /movies/15/rate with score=5
  ↓
movies.py::rate(id=15)
  ↓
log_event(current_user.id, 'user.rated', {'movie_id': 15, 'score': 5})
  ↓
utils.py::log_event(user_id=2, event_type='user.rated', payload={'movie_id':15,'score':5})
  ├── EventLog written to DB   ← guaranteed
  └── produce_event('user.rated', {'movie_id':15,'score':5,'user_id':2})
        ↓
      kafka_producer.py::produce_event(topic, payload_dict)
        ├── _get_producer()  → returns cached KafkaProducer (or None if down)
        ├── producer.send('user.rated', value={'movie_id':15,'score':5,'user_id':2})
        │     → KafkaProducer serializes to JSON bytes: b'{"movie_id":15,...}'
        │     → sends to Kafka broker at localhost:9092
        └── producer.flush(timeout=1)  → wait up to 1s for acknowledgement
```

### Consumer Flow (Kafka → ML → DB)

```
Kafka broker has message at offset 18 in user.rated
  ↓
ml_service/consumer.py::run()  [infinite loop]
  for message in consumer:   ← KafkaConsumer yields messages as they arrive
    process_message(message.topic, message.value)
      ↓
    process_message('user.rated', {'movie_id':15,'score':5,'user_id':2})
      ├── user_id = payload.get('user_id')   → 2
      ├── movie_id = payload.get('movie_id') → 15
      ├── get_movie_title(15)                → "The Lion King"
      ├── logger.info('[user.rated]  user_id=2  "The Lion King"  score=5')
      └── build_recommendations(user_id=2)
            ↓
          recommender.py::build_recommendations(2)
            ├── get_all_ratings()      → 141 (user_id, movie_id, score) tuples
            ├── _svd_recs(2, ratings)  → [(movie_id, predicted_score), ...]
            └── save_recommendations(2, recs)
                  ↓
                db_utils.py::save_recommendations(2, recs)
                  ├── DELETE FROM recommendations WHERE user_id=2
                  └── INSERT INTO recommendations ... (10 rows)
            ↓
          logger.info('Updated recommendations for user 2')
```

### What Happens When Kafka Is Down

**Flask side**: `produce_event()` catches the connection error, sets a 30-second cooldown, logs a warning, and returns normally. The HTTP response is not affected. The EventLog DB write has already committed before the Kafka attempt. Zero user impact.

**Consumer side**: The `run()` function is wrapped in `while True: try: ... except Exception:`. If Kafka is unreachable, `KafkaConsumer(...)` raises, the exception is caught, a warning is logged, and the consumer sleeps 5 seconds before retrying. The process does not exit.

```python
while True:
    try:
        consumer = KafkaConsumer(*TOPICS, ...)  # raises if Kafka down
        while True:
            for message in consumer:
                process_message(message.topic, message.value)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        logger.warning('Kafka error: %s', exc)
        logger.info('Retrying in %d seconds...', RETRY_INTERVAL)
        time.sleep(RETRY_INTERVAL)   # wait 5s, then try again
```

---

## 6. ML Service

### How It Is Completely Decoupled

The `ml_service/` directory is a completely independent Python package. It:
- Has **no imports from `app/`** (verified by an independence check in `test_ml.py`)
- Does **not use Flask** or any Flask extension
- Does **not use Flask-SQLAlchemy** — it talks to the database directly via SQLAlchemy Core
- Can be run without Flask being installed at all

The only shared resources are:
- The SQLite file at `instance/cinematch.db` (path computed relative to `__file__`)
- Kafka topics (strings)

### consumer.py — Startup Sequence and Infinite Loop

When `python -m ml_service.consumer` is run:

```
1. sys.path.insert(0, project_root)   ← makes ml_service importable as a package

2. logging.basicConfig(...)           ← configure logging to stderr

3. run() called:
   a. logger.info('CineMatch ML Consumer starting up')
   b. logger.info('Broker: localhost:9092')
   c. logger.info('Topics: user.rated, ...')

   d. build_all_recommendations()
      ├── get_all_users()          → [1, 2, 3, ..., 11]
      └── for uid in users:
            build_recommendations(uid)   ← SVD for all 11 users at startup
      └── logger.info('Done. Recommendations saved for 11 users.')

   e. OUTER LOOP: while True:
        try:
          consumer = KafkaConsumer(
            'user.rated', 'user.watched', 'user.searched', 'user.clicked',
            bootstrap_servers='localhost:9092',
            group_id='cinematch-ml',
            auto_offset_reset='latest',       ← start from newest message
            consumer_timeout_ms=1000,          ← non-blocking 1s poll (allows Ctrl-C)
            session_timeout_ms=10_000,
            heartbeat_interval_ms=3_000,
            request_timeout_ms=30_000,
          )
          INNER LOOP: while True:
            for message in consumer:
              process_message(message.topic, message.value)
        except KeyboardInterrupt: sys.exit(0)
        except Exception: sleep(5); retry outer loop
```

**Why `consumer_timeout_ms=1000`?** The `for message in consumer:` loop would block forever if no messages arrive. With `consumer_timeout_ms=1000`, the loop exits after 1 second of silence, returns control to `while True`, and immediately re-enters the loop. This makes Ctrl-C responsive — without it, pressing Ctrl-C during idle time would have to wait for the next message to arrive.

### recommender.py — The Math

The recommender implements **mean-centred Truncated SVD** collaborative filtering.

**Step 1: Build the user-item matrix**

```
R[user_index][movie_index] = score (or 0 if not rated)

Example (4 users, 5 movies, simplified):
         Film A  Film B  Film C  Film D  Film E
User 1:    5       4       0       0       3
User 2:    4       0       0       5       0
User 3:    0       0       4       0       3
User 4:    0       5       0       4       0
```

**Step 2: Mean-centre (remove user bias)**

Each user has a different baseline: some rate everything 5 stars, some rate everything 2. Mean-centring removes this bias:
```
user_mean[i] = average of all non-zero entries in row i
R_centred[i][j] = R[i][j] - user_mean[i]   (only for rated items)
```

**Step 3: Truncated SVD**

SVD (Singular Value Decomposition) factorises the centred matrix into three matrices:
```
R_centred ≈ U × Σ × Vᵀ
```
Where:
- `U` (n_users × k): each row is a user represented in k latent dimensions
- `Σ` (k × k): diagonal matrix of "importance" of each dimension
- `Vᵀ` (k × n_movies): each column is a movie in k latent dimensions

The latent dimensions capture concepts like "prefers action", "likes 1990s films", "dislikes animation" — the algorithm discovers these automatically from the rating patterns.

`k = min(20, min(n_users, n_movies) - 1)` — the number of latent factors is capped at 20 but reduced if the matrix is small (SVD requires k < min(rows, cols)).

**Step 4: Reconstruct predicted ratings**

```python
predicted = U @ np.diag(sigma) @ Vt + user_means.reshape(-1, 1)
predicted = np.clip(predicted, 1.0, 5.0)
```

Every cell in `predicted` is now a score estimate, even for user-movie pairs that were 0 (unrated).

**Step 5: Extract and rank recommendations**

For the target user:
```python
user_row = predicted[uid2i[user_id]]   # predicted scores for this user
rated = get_user_rated_movies(user_id) # movies already rated
recs = [(movie_id, score) for (movie_id, score) in user_row if movie_id not in rated]
recs.sort(key=lambda x: x[1], reverse=True)
return recs[:10]  # top 10
```

**Fallback path**: If there are fewer than 10 ratings in the entire database (`_MIN_RATINGS_FOR_SVD = 10`), SVD cannot produce meaningful results. The fallback returns the highest `avg_rating` movies the user hasn't yet rated.

### db_utils.py — Why Direct SQLAlchemy

Flask-SQLAlchemy requires an active **Flask application context** to work — it uses `current_app` internally. When `ml_service/consumer.py` runs as a standalone process (no Flask running), there is no `current_app`. Using Flask-SQLAlchemy would raise `RuntimeError: No application is running`.

The solution: use **SQLAlchemy Core** directly, with a `create_engine()` call:

```python
_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'instance', 'cinematch.db')
)

def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(f'sqlite:///{_DB_PATH}', future=True)
    return _engine
```

The path is computed *relative to the `db_utils.py` file* (`..` goes up from `ml_service/` to the project root, then into `instance/`). This works regardless of the current working directory when the script is run.

SQLAlchemy Core uses `text()` for raw SQL strings and explicit `conn.execute()` calls instead of ORM queries, which is appropriate here since the ML service only needs simple reads and one atomic write (delete+insert).

---

## 7. Full Request Lifecycles

### a. User Registers

```
Browser: GET /auth/register
  → Flask renders auth/register.html (form)

Browser: POST /auth/register (username=alice, email=alice@x.com, password=secret123)
  → auth.py::register()
  → validate inputs (length, presence)
  → User.query.filter_by(email='alice@x.com').first() → None (not taken)
  → User.query.filter_by(username='alice').first() → None (not taken)
  → hash = bcrypt.generate_password_hash('secret123').decode('utf-8')
     → "$2b$12$TsA...83chars..."
  → user = User(username='alice', email='alice@x.com', password_hash=hash)
  → db.session.add(user); db.session.commit()
     → INSERT INTO users (username, email, password_hash, created_at) VALUES (...)
  → flash('Registration successful!', 'success')
  → redirect 302 → GET /auth/login
```

DB writes: 1 row in `users`.

### b. User Logs In

```
Browser: POST /auth/login (email=alice@x.com, password=secret123)
  → auth.py::login()
  → user = User.query.filter_by(email='alice@x.com').first()
     → SELECT * FROM users WHERE email='alice@x.com' LIMIT 1
  → bcrypt.check_password_hash(user.password_hash, 'secret123') → True
  → login_user(user)
     → Flask-Login writes user.id (e.g. 4) into the session
     → Session is a signed cookie: Set-Cookie: session=<encrypted>; HttpOnly
  → redirect 302 → GET /dashboard/
```

All subsequent requests from this browser will include the cookie, and Flask-Login will call `load_user(4)` to populate `current_user`.

### c. User Rates a Movie (Most Important — Full Trace)

```
Browser: POST /movies/15/rate  (form body: score=5)
  Cookie: session=<encrypted containing user_id=2>

1. Flask-Login middleware:
   → Decrypts session cookie → user_id=2
   → load_user(2) → SELECT * FROM users WHERE id=2
   → current_user = <User alice>

2. movies.py::rate(id=15)
   → movie = Movie.query.get_or_404(15)
      → SELECT * FROM movies WHERE id=15

3. Score validation:
   → score = int('5') = 5
   → 1 <= 5 <= 5 ✓

4. Upsert:
   → existing = Rating.query.filter_by(user_id=2, movie_id=15).first()
   → If exists: existing.score = 5
   → If not: db.session.add(Rating(user_id=2, movie_id=15, score=5))

5. Avg recalculation:
   → db.session.flush()   ← writes to DB without committing (makes score visible to AVG)
   → avg = db.session.query(func.avg(Rating.score)).filter(Rating.movie_id==15).scalar()
      → SELECT AVG(score) FROM ratings WHERE movie_id=15
   → movie.avg_rating = round(avg, 2)
   → db.session.commit()
      → UPDATE ratings SET score=5 WHERE user_id=2 AND movie_id=15
      → UPDATE movies SET avg_rating=X WHERE id=15

6. log_event(user_id=2, 'user.rated', {'movie_id':15, 'score':5})
   → INSERT INTO events_log (user_id, event_type, payload, created_at) VALUES (...)
   → db.session.commit()   ← event log committed separately
   → produce_event('user.rated', {'movie_id':15, 'score':5, 'user_id':2})
      → KafkaProducer.send('user.rated', b'{"movie_id":15,"score":5,"user_id":2}')
      → KafkaProducer.flush(timeout=1)
         → Kafka broker receives message, assigns offset 18

7. Return JSON:
   → jsonify({'success': True, 'avg_rating': 2.43})

--- Meanwhile, ~0.5 seconds later ---

8. Kafka consumer (separate process):
   → for message in consumer:  ← message arrives
   → process_message('user.rated', {'movie_id':15,'score':5,'user_id':2})
   → build_recommendations(user_id=2)
      → get_all_ratings() → 141 tuples from ratings table
      → _svd_recs(2, ratings) → SVD computation (~50ms)
      → save_recommendations(2, [(movie_id, score), ...])
         → BEGIN TRANSACTION
         → DELETE FROM recommendations WHERE user_id=2
         → INSERT INTO recommendations ... × 10 rows
         → COMMIT
   → logger.info('Updated recommendations for user 2')
```

DB writes (in order): `ratings` (upsert), `movies` (avg_rating), `events_log` (1 row), `recommendations` (10 rows — in separate process).

### d. User Visits Dashboard

```
Browser: GET /dashboard/
  Cookie: session=<encrypted containing user_id=2>

1. Flask-Login: load_user(2) → current_user = alice

2. dashboard.py::index()
   → Recommendation.query.filter_by(user_id=2)
       .order_by(Recommendation.score.desc()).limit(10).all()
      → SELECT r.*, m.* FROM recommendations r JOIN movies m ON r.movie_id=m.id
        WHERE r.user_id=2 ORDER BY r.score DESC LIMIT 10
      → 10 Recommendation objects, each with .movie loaded via backref

   → Rating.query.filter_by(user_id=2)
       .order_by(Rating.rated_at.desc()).limit(5).all()
      → 5 Rating objects with .movie loaded

   → Watchlist.query.filter_by(user_id=2)
       .order_by(Watchlist.added_at.desc()).limit(5).all()
      → up to 5 Watchlist objects with .movie loaded

3. render_template('dashboard/index.html',
     recommendations=[...], recent_ratings=[...], watchlist=[...])
   → Jinja2 renders the template
   → For each rec: rec.movie.title, rec.movie.genre, rec.movie.avg_rating
   → 200 OK, HTML response
```

---

## 8. Architecture — How the Two Sides Communicate

### The Two-Sided Diagram

```
┌─────────────────────────────────────┐      ┌──────────────────────────────────────┐
│          Flask Web App              │      │          ML Service                   │
│  (app/)                             │      │  (ml_service/)                       │
│                                     │      │                                      │
│  routes/ → utils.py → kafka_prod   │─────▶│  consumer.py → recommender.py       │
│                    ↓                │      │                      ↓               │
│              events_log             │      │              recommendations          │
│              ratings                │      │  ← reads ratings                     │
│              movies                 │      │  → writes recommendations            │
│              users                  │      │                                      │
│                    ↑                │      │                                      │
│              dashboard.py reads     │      │                                      │
│              recommendations        │      │                                      │
└─────────────────────────────────────┘      └──────────────────────────────────────┘
                    │                                          ▲
                    │           Kafka Topics                   │
                    └──────── user.rated ──────────────────────┘
                              user.watched
                              user.searched
                              user.clicked
```

### The Rule: No Cross-Imports

```python
# This NEVER appears in app/:
from ml_service import anything

# This NEVER appears in ml_service/:
from app import anything
import flask
```

This is enforced and tested:
```python
# test_ml.py — independence check
import ml_service.db_utils as du
import ml_service.recommender as rec
for mod in (du, rec):
    src = open(mod.__file__).read()
    assert 'from app' not in src and 'import app' not in src
```

### Shared Resources

| Resource | Flask does | ML service does |
|---|---|---|
| `ratings` table | Writes new ratings | Reads all ratings for SVD |
| `recommendations` table | Reads to show dashboard | Deletes old + inserts new |
| `events_log` table | Writes events | Never reads (not needed) |
| `movies` table | Reads for display | Reads avg_rating for fallback |
| Kafka topics | Publishes messages | Consumes messages |

### Why This Is Good Design

1. **Independent deployment**: The ML service can be on a different server, upgraded to a better model, or restarted — without touching Flask.

2. **No blocking**: Flask does not wait for ML computation. The rating response is returned in <10ms. ML runs asynchronously and updates recommendations in the background.

3. **Resilience**: If the ML service is down, recommendations on the dashboard are simply the last ones computed (or empty for new users). The rating still works, the EventLog still records the event, and when the ML service comes back up, it starts consuming from its last committed Kafka offset.

4. **Separation of concerns**: Flask code never has to know whether SVD is used or some other algorithm. ML code never has to know what web framework renders the recommendations. Each side has one job.

5. **Testability**: `test_ml.py` runs the entire ML pipeline — ratings → SVD → recommendations — without starting Flask. `test_live.py` tests the full round-trip. Each can be run independently.

---

## 9. How to Run

### Prerequisites

- Python 3.12
- Docker Desktop
- Git

### Step-by-Step from Scratch

**1. Clone and install dependencies**
```bash
cd "CineMatch Project"
pip install -r requirements.txt
```
This installs Flask, SQLAlchemy, Flask-Login, Flask-Bcrypt, kafka-python-ng, NumPy, SciPy, and scikit-learn.

**2. Set up the database**
```bash
python -m flask db upgrade
```
This reads `migrations/versions/0da335019721_initial_schema.py` and creates `instance/cinematch.db` with all 6 tables. If the file already exists, Alembic skips migrations that have already been applied.

**3. Seed sample data**
```bash
python seed.py
```
Creates 20 movies, 8 users (user1@cinematch.dev through user8@cinematch.dev, password: `password123`), ~141 ratings. Safe to re-run — idempotent.

**4. Start Kafka (Docker)**
```bash
docker-compose up -d
```
Starts two containers: Zookeeper on port 2181, Kafka on port 9092. Wait ~10 seconds for Kafka to fully initialise.

**5. Start the ML consumer (separate terminal)**
```bash
python -m ml_service.consumer
```
The consumer will:
- Build recommendations for all existing users (using SVD) — takes ~2 seconds
- Connect to Kafka and start listening for events

Expected output:
```
Building initial recommendations for all users...
Recommendations saved for user 1  [SVD, 10 items]
...
Done. Recommendations saved for 11 users.
Connected. Waiting for events...
```

**6. Start Flask (separate terminal)**
```bash
python -m flask run
# or: python run.py
```
Flask runs on http://127.0.0.1:5000.

**7. Verify everything works**
```bash
python test_live.py
```
This script:
- Logs in as user2
- Rates a movie
- Waits 6 seconds
- Checks the Kafka consumer log for the rebuild confirmation
- Checks the recommendations table

Expected output: all `[PASS]`.

### Verifying Each Component Independently

| Component | Verification command |
|---|---|
| Database | `python test_ml.py` (ML unit tests, no Flask, no Kafka) |
| Flask web | Visit http://127.0.0.1:5000 and register/login |
| Kafka | `docker exec cinematchproject-kafka-1 kafka-topics --list --bootstrap-server cinematchproject-kafka-1:9092` |
| ML + Kafka end-to-end | `python test_live.py` |

### What Happens Without Kafka

Flask works normally — every feature except streaming events to Kafka. Recommendations still show from the last ML run. The EventLog still records every action. Run `python ml_service/consumer.py` later and it will build recommendations from the DB directly on startup.

---

## 10. What Was Learned

### Application Factory Pattern

Instead of `app = Flask(__name__)` at module level, wrapping app creation in a function solves circular imports, enables multiple configurations (test vs. production), and lets Flask-Migrate auto-discover models. The pattern is: extensions created globally → bound to app inside factory → blueprints imported and registered inside factory.

### Blueprint

A Blueprint organises routes into groups. Each Blueprint has its own URL prefix, template folder (optional), and namespace. `url_for('movies.detail', id=1)` means "the `detail` function in the `movies` Blueprint". Blueprints make it easy to split a large app into logical modules without affecting each other.

### ORM (Object-Relational Mapping)

SQLAlchemy ORM maps Python classes to database tables. Instead of writing `SELECT * FROM users WHERE id=2`, you write `User.query.get(2)`. Relationships (`db.relationship`) allow accessing related objects as Python attributes (`rating.movie.title`) — SQLAlchemy generates the JOIN query automatically. The `lazy=True` default means joins happen on-demand (not eagerly loaded).

### bcrypt

bcrypt is an adaptive hashing algorithm specifically designed for passwords. It is deliberately slow (configurable via "work factor"), embeds a random salt in every hash, and produces a fixed-length output. The same password produces a different hash each time it is called, making rainbow-table attacks impossible. `check_password_hash` re-hashes the plain-text and compares — it never stores or transmits the plain password.

### Flask-Login

Flask-Login provides session-based authentication. It signs the user ID into a cookie using the app's `SECRET_KEY`. On every request, it reads the cookie, extracts the ID, calls the `user_loader` callback to fetch the user from the DB, and makes it available as `current_user`. `@login_required` checks `current_user.is_authenticated` and redirects to the login page if False. `UserMixin` gives the model the four properties Flask-Login expects.

### Event-Driven Architecture

Instead of calling the ML service directly from the rate endpoint (tight coupling, blocking), the rate endpoint publishes an event to Kafka (fire-and-forget). The ML service consumes this event asynchronously and rebuilds recommendations. The two systems are completely decoupled in time (ML runs later), space (can be on different machines), and code (no shared imports). The event stream also serves as a durable audit log.

### Kafka Decoupling

Kafka adds resilience: if the ML service is down when a user rates a movie, the event is stored in Kafka (up to 24 hours by default). When the ML service comes back up, it reads from its last committed offset and processes all the missed events. This is impossible with direct HTTP calls (if the ML server is down, the call fails).

### Collaborative Filtering

Collaborative filtering makes predictions based on the collective behaviour of all users — not the content of the movies themselves. The intuition: if Alice and Bob both gave 5 stars to The Dark Knight, Inception, and Interstellar, and Alice loved Arrival (4.5 stars) but Bob hasn't seen it — Bob will probably like Arrival too. The algorithm finds these patterns by factorising the user-item rating matrix.

### Truncated SVD (Singular Value Decomposition)

SVD is a matrix factorisation technique from linear algebra. Applied to a sparse user-item rating matrix, it discovers hidden "latent factors" — abstract dimensions that capture user preferences and movie characteristics. The "truncated" version (`scipy.sparse.linalg.svds`) only computes the top-k factors, which is faster and reduces noise. Mean-centring before SVD removes individual rating biases (some users always rate high, some always rate low), making the predictions more accurate.

---

*Report generated from CineMatch Project — 6 development phases, 20+ source files, ~2,500 lines of Python and HTML.*
