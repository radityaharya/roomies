import io
from flask import Flask, flash, redirect, render_template, request, url_for, send_file
import requests
from PIL import Image

# TODO: Change this to use JWT
def set_user_cookie(user_id):
    """
    It redirects the user to the index page, and sets a cookie called "user_id" to the user's id
    
    Args:
      user_id: The user's ID.
    
    Returns:
      A response object with a cookie set to the user_id
    """
    response = redirect(url_for("index"))
    response.set_cookie("user_id", str(user_id))
    return response


def price_format(price):
    """
    It takes a number, and returns a string with the number formatted with commas and two decimal places
    
    Args:
      price: The price of the item
    
    Returns:
      The price is being returned in a string format with a comma every three digits
    """
    return f"{price:,.2f}"


def get_request_ip(request):
    """
    If the request has a header, return that, otherwise return the remote address
    
    Args:
      request: The request object.
    
    Returns:
      The IP address of the client.
    """
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
    return ip

def get_coordinates(ipaddr):
    """
    It takes an IP address as input, and returns a list of two numbers, the latitude and longitude of
    the IP address
    
    Args:
      ipaddr: The IP address you want to get the coordinates for.
    
    Returns:
      A list of the latitude and longitude of the IP address.
    """
    try:
      response = requests.get(f"http://ip-api.com/json/{ipaddr}", timeout=5)
      lat = response.json()["lat"]
      lon = response.json()["lon"]
    except Exception as e:
      print(e)
      lat = 0
      lon = 0
    return [lat, lon]


def get_icon_from_facilities(facilities):
    """
    > It takes a list of facilities and returns a list of icons
    
    Args:
      facilities: a list of facilities
    
    Returns:
      A list of icons
    """
    icons = []
    for facility in facilities:
        if "Wifi" in facility:
            icons.append("fa-solid fa-wifi")
        elif "Parking" in facility:
            icons.append("fa-solid fa-square-parking")
        elif "Pool" in facility:
            icons.append("fa-solid fa-person-swimming")
        elif "Gym" in facility:
            icons.append("fa-solid fa-dumbbell")
        else:
            pass
    return icons[:3]

def add_watermark(img_path):
    """
    It takes an image and adds a watermark to it.
    
    Args:
      image: The image you want to add a watermark to.
    
    Returns:
      An image with a watermark.
    """
    image = Image.open(img_path) #jpg
    watermark = Image.open("static/img/watermark.png")

    width, height = image.size
    mark_width, mark_height = watermark.size
    left = (width - mark_width) // 2
    top = (height - mark_height) // 2
    image = image.crop((0, 0, width, height - 60))
    

    image.paste(watermark, (left, top), watermark)

    img_io = io.BytesIO()
    image.save(img_io, "JPEG", quality=100)
    img_io.seek(0)
    return send_file(img_io, mimetype="image/jpeg")