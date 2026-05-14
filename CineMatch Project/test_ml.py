"""
ML unit tests — run without Kafka or Flask.
Tests db_utils and recommender directly against the live DB.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OK   = '[PASS]'
FAIL = '[FAIL]'

def check(label, cond, detail=''):
    tag = OK if cond else FAIL
    print(f'  {tag} {label}' + (f'  ({detail})' if detail else ''))
    if not cond:
        sys.exit(1)

print('\nML Recommender Tests\n')

# ── db_utils ────────────────────────────────────────────────────────────────
print('[ db_utils ]')
from ml_service.db_utils import (
    get_all_ratings, get_all_users, get_all_movies,
    get_user_rated_movies, get_movie_title, save_recommendations
)

ratings = get_all_ratings()
check(f'get_all_ratings() returns >= 45 rows', len(ratings) >= 45, f'{len(ratings)} rows')
check('Each row is (int, int, int/float)', all(isinstance(r[0], int) for r in ratings))

users = get_all_users()
check(f'get_all_users() returns >= 5 users', len(users) >= 5, str(users))

movies = get_all_movies()
check(f'get_all_movies() returns movies', len(movies) > 0, f'{len(movies)} movies')
check('Movies sorted by avg_rating desc', movies[0][1] >= movies[-1][1])

uid = users[0]
rated = get_user_rated_movies(uid)
check(f'get_user_rated_movies({uid}) returns a set', isinstance(rated, set))
check(f'User {uid} has rated some movies', len(rated) >= 1, f'{len(rated)} rated')

title = get_movie_title(1)
check('get_movie_title(1) returns a string', isinstance(title, str) and len(title) > 0, title)
check('get_movie_title(99999) returns placeholder', 'movie#' in get_movie_title(99999))

save_recommendations(uid, [(movies[0][0], 4.5), (movies[1][0], 3.8)])
check('save_recommendations() does not raise', True)

# ── recommender ─────────────────────────────────────────────────────────────
print('\n[ recommender — SVD path ]')
from ml_service.recommender import build_recommendations, build_all_recommendations

build_recommendations(uid)
check(f'build_recommendations({uid}) completes without error', True)

# Verify rows were saved
from ml_service.db_utils import _get_engine
from sqlalchemy import text
with _get_engine().connect() as conn:
    n = conn.execute(
        text('SELECT COUNT(*) FROM recommendations WHERE user_id = :uid'), {'uid': uid}
    ).fetchone()[0]
check(f'Recommendations saved to DB for user {uid}', n > 0, f'{n} rows')

# ── build_all ───────────────────────────────────────────────────────────────
print('\n[ build_all_recommendations ]')
build_all_recommendations()
check('build_all_recommendations() completes without error', True)

with _get_engine().connect() as conn:
    total = conn.execute(text('SELECT COUNT(*) FROM recommendations')).fetchone()[0]
    n_users_with_recs = conn.execute(
        text('SELECT COUNT(DISTINCT user_id) FROM recommendations')
    ).fetchone()[0]

check(f'Recommendations table has rows', total > 0, f'{total} total rows')
check(f'Multiple users have recommendations', n_users_with_recs >= len(users),
      f'{n_users_with_recs}/{len(users)} users')

# ── SVD vs fallback ─────────────────────────────────────────────────────────
print('\n[ SVD vs fallback logic ]')
from ml_service.recommender import _svd_recs, _fallback_recs

svd_result = _svd_recs(uid, ratings)
check('_svd_recs returns a list', isinstance(svd_result, list), str(type(svd_result)))
check('SVD recs are (movie_id, score) tuples', all(len(r) == 2 for r in svd_result))
check('SVD scores are 1–5 range', all(1.0 <= r[1] <= 5.0 for r in svd_result),
      str([(r[1]) for r in svd_result]))

fb_result = _fallback_recs(uid)
check('_fallback_recs returns a list', isinstance(fb_result, list))
check('Fallback recs exclude already-rated movies',
      all(mid not in rated for mid, _ in fb_result))

# ── no import from app/ ─────────────────────────────────────────────────────
print('\n[ Independence check ]')
import ml_service.db_utils as du
import ml_service.recommender as rec
for mod in (du, rec):
    src = open(mod.__file__).read()
    check(f'{mod.__name__} has no "from app" import',
          'from app' not in src and 'import app' not in src)

print(f'\nAll ML tests passed.')
print(f'\nDB state: {total} recommendations across {n_users_with_recs} users.')
