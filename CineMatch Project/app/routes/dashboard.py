from flask import Blueprint, render_template
from flask_login import login_required, current_user

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
