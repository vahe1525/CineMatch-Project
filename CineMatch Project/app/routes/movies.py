from flask import Blueprint

movies_bp = Blueprint('movies', __name__, url_prefix='/movies')
