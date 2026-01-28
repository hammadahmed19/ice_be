from flask import Flask, request, jsonify
from flask_cors import CORS
import piexif
import math

app = Flask(__name__)
from flask_cors import CORS

CORS(
    app,
    resources={
        r"/verify-image": {
            "origins": ["https://ice-watch-adminpanel.vercel.app"]
        }
    }
)

# ===============================
# COUNTRY BOUNDARIES (Bounding Box)
# ===============================
COUNTRY_BOUNDARIES = {
    "pakistan": {
        "min_lat": 23.6345,
        "max_lat": 37.0841,
        "min_lon": 60.8728,
        "max_lon": 77.8375,
    }
}

# ===============================
# HELPERS
# ===============================
def rational_to_float(r):
    return float(r[0]) / float(r[1]) if r and r[1] != 0 else 0.0

def dms_to_decimal(dms, ref):
    degrees = rational_to_float(dms[0])
    minutes = rational_to_float(dms[1])
    seconds = rational_to_float(dms[2])

    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ["S", "W"]:
        decimal *= -1
    return decimal

def is_within_country(lat, lon, country):
    bounds = COUNTRY_BOUNDARIES.get(country.lower())
    if not bounds:
        return False

    return (
        bounds["min_lat"] <= lat <= bounds["max_lat"]
        and bounds["min_lon"] <= lon <= bounds["max_lon"]
    )

def haversine_distance(lat1, lon1, lat2, lon2):
    """Distance in meters"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# ===============================
# EXIF EXTRACTION
# ===============================
def extract_image_metadata(image_file):
    try:
        exif_dict = piexif.load(image_file.read())
    except Exception:
        return None, None

    gps = exif_dict.get("GPS", {})
    try:
        lat = gps.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef)
        lon = gps.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef)

        if lat and lon and lat_ref and lon_ref:
            latitude = dms_to_decimal(lat, lat_ref.decode())
            longitude = dms_to_decimal(lon, lon_ref.decode())
            return latitude, longitude
    except Exception:
        pass

    return None, None

# ===============================
# API: VERIFY IMAGE (USED BY REACT)
# ===============================
@app.route("/verify-image", methods=["POST"])
def verify_image():
    image = request.files.get("image")
    country_name = request.form.get("country_name", "").lower()

    print("Received verification request")

    if not image:
        return jsonify({
            "verified": False,
            "reason": "No image uploaded"
        }), 400

    exif_lat, exif_lon = extract_image_metadata(image)

    print(f"Extracted EXIF GPS: {exif_lat}, {exif_lon}")

    if exif_lat is None or exif_lon is None:
        return jsonify({
            "verified": False,
            "reason": "Image has no GPS EXIF data"
        })

    if not is_within_country(exif_lat, exif_lon, country_name):
        return jsonify({
            "verified": False,
            "reason": f"Image GPS is outside {country_name.title()}"
        })

    return jsonify({
        "verified": True,
        "reason": f"Image GPS is inside {country_name.title()}"
    })


# ===============================
# RUN SERVER (LAN ACCESS)
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
