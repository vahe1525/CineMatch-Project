from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

from app import db
from app.models import Recommendation, Rating, Watchlist

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    recommendations = (Recommendation.query
                       .filter_by(user_id=current_user.id)
                       .order_by(Recommendation.score.desc())
                       .limit(10)
                       .all())

    recent_ratings = (Rating.query
                      .filter_by(user_id=current_user.id)
                      .order_by(Rating.rated_at.desc())
                      .limit(5)
                      .all())

    watchlist = (Watchlist.query
                 .filter_by(user_id=current_user.id)
                 .order_by(Watchlist.added_at.desc())
                 .limit(5)
                 .all())

    return render_template('dashboard/index.html',
                           recommendations=recommendations,
                           recent_ratings=recent_ratings,
                           watchlist=watchlist)


@dashboard_bp.route('/profile')
@login_required
def profile():
    all_ratings = (Rating.query
                   .filter_by(user_id=current_user.id)
                   .order_by(Rating.rated_at.desc())
                   .all())
    watchlist_count = Watchlist.query.filter_by(user_id=current_user.id).count()
    avg_score = None
    if all_ratings:
        avg_score = round(sum(r.score for r in all_ratings) / len(all_ratings), 1)

    return render_template('dashboard/profile.html',
                           all_ratings=all_ratings,
                           watchlist_count=watchlist_count,
                           avg_score=avg_score)


@dashboard_bp.route('/watchlist/<int:movie_id>/remove', methods=['POST'])
@login_required
def remove_watchlist(movie_id):
    item = Watchlist.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return jsonify({'success': True})
