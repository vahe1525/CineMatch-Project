"""
CineMatch ML — Collaborative Filtering Recommender

Algorithm:
  - If DB has >= 10 ratings: mean-centred SVD (scipy.sparse.linalg.svds)
  - Otherwise: fallback to top-rated movies the user hasn't seen

No Flask dependencies — uses ml_service.db_utils for all DB access.
"""
import logging
import numpy as np

from ml_service.db_utils import (
    get_all_ratings,
    get_all_users,
    get_all_movies,
    get_user_rated_movies,
    save_recommendations,
)

logger = logging.getLogger(__name__)

_MIN_RATINGS_FOR_SVD = 10
_TOP_N = 10
_SVD_COMPONENTS = 20        # capped later to min(n_users, n_movies) - 1


# ---------------------------------------------------------------------------
# Fallback: top-rated movies the user hasn't seen
# ---------------------------------------------------------------------------

def _fallback_recs(user_id):
    """Return top-rated movies the user hasn't yet rated."""
    rated = get_user_rated_movies(user_id)
    movies = get_all_movies()          # already sorted by avg_rating desc
    recs = [(mid, score) for mid, score in movies if mid not in rated]
    return recs[:_TOP_N]


# ---------------------------------------------------------------------------
# Core SVD collaborative filter
# ---------------------------------------------------------------------------

def _svd_recs(user_id, ratings):
    """
    Build recommendations via mean-centred SVD.
    Returns list of (movie_id, predicted_score) for the target user.
    """
    from scipy.sparse import csr_matrix
    from scipy.sparse.linalg import svds

    # Build index maps
    users  = sorted({r[0] for r in ratings})
    movies = sorted({r[1] for r in ratings})
    uid2i  = {u: i for i, u in enumerate(users)}
    mid2j  = {m: j for j, m in enumerate(movies)}

    n_users, n_movies = len(users), len(movies)

    # Dense user-item matrix (0 = not rated)
    R = np.zeros((n_users, n_movies), dtype=np.float64)
    for u, m, s in ratings:
        R[uid2i[u], mid2j[m]] = s

    # Mean-centre (per user, over rated items only)
    user_means = np.zeros(n_users)
    R_c = R.copy()
    for i in range(n_users):
        mask = R_c[i] != 0
        if mask.any():
            user_means[i] = R_c[i, mask].mean()
            R_c[i, mask] -= user_means[i]

    # SVD — k must be < min(n_users, n_movies)
    k = min(_SVD_COMPONENTS, min(n_users, n_movies) - 1)
    if k < 1:
        return None                   # not enough distinct users/movies

    U, sigma, Vt = svds(csr_matrix(R_c), k=k)

    # Reconstruct full prediction matrix
    predicted = U @ np.diag(sigma) @ Vt + user_means.reshape(-1, 1)
    predicted = np.clip(predicted, 1.0, 5.0)

    # Extract predictions for the target user
    if user_id not in uid2i:
        return None                   # user has no ratings in this snapshot

    ui = uid2i[user_id]
    user_row = predicted[ui]

    rated = get_user_rated_movies(user_id)
    recs = [
        (movies[j], float(user_row[j]))
        for j in range(n_movies)
        if movies[j] not in rated
    ]
    recs.sort(key=lambda x: x[1], reverse=True)
    return recs[:_TOP_N]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_recommendations(user_id):
    """
    Compute and persist top-10 recommendations for a single user.
    Falls back to top-rated movies if SVD cannot run.
    """
    try:
        ratings = get_all_ratings()

        if len(ratings) >= _MIN_RATINGS_FOR_SVD:
            recs = _svd_recs(user_id, ratings)
            if recs is None:
                logger.debug('SVD returned None for user %s — using fallback', user_id)
                recs = _fallback_recs(user_id)
            source = 'SVD'
        else:
            recs = _fallback_recs(user_id)
            source = 'top-rated fallback'

        if recs:
            save_recommendations(user_id, recs)
            logger.info(
                'Recommendations saved for user %s  [%s, %d items]',
                user_id, source, len(recs)
            )
        else:
            logger.debug('No recommendations generated for user %s', user_id)

    except Exception as exc:
        logger.warning('build_recommendations failed for user %s: %s', user_id, exc)


def build_all_recommendations():
    """
    Rebuild recommendations for every user in the DB.
    Called once on consumer startup and can be scheduled periodically.
    """
    logger.info('Building initial recommendations for all users...')
    users = get_all_users()
    if not users:
        logger.info('No users in DB — skipping.')
        return

    success = 0
    for uid in users:
        try:
            build_recommendations(uid)
            success += 1
        except Exception as exc:
            logger.warning('Failed for user %s: %s', uid, exc)

    logger.info('Done. Recommendations saved for %d users.', success)
