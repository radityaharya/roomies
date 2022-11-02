import os

import bson
import geopy.distance
import numpy as np
import pymongo
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
)
from flask_caching import Cache

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.serving import WSGIRequestHandler
import util

load_dotenv()

app = Flask("roomies")
app.secret_key = os.urandom(24)
client = pymongo.MongoClient(os.getenv("MONGO_URI"))

db = client.roomies
users = db.users

cache = Cache(app, config={"CACHE_TYPE": "SimpleCache"})

# TODO: Change this to use JWT
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = db.users.find_one({"email": request.form["email"]})
        if user is None:
            flash("Email not found")
            return redirect(url_for("login"))
        if not check_password_hash(user["password"], request.form["password"]):
            flash("Wrong password")
            return redirect(url_for("login"))
        return util.set_user_cookie(user["_id"])
    return render_template("login.jinja")

# TODO: Change this to use JWT
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        user = db.users.find_one({"email": request.form["email"]})
        if user is not None:
            flash("Email already exists")
            return redirect(url_for("signup"))
        db.users.insert_one(
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


@app.route("/")
@cache.cached(timeout=300, query_string=True)
def home():
    """
    Returns:
      the render_template function, which is a function that renders a template.
    """
    return render_template("index.jinja")


@app.route("/properties")
@cache.cached(timeout=50, query_string=True)
def index():
    """
    Returns:
      a rendered template of the home page.
    """
    user_id = request.cookies.get("user_id")
    if user_id:
        user = users.find_one({"_id": bson.ObjectId(user_id)})
    else:
        return redirect(url_for("login"))
    properties = db.properties.find()
    user_ip = util.get_request_ip(request)
    user_coordinates = util.get_coordinates(user_ip)
    properties = [property for property in properties if "coordinates" in property]
    property_coordinates = [
        (property["coordinates"][1], property["coordinates"][0])
        for property in properties
    ]
    distances = [
        geopy.distance.distance(user_coordinates, property_coordinate).km
        for property_coordinate in property_coordinates
    ]
    properties = [properties[i] for i in np.argsort(distances)]
    properties = properties[:5]
    near_you = []
    for property_item in properties:

        data_near_you = {
            "id": str(property_item["_id"]),
            "name": property_item["name"],
            "location": property_item["location"],
            "price": util.price_format(property_item["price"]),
            "icons": util.get_icon_from_facilities(property_item["fasilitas"]),
            "pictures": property_item["pictures"],
        }
        near_you.append(data_near_you)

    data = {
        "near_you": near_you,
        "top": near_you,
    }

    return render_template("home.jinja", properties=data["near_you"], user=user)


@app.route("/property/<property_id>", methods=["GET"])
@cache.cached(timeout=50, query_string=True)
def details(property_id):
    property_item = db.properties.find_one({"_id": bson.ObjectId(property_id)})
    if property is None:
        return redirect(url_for("index"))

    data = {
        "name": property_item["name"],
        "location": property_item["location"],
        "price": util.price_format(property_item["price"]),
        "fasilitas": property_item["fasilitas"],
        "pictures": property_item["pictures"],
        "description": property_item["description"],
        "icons": util.get_icon_from_facilities(property_item["fasilitas"]),
    }

    return render_template("property.jinja", property=data)


@app.route("/search", methods=["GET", "POST"])
def search():
    query = request.args.get("query")
    filter_item = request.args.get("filter")
    sort = request.args.get("sort")
    limit = request.args.get("limit")
    # TODO: Make this a function
    if query is None:
        query = ""
    if filter is None:
        filter_item = "all"
    if sort is None:
        sort = "location-asc"
    if limit is None:
        limit = 50
    else:
        limit = int(limit)
    sort = sort.split("-")
    sort_by = sort[0]
    sort_order = sort[1]
    
    # TODO: Make this a function
    if sort_order == "asc":
        sort_order = pymongo.ASCENDING
    else:
        sort_order = pymongo.DESCENDING

    # TODO: Make this a function
    if sort_by == "location" or query == "":

        user_ip = util.get_request_ip(request)
        user_coordinates = util.get_coordinates(user_ip)
        if query != "":
            properties = db.properties.find({"$text": {"$search": query}})
        else:
            properties = db.properties.find()
            sort_order = pymongo.ASCENDING
        properties = [property for property in properties if "coordinates" in property]
        property_coordinates = [
            (property["coordinates"][1], property["coordinates"][0])
            for property in properties
        ]
        distances = [
            geopy.distance.distance(user_coordinates, property_coordinate).km
            for property_coordinate in property_coordinates
        ]
        if sort_order == pymongo.ASCENDING:
            properties = [properties[i] for i in np.argsort(distances)]
        else:
            properties = [properties[i] for i in np.argsort(distances)[::-1]]
    # TODO: Make this a function
    elif sort_by == "price":
        print("price")
        properties = (
            db.properties.find({"$text": {"$search": query}})
            .sort("price", sort_order)
            .limit(limit)
        )
    else:
        properties = (
            db.properties.find({"$text": {"$search": query}})
            .sort("name", sort_order)
            .limit(limit)
        )

    results = []
    for property_item in properties:
        data_near_you = {
            "id": str(property_item["_id"]),
            "name": property_item["name"],
            "location": property_item["location"],
            "price": util.price_format(property_item["price"]),
            "icons": [
                f"https://r2.radityaharya.me/{icon}-solid.svg"
                for icon in property_item["fasilitas"]
            ],
            "pictures": property_item["pictures"],
        }
        results.append(data_near_you)
    return render_template("search.jinja", properties=results)


@app.route("/static/img/<path:filename>")
def static_img(filename):
    # file_path = os.path.join(app.root_path, "static", "img", filename)
    return send_from_directory("static/img", filename)
    # return util.add_watermark(file_path)


class MyRequestHandler(WSGIRequestHandler):
    def address_string(self):
        return self.headers["X-Forwarded-For"]

    def log_date_time_string(self):
        return ""

    def log_request(self, code="-", size="-"):
        if code != 200:
            self.log_error(
                "code: %s, size: %s, request: %s", code, size, self.requestline
            )
        else:
            self.log_message(
                "code: %s, size: %s, request: %s", code, size, self.requestline
            )


def run(*kwargs):
    return app(*kwargs)


if __name__ == "__main__":
    app.run(debug=True, port=5000, request_handler=MyRequestHandler)
