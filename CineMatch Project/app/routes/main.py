import random
from flask import Blueprint, render_template
from flask_login import current_user

from app.models import Movie, Rating, Recommendation, Watchlist

main_bp = Blueprint('main', __name__, url_prefix='')


@main_bp.route('/')
def index():
    if not current_user.is_authenticated:
        # ── Anonymous ───────────────────────────────────────────────────────
        top_rated = (Movie.query
                     .filter(Movie.avg_rating > 0)
                     .order_by(Movie.avg_rating.desc())
                     .limit(20).all())
        popular_by_genre = _popular_by_genre(5)
        return render_template('index.html',
                               mode='anonymous',
                               top_rated=top_rated,
                               popular_by_genre=popular_by_genre,
                               featured=top_rated[0] if top_rated else None)

    rating_count = Rating.query.filter_by(user_id=current_user.id).count()

    if rating_count < 5:
        # ── New user ────────────────────────────────────────────────────────
        already_rated = {r.movie_id for r in
                         Rating.query.filter_by(user_id=current_user.id).all()}
        all_movies = Movie.query.filter(Movie.poster_url != '').all()
        genres_seen = set()
        onboarding = []
        for m in sorted(all_movies, key=lambda x: -x.avg_rating):
            if m.id in already_rated:
                continue
            primary_genre = m.genre.split(',')[0].strip() if m.genre else 'Other'
            if primary_genre not in genres_seen:
                genres_seen.add(primary_genre)
                onboarding.append(m)
            if len(onboarding) == 10:
                break

        top_rated = (Movie.query
                     .filter(Movie.avg_rating > 0)
                     .order_by(Movie.avg_rating.desc())
                     .limit(20).all())
        popular_by_genre = _popular_by_genre(5)

        return render_template('index.html',
                               mode='new_user',
                               top_rated=top_rated,
                               popular_by_genre=popular_by_genre,
                               onboarding=onboarding,
                               featured=top_rated[0] if top_rated else None)

    # ── Returning user ───────────────────────────────────────────────────────
    recommendations = (Recommendation.query
                       .filter_by(user_id=current_user.id)
                       .order_by(Recommendation.score.desc())
                       .limit(20).all())

    top_rated = (Movie.query
                 .filter(Movie.avg_rating > 0)
                 .order_by(Movie.avg_rating.desc())
                 .limit(20).all())

    # Check if we have Recommendation ORM objects or Movie objects (fallback)
    recs_are_objects = recommendations and hasattr(recommendations[0], 'movie')

    if not recs_are_objects and not recommendations:
        recommendations = top_rated[:20]
        recs_are_objects = False

    # "Because you liked …" row
    because_movies = []
    top_user_rating = (Rating.query
                       .filter_by(user_id=current_user.id)
                       .order_by(Rating.score.desc())
                       .first())
    because_label = ''
    if top_user_rating:
        liked_movie = Movie.query.get(top_user_rating.movie_id)
        if liked_movie:
            because_label = liked_movie.title
            primary_genre = liked_movie.genre.split(',')[0].strip()
            because_movies = (Movie.query
                              .filter(Movie.genre.like(f'%{primary_genre}%'),
                                      Movie.id != liked_movie.id)
                              .order_by(Movie.avg_rating.desc())
                              .limit(20).all())

    # Hero: random recommendation with a poster
    featured = None
    if recs_are_objects:
        pool = [r.movie for r in recommendations if r.movie and r.movie.poster_url]
    else:
        pool = [m for m in recommendations if m and m.poster_url]
    if pool:
        featured = random.choice(pool[:5])

    return render_template('index.html',
                           mode='returning',
                           recommendations=recommendations,
                           because_movies=because_movies,
                           because_label=because_label,
                           top_rated=top_rated,
                           featured=featured)


def _popular_by_genre(limit_per_genre=5):
    """Return dict {genre: [movies]} for top 5 genres by movie count."""
    all_movies = Movie.query.filter(Movie.avg_rating > 0, Movie.poster_url != '').all()
    genre_buckets: dict[str, list] = {}
    for m in all_movies:
        primary = m.genre.split(',')[0].strip() if m.genre else 'Other'
        genre_buckets.setdefault(primary, []).append(m)

    # Sort each bucket by avg_rating
    result = {}
    sorted_genres = sorted(genre_buckets.items(), key=lambda x: -len(x[1]))[:6]
    for genre, movies in sorted_genres:
        result[genre] = sorted(movies, key=lambda m: -m.avg_rating)[:limit_per_genre]
    return result
