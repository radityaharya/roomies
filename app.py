import os
import logging

import bson
import geopy.distance
import numpy as np
import pymongo
from dotenv import load_dotenv
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
)

from werkzeug.serving import WSGIRequestHandler
from modules import auth_user
import util
import midtransclient
import datetime

load_dotenv(override=True)

app = Flask("roomies")
app.secret_key = os.urandom(24)
client = pymongo.MongoClient(os.environ["MONGO_URL"])

db = client.roomies
users = db.users

logger = logging.getLogger("roomies")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Returns:
      The login function from the auth_user module.
    """
    return auth_user.login(users, request)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Returns:
      The signup function from the auth_user module.
    """
    return auth_user.signup(users, request)


@app.route("/")
def home():
    """
    Returns:
      the render_template function, which is a function that renders a template.
    """
    return render_template("index.jinja", is_logged_in=auth_user.is_logged_in(request))


@app.route("/properties", methods=["GET", "POST"])
@auth_user.is_authenticated(request, users)
def index():
    """
    Returns:
      a rendered template of the home page.
    """
    if request.method == "GET":
        user = users.find_one(
            {
                "_id": bson.ObjectId(
                    auth_user.decode_token(request.cookies.get("token"))["user_id"]
                )
            }
        )
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
        properties = properties[:8]
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

        return render_template(
            "home.jinja",
            properties=data["near_you"],
            user=user,
            is_logged_in=auth_user.is_logged_in(request),
        )
    if request.method == "POST":
        query = request.form.get("query")
        return redirect(url_for("search", query=query))


@app.route("/property/<property_id>", methods=["GET"])
def details(property_id):
    property_item = db.properties.find_one({"_id": bson.ObjectId(property_id)})
    if property is None:
        return redirect(url_for("index"))

    data = {
        "id": str(property_item["_id"]),
        "name": property_item["name"],
        "location": property_item["location"],
        "price": util.price_format(property_item["price"]),
        "fasilitas": property_item["fasilitas"],
        "pictures": property_item["pictures"],
        "description": property_item["description"],
        "icons": util.get_icon_from_facilities(property_item["fasilitas"]),
        "price_description": property_item["price_description"],
    }

    return render_template(
        "property.jinja", property=data, is_logged_in=auth_user.is_logged_in(request)
    )


@app.route("/payment/<property_id>", methods=["GET"])
def payment(property_id):
    property_item = db.properties.find_one({"_id": bson.ObjectId(property_id)})
    if property is None:
        return redirect(url_for("index"))

    data = {
        "id": str(property_item["_id"]),
        "name": property_item["name"],
        "location": property_item["location"],
        "price": util.price_format(property_item["price"]),
        "fasilitas": property_item["fasilitas"],
        "pictures": property_item["pictures"],
        "description": property_item["description"],
        "icons": util.get_icon_from_facilities(property_item["fasilitas"]),
        "price_description": property_item["price_description"],
    }

    snap = midtransclient.Snap(
        is_production=False, 
        server_key=os.environ["MIDTRANS_SERVER_KEY"], 
        client_key=os.environ["MIDTRANS_CLIENT_KEY"]
    )
    # Prepare parameter
    random_str = os.urandom(5).hex()
    param = {
        "transaction_details": {
            "order_id": f"{property_id}-{random_str}",
            "gross_amount": property_item["price"],
        },
        "credit_card": {"secure": True},
    }

    transaction = snap.create_transaction(param)

    transaction_redirect_url = transaction["redirect_url"]

    return render_template(
        "payment.jinja", property=data, is_logged_in=auth_user.is_logged_in(request),
        transaction_url = transaction_redirect_url
    )

@app.route("/midtrans")
def midtrans():
    query_args = request.args
    api_client = midtransclient.CoreApi(
        is_production=False,
        server_key=os.environ["MIDTRANS_SERVER_KEY"],
        client_key=os.environ["MIDTRANS_CLIENT_KEY"],
    )
    return ""

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

    search_data = {"query": query, "sort": f"{sort_by}-{sort_order}", "limit": limit}

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
    return render_template(
        "search.jinja",
        properties=results,
        is_logged_in=auth_user.is_logged_in(request),
        search_data=search_data,
    )


@app.route("/static/img/<path:filename>")
def static_img(filename):
    if os.path.isfile(f"static/img/{filename}"):
        return send_from_directory("static/img", filename)
    else:
        # proxy fallback
        imghost = os.environ.get("IMG_HOST")
        return redirect(f"{imghost}/{filename}")


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
    wsgi_log = logging.getLogger("werkzeug")
    wsgi_log.setLevel(logging.ERROR)
    app.run(debug=True, port=5000, request_handler=MyRequestHandler)
