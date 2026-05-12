from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app import db
from app.models import Movie, Rating, Watchlist
from app.utils import log_event

movies_bp = Blueprint('movies', __name__, url_prefix='/movies')

_PER_PAGE = 12


@movies_bp.route('/')
def catalog():
    page = request.args.get('page', 1, type=int)
    pagination = (Movie.query
                  .order_by(Movie.title)
                  .paginate(page=page, per_page=_PER_PAGE, error_out=False))
    return render_template('movies/catalog.html',
                           movies=pagination.items,
                           pagination=pagination)


@movies_bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        pattern = f'%{q}%'
        results = (Movie.query
                   .filter(or_(Movie.title.ilike(pattern),
                               Movie.genre.ilike(pattern)))
                   .order_by(Movie.title)
                   .all())
        if current_user.is_authenticated:
            log_event(current_user.id, 'user.searched', {'query': q})
    return render_template('movies/search.html', results=results, q=q)


@movies_bp.route('/<int:id>')
def detail(id):
    movie = Movie.query.get_or_404(id)
    user_rating  = None
    in_watchlist = False
    if current_user.is_authenticated:
        user_rating  = Rating.query.filter_by(user_id=current_user.id, movie_id=id).first()
        in_watchlist = Watchlist.query.filter_by(user_id=current_user.id, movie_id=id).first() is not None
        log_event(current_user.id, 'user.clicked', {'movie_id': id})
    return render_template('movies/detail.html',
                           movie=movie,
                           user_rating=user_rating,
                           in_watchlist=in_watchlist)


@movies_bp.route('/<int:id>/rate', methods=['POST'])
@login_required
def rate(id):
    movie = Movie.query.get_or_404(id)

    try:
        score = int(request.form.get('score', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid score'}), 400

    if not 1 <= score <= 5:
        return jsonify({'success': False, 'error': 'Score must be 1–5'}), 400

    existing = Rating.query.filter_by(user_id=current_user.id, movie_id=id).first()
    if existing:
        existing.score = score
    else:
        db.session.add(Rating(user_id=current_user.id, movie_id=id, score=score))

    db.session.flush()
    avg = (db.session.query(func.avg(Rating.score))
           .filter(Rating.movie_id == id)
           .scalar())
    movie.avg_rating = round(float(avg), 2)
    db.session.commit()

    log_event(current_user.id, 'user.rated', {'movie_id': id, 'score': score})
    return jsonify({'success': True, 'avg_rating': movie.avg_rating})


@movies_bp.route('/<int:id>/watchlist', methods=['POST'])
@login_required
def toggle_watchlist(id):
    Movie.query.get_or_404(id)

    existing = Watchlist.query.filter_by(user_id=current_user.id, movie_id=id).first()
    if existing:
        db.session.delete(existing)
        action       = 'remove'
        in_watchlist = False
    else:
        db.session.add(Watchlist(user_id=current_user.id, movie_id=id))
        action       = 'add'
        in_watchlist = True

    db.session.commit()
    log_event(current_user.id, 'user.watched', {'movie_id': id, 'action': action})
    return jsonify({'success': True, 'in_watchlist': in_watchlist})
