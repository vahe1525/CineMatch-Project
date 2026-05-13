"""
Seed script — run from the project root:
    python seed.py

Fully idempotent: safe to re-run. Adds movies, users, ratings if missing.
Phase 6 extension adds user6-user8 and tops up movies to >= 3 ratings each.
"""
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db, bcrypt
from app.models import Movie, User, Rating, EventLog

MOVIES = [
    {
        'title': 'The Shawshank Redemption', 'genre': 'Drama', 'year': 1994,
        'director': 'Frank Darabont',
        'description': 'Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency.',
    },
    {
        'title': 'The Godfather', 'genre': 'Crime', 'year': 1972,
        'director': 'Francis Ford Coppola',
        'description': "An organized crime dynasty's aging patriarch transfers control of his clandestine empire to his reluctant son.",
    },
    {
        'title': 'The Dark Knight', 'genre': 'Action', 'year': 2008,
        'director': 'Christopher Nolan',
        'description': 'Batman faces the Joker, a criminal mastermind who plunges Gotham City into anarchy.',
    },
    {
        'title': 'Pulp Fiction', 'genre': 'Crime', 'year': 1994,
        'director': 'Quentin Tarantino',
        'description': "The lives of two mob hitmen, a boxer, a gangster, and his wife intertwine in four tales of violence and redemption.",
    },
    {
        'title': 'Forrest Gump', 'genre': 'Drama', 'year': 1994,
        'director': 'Robert Zemeckis',
        'description': 'The presidencies of Kennedy and Johnson, Vietnam, Watergate, and other historical events unfold through the perspective of an Alabama man with an IQ of 75.',
    },
    {
        'title': 'Inception', 'genre': 'Sci-Fi', 'year': 2010,
        'director': 'Christopher Nolan',
        'description': 'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a CEO.',
    },
    {
        'title': 'The Matrix', 'genre': 'Sci-Fi', 'year': 1999,
        'director': 'Lana Wachowski',
        'description': 'A computer programmer discovers that reality as he knows it is a simulation and joins a rebellion to break free.',
    },
    {
        'title': 'Goodfellas', 'genre': 'Crime', 'year': 1990,
        'director': 'Martin Scorsese',
        'description': 'The story of Henry Hill and his life in the mob, covering his career from the 1950s through 1980.',
    },
    {
        'title': 'The Silence of the Lambs', 'genre': 'Thriller', 'year': 1991,
        'director': 'Jonathan Demme',
        'description': 'A young FBI cadet must receive the help of an incarcerated and manipulative cannibal killer to catch another serial killer.',
    },
    {
        'title': "Schindler's List", 'genre': 'Drama', 'year': 1993,
        'director': 'Steven Spielberg',
        'description': 'In German-occupied Poland during World War II, industrialist Oskar Schindler gradually becomes concerned for his Jewish workforce after witnessing their persecution.',
    },
    {
        'title': 'Interstellar', 'genre': 'Sci-Fi', 'year': 2014,
        'director': 'Christopher Nolan',
        'description': "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
    },
    {
        'title': 'Fight Club', 'genre': 'Drama', 'year': 1999,
        'director': 'David Fincher',
        'description': 'An insomniac office worker and a soap salesman build a global organization to serve as an outlet for male aggression.',
    },
    {
        'title': 'The Lord of the Rings: The Fellowship of the Ring', 'genre': 'Fantasy', 'year': 2001,
        'director': 'Peter Jackson',
        'description': 'A meek Hobbit from the Shire and eight companions set out on a journey to destroy the powerful One Ring and save Middle-earth.',
    },
    {
        'title': 'Star Wars: A New Hope', 'genre': 'Sci-Fi', 'year': 1977,
        'director': 'George Lucas',
        'description': 'Luke Skywalker joins forces with a Jedi Knight, a cocky pilot, a Wookiee, and two droids to save the galaxy from the Empire.',
    },
    {
        'title': 'The Lion King', 'genre': 'Animation', 'year': 1994,
        'director': 'Roger Allers',
        'description': 'Lion prince Simba and his father are targeted by his scheming uncle, who wants to ascend the throne himself.',
    },
    {
        'title': 'Gladiator', 'genre': 'Action', 'year': 2000,
        'director': 'Ridley Scott',
        'description': 'A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family and sent him into slavery.',
    },
    {
        'title': 'The Departed', 'genre': 'Crime', 'year': 2006,
        'director': 'Martin Scorsese',
        'description': 'An undercover cop and a mole in the police attempt to identify each other while simultaneously infiltrating the Irish mob in South Boston.',
    },
    {
        'title': 'Whiplash', 'genre': 'Drama', 'year': 2014,
        'director': 'Damien Chazelle',
        'description': "A promising young drummer enrolls at a cut-throat music conservatory where his ruthless teacher will stop at nothing to realize a student's potential.",
    },
    {
        'title': 'Parasite', 'genre': 'Thriller', 'year': 2019,
        'director': 'Bong Joon-ho',
        'description': 'Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.',
    },
    {
        'title': 'Everything Everywhere All at Once', 'genre': 'Sci-Fi', 'year': 2022,
        'director': 'Daniel Kwan',
        'description': 'A middle-aged Chinese immigrant is swept up in an insane adventure where she alone can save the multiverse by exploring other universes.',
    },
]

USERS = [
    {'username': f'user{i}', 'email': f'user{i}@cinematch.dev', 'password': 'password123'}
    for i in range(1, 9)   # user1 through user8
]


def seed():
    app = create_app()
    with app.app_context():
        from sqlalchemy import func

        # ── Movies ──────────────────────────────────────────────────────────
        print('Ensuring movies...')
        movies = []
        movies_added = 0
        for data in MOVIES:
            m = Movie.query.filter_by(title=data['title']).first()
            if not m:
                m = Movie(
                    title=data['title'],
                    genre=data['genre'],
                    year=data['year'],
                    director=data['director'],
                    description=data['description'],
                    poster_url='',
                    avg_rating=0.0,
                )
                db.session.add(m)
                movies_added += 1
            movies.append(m)
        db.session.commit()
        print(f'  {movies_added} new movies added ({len(movies)} total).')

        # ── Users ────────────────────────────────────────────────────────────
        print('Ensuring users...')
        users_added = 0
        all_users = []
        for data in USERS:
            u = User.query.filter_by(email=data['email']).first()
            if not u:
                pw_hash = bcrypt.generate_password_hash(data['password']).decode('utf-8')
                u = User(username=data['username'],
                         email=data['email'],
                         password_hash=pw_hash)
                db.session.add(u)
                users_added += 1
            all_users.append(u)
        db.session.commit()
        print(f'  {users_added} new users added ({len(all_users)} total).')

        # ── Ratings for each user ─────────────────────────────────────────
        print('Adding ratings...')
        ratings_added = 0
        for u in all_users:
            already_rated = {r.movie_id for r in Rating.query.filter_by(user_id=u.id).all()}
            unrated = [m for m in movies if m.id not in already_rated]
            if not unrated:
                continue
            n = min(random.randint(10, 15), len(unrated))
            for m in random.sample(unrated, n):
                score = random.randint(1, 5)
                db.session.add(Rating(user_id=u.id, movie_id=m.id, score=score))
                ratings_added += 1
        db.session.commit()
        print(f'  {ratings_added} new ratings added.')

        # ── Ensure every movie has >= 3 ratings ──────────────────────────
        print('Topping up movies to 3+ ratings...')
        topped = 0
        for m in movies:
            count = Rating.query.filter_by(movie_id=m.id).count()
            if count >= 3:
                continue
            raters = {r.user_id for r in Rating.query.filter_by(movie_id=m.id).all()}
            candidates = [u for u in all_users if u.id not in raters]
            needed = 3 - count
            for u in random.sample(candidates, min(needed, len(candidates))):
                score = random.randint(3, 5)
                db.session.add(Rating(user_id=u.id, movie_id=m.id, score=score))
                topped += 1
        db.session.commit()
        if topped:
            print(f'  {topped} top-up ratings added.')

        # ── Recalculate avg_rating ────────────────────────────────────────
        print('Recalculating avg_rating for all movies...')
        for m in movies:
            avg = (db.session.query(func.avg(Rating.score))
                   .filter(Rating.movie_id == m.id)
                   .scalar())
            m.avg_rating = round(float(avg), 2) if avg else 0.0
        db.session.commit()

        print(f'\nSeed complete:')
        print(f'  Movies  : {Movie.query.count()}')
        print(f'  Users   : {User.query.count()}')
        print(f'  Ratings : {Rating.query.count()}')


if __name__ == '__main__':
    seed()
