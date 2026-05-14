"""
Fetch 200 popular movies from TMDB and populate the database.
Run from project root:  python fetch_movies.py

Also creates the 8 default demo users if they don't exist yet.
Handles rate limiting with 0.25s delay between requests.
"""
import os
import sys
import time
import random
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db, bcrypt
from app.models import Movie, User, Rating, Watchlist, Recommendation, EventLog
from sqlalchemy import func

TMDB_API_KEY = '8876bacb63d20fc212f583300537f84b'
BASE_URL = 'https://api.themoviedb.org/3'
POSTER_BASE = 'https://image.tmdb.org/t/p/w500'


def get_genre_map():
    r = requests.get(f'{BASE_URL}/genre/movie/list',
                     params={'api_key': TMDB_API_KEY, 'language': 'en-US'},
                     timeout=10)
    r.raise_for_status()
    return {g['id']: g['name'] for g in r.json()['genres']}


def get_credits(tmdb_movie_id):
    try:
        r = requests.get(f'{BASE_URL}/movie/{tmdb_movie_id}/credits',
                         params={'api_key': TMDB_API_KEY}, timeout=10)
        time.sleep(0.25)
        if r.status_code != 200:
            return '', ''
        data = r.json()
        director = next(
            (c['name'] for c in data.get('crew', []) if c['job'] == 'Director'),
            ''
        )
        cast = ', '.join(c['name'] for c in data.get('cast', [])[:3])
        return director, cast
    except Exception as exc:
        print(f'    [warn] credits fetch failed: {exc}')
        return '', ''


def fetch_all_popular(genre_map):
    movies = []
    for page in range(1, 11):
        print(f'  Page {page}/10 ...')
        r = requests.get(f'{BASE_URL}/movie/popular',
                         params={'api_key': TMDB_API_KEY, 'page': page,
                                 'language': 'en-US'},
                         timeout=10)
        r.raise_for_status()
        movies.extend(r.json().get('results', []))
        time.sleep(0.25)
    return movies


def main():
    app = create_app()
    with app.app_context():
        print('Fetching genre map from TMDB...')
        genre_map = get_genre_map()
        time.sleep(0.25)

        print('Fetching 200 popular movies (10 pages × 20)...')
        raw_movies = fetch_all_popular(genre_map)
        print(f'Got {len(raw_movies)} raw entries.')

        # Deduplicate by tmdb_id, keep first 200
        seen_ids = set()
        unique_movies = []
        for m in raw_movies:
            if m['id'] not in seen_ids:
                seen_ids.add(m['id'])
                unique_movies.append(m)
            if len(unique_movies) == 200:
                break

        print(f'Unique movies to insert: {len(unique_movies)}')

        # ── Clear existing data ──────────────────────────────────────────────
        print('Clearing existing movies, ratings, recommendations...')
        Recommendation.query.delete()
        Rating.query.delete()
        Watchlist.query.delete()
        EventLog.query.delete()
        Movie.query.delete()
        db.session.commit()

        # ── Insert new movies ────────────────────────────────────────────────
        print('Inserting new movies with credits...')
        inserted = 0
        for m_data in unique_movies:
            tmdb_id = m_data['id']

            genre_ids = m_data.get('genre_ids', [])
            genre_names = [genre_map[gid] for gid in genre_ids[:2] if gid in genre_map]
            genre = ', '.join(genre_names) if genre_names else 'Other'

            release_date = m_data.get('release_date', '')
            year = int(release_date[:4]) if len(release_date) >= 4 else None

            poster_path = m_data.get('poster_path')
            poster_url = (POSTER_BASE + poster_path) if poster_path else ''

            print(f'  [{inserted + 1:3d}/200] {m_data["title"][:50]}')
            director, cast = get_credits(tmdb_id)

            # TMDB vote_average is 0-10; convert to 0-5 scale
            tmdb_avg = m_data.get('vote_average', 0)
            avg_rating = round(tmdb_avg / 2, 2)

            movie = Movie(
                tmdb_id=tmdb_id,
                title=m_data['title'],
                genre=genre,
                year=year,
                director=director,
                description=m_data.get('overview', ''),
                poster_url=poster_url,
                avg_rating=avg_rating,
                runtime=None,
                cast=cast,
            )
            db.session.add(movie)
            inserted += 1

            if inserted % 25 == 0:
                db.session.commit()
                print(f'  -- committed {inserted} so far --')

        db.session.commit()
        print(f'Inserted {inserted} movies.')

        # ── Ensure demo users exist ──────────────────────────────────────────
        print('Ensuring demo users...')
        demo_users = [
            {'username': f'user{i}', 'email': f'user{i}@cinematch.dev', 'password': 'password123'}
            for i in range(1, 9)
        ]
        users_added = 0
        for data in demo_users:
            if not User.query.filter_by(email=data['email']).first():
                pw_hash = bcrypt.generate_password_hash(data['password']).decode('utf-8')
                db.session.add(User(username=data['username'],
                                   email=data['email'],
                                   password_hash=pw_hash))
                users_added += 1
        db.session.commit()
        if users_added:
            print(f'  {users_added} new demo users created (password: password123).')

        # ── Re-seed ratings for existing users ──────────────────────────────
        users = User.query.all()
        movies = Movie.query.all()

        if not users:
            print('No users found — register via the web UI first.')
        else:
            print(f'Re-seeding ratings for {len(users)} users over {len(movies)} movies...')
            ratings_added = 0
            for u in users:
                n = min(random.randint(15, 25), len(movies))
                sample = random.sample(movies, n)
                for m in sample:
                    score = random.randint(1, 5)
                    db.session.add(Rating(user_id=u.id, movie_id=m.id, score=score))
                    ratings_added += 1
            db.session.commit()
            print(f'  {ratings_added} ratings added.')

            # Ensure every movie has >= 3 ratings
            print('Topping up movies to >= 3 ratings...')
            topped = 0
            for m in movies:
                count = Rating.query.filter_by(movie_id=m.id).count()
                if count >= 3:
                    continue
                raters = {r.user_id for r in Rating.query.filter_by(movie_id=m.id).all()}
                candidates = [u for u in users if u.id not in raters]
                needed = 3 - count
                for u in random.sample(candidates, min(needed, len(candidates))):
                    db.session.add(Rating(user_id=u.id, movie_id=m.id, score=random.randint(3, 5)))
                    topped += 1
            db.session.commit()
            if topped:
                print(f'  {topped} top-up ratings added.')

            # Recalculate avg_rating from user ratings (overrides TMDB value)
            print('Recalculating avg_rating from user data...')
            for m in movies:
                avg = (db.session.query(func.avg(Rating.score))
                       .filter(Rating.movie_id == m.id).scalar())
                m.avg_rating = round(float(avg), 2) if avg else 0.0
            db.session.commit()

        print('\nDone!')
        print(f'  Movies  : {Movie.query.count()}')
        print(f'  Users   : {User.query.count()}')
        print(f'  Ratings : {Rating.query.count()}')


if __name__ == '__main__':
    main()
