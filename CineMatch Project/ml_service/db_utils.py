"""
Direct DB access for the ML service.
No Flask app context — uses SQLAlchemy Core (create_engine) only.
"""
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'instance', 'cinematch.db')
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(f'sqlite:///{_DB_PATH}', future=True)
    return _engine


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_all_ratings():
    """Return list of (user_id, movie_id, score) for every rating in DB."""
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text('SELECT user_id, movie_id, score FROM ratings')
        ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def get_all_users():
    """Return list of all user IDs."""
    with _get_engine().connect() as conn:
        rows = conn.execute(text('SELECT id FROM users')).fetchall()
    return [r[0] for r in rows]


def get_all_movies():
    """Return list of (movie_id, avg_rating) ordered by avg_rating desc."""
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text('SELECT id, avg_rating FROM movies ORDER BY avg_rating DESC')
        ).fetchall()
    return [(r[0], float(r[1] or 0.0)) for r in rows]


def get_user_rated_movies(user_id):
    """Return set of movie_ids already rated by the user."""
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text('SELECT movie_id FROM ratings WHERE user_id = :uid'),
            {'uid': user_id}
        ).fetchall()
    return {r[0] for r in rows}


def get_movie_title(movie_id):
    """Return movie title or a placeholder string."""
    try:
        with _get_engine().connect() as conn:
            row = conn.execute(
                text('SELECT title FROM movies WHERE id = :id'),
                {'id': movie_id}
            ).fetchone()
        return row[0] if row else f'movie#{movie_id}'
    except Exception:
        return f'movie#{movie_id}'


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def save_recommendations(user_id, recommendations):
    """
    Atomically replace a user's recommendations.

    recommendations: list of (movie_id, score) pairs.
    Deletes all existing recommendations for the user, then inserts new ones.
    """
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    with _get_engine().begin() as conn:
        conn.execute(
            text('DELETE FROM recommendations WHERE user_id = :uid'),
            {'uid': user_id}
        )
        for movie_id, score in recommendations:
            conn.execute(
                text(
                    'INSERT INTO recommendations (user_id, movie_id, score, generated_at) '
                    'VALUES (:uid, :mid, :score, :now)'
                ),
                {'uid': user_id, 'mid': movie_id, 'score': round(float(score), 4), 'now': now}
            )
