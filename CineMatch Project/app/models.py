from datetime import datetime
from app import db

# USER
class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Relations — մի user-ի բոլոր ratings/watchlist/events
    ratings         = db.relationship('Rating', backref='user', lazy=True)
    watchlist       = db.relationship('Watchlist', backref='user', lazy=True)
    events          = db.relationship('EventLog', backref='user', lazy=True)
    recommendations = db.relationship('Recommendation', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'


# MOVIE
class Movie(db.Model):
    __tablename__ = 'movies'

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    genre       = db.Column(db.String(100))          
    year        = db.Column(db.Integer)
    director    = db.Column(db.String(100))
    description = db.Column(db.Text)
    poster_url  = db.Column(db.String(300))
    avg_rating  = db.Column(db.Float, default=0.0)  

    ratings         = db.relationship('Rating', backref='movie', lazy=True)
    watchlist_items = db.relationship('Watchlist', backref='movie', lazy=True)
    recommendations = db.relationship('Recommendation', backref='movie', lazy=True)

    def __repr__(self):
        return f'<Movie {self.title}>'


class Rating(db.Model):
    __tablename__ = 'ratings'

    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    score    = db.Column(db.Integer, nullable=False)   # 1-5
    rated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'movie_id', name='unique_user_movie_rating'),
    )


# WATCHLIST  (user → movie, "ուզում եմ տեսնել")
class Watchlist(db.Model):
    __tablename__ = 'watchlist'

    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


# EVENT LOG  (ամեն user action)
class EventLog(db.Model):
    __tablename__ = 'events_log'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)

    payload    = db.Column(db.JSON)
    # Օրինակ՝ {"movie_id": 12, "score": 4}
    #          {"query": "Nolan"}

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# RECOMMENDATION  (ML service-ը գրում է, Flask-ը կարդում)
class Recommendation(db.Model):
    __tablename__ = 'recommendations'

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id     = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    score        = db.Column(db.Float)     # ML-ի վստահության գնահատական
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)