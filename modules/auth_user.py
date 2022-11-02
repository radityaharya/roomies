import jwt
from flask import request, redirect, url_for, render_template, flash
from werkzeug.security import check_password_hash, generate_password_hash
import bson
import logging

logger = logging.getLogger("roomies")

def signup(user_collection, request):
    """
    It takes a request object and creates a new user in the database.
    
    Args:
      user_collection: The user collection in the database.
      request: The request object.
    
    Returns:
      A redirect to the login page.
    """
    if request.method == "POST":
        user = user_collection.find_one({"email": request.form["email"]})
        if user is not None:
            flash("Email already exists")
            return redirect(url_for("signup"))
        user_collection.insert_one(
            {
                "email": request.form["email"],
                "password": generate_password_hash(request.form["password"]),
                "first_name": request.form["firstname"],
                "last_name": request.form["lastname"],
                "province": request.form["province"],
            }
        )
        return redirect(url_for("login"))
    return render_template("signup.jinja")


def generate_token(user_id):
    """
    It takes a user_id and generates a token.
    
    Args:
      user_id: The user_id of the user.
    
    Returns:
      A token.
    """
    # TODO: Add expiry date to token
    user_id = str(user_id)
    return jwt.encode({"user_id": user_id}, "secret", algorithm="HS256")

def decode_token(token):
    """
    It takes a token and decodes it.
    
    Args:
      token: The token.
    
    Returns:
      The decoded token.
    """
    # TODO: Read expiry date from token
    return jwt.decode(token, "secret", algorithms=["HS256"])

def set_user_cookie(user_id, response):
    """
    It takes a user_id and sets the user_id cookie.
    
    Args:
      user_id: The user_id of the user.
    
    Returns:
      A redirect to the index page.
    """
    response.set_cookie("token", generate_token(user_id))
    return response

def login(user_collection, request):
    """
    It takes a request object and logs the user in.
    
    Args:
      user_collection: The user collection in the database.
      request: The request object.
    
    Returns:
      A redirect to the index page.
    """
    if request.method == "POST":
        # use JWT
        user = user_collection.find_one({"email": request.form["email"]})
        if user is None:
            flash("Email not found")
            return redirect(url_for("login"))
        if not check_password_hash(user["password"], request.form["password"]):
            flash("Wrong password")
            return redirect(url_for("login"))
        return set_user_cookie(user["_id"], redirect("/"))
    return render_template("login.jinja")

# wrapper decorator to check if user is authenticated
def is_authenticated(request, user_collection):
    """
    It takes a request object and checks if the user is authenticated.
    
    Args:
      request: The request object.
      user_collection: The user collection in the database.
    
    Returns:
      A redirect to the login page.
    """
    def wrapper(func):
        def wrapped(*args, **kwargs):
            if "token" not in request.cookies:
                return redirect(url_for("login"))
            try:
                user_id = decode_token(request.cookies["token"])["user_id"]
            except jwt.exceptions.DecodeError:
                return redirect(url_for("login"))
            user = user_collection.find_one({"_id": bson.ObjectId(user_id)})
            if user is None:
                return redirect(url_for("login"))
            return func(*args, **kwargs)
        return wrapped
    return wrapper

def is_logged_in(request):
    """
    It takes a request object and checks if the user is logged in.
    
    Args:
      request: The request object.
    
    Returns:
      A boolean.
    """
    if "token" not in request.cookies:
        logger.info("User is not logged in")
        return False
    try:
        user_id = decode_token(request.cookies["token"])["user_id"]
    except jwt.exceptions.DecodeError:
        logger.info("Token is invalid")
        return False
    logger.info("User is logged in")
    return True