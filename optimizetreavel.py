import os
import asyncio
import json
import base64
import requests
import argparse
import time
from io import BytesIO
from PIL import Image
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from pymongo import MongoClient
from bson import ObjectId
from collections import OrderedDict
from autogen_agentchat.agents import AssistantAgent 
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

CACHE_FILE = Path("location_cache.json")
if CACHE_FILE.exists():
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        LOCATION_CACHE = json.load(f)
else:
    LOCATION_CACHE = {}

def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(LOCATION_CACHE, f, indent=2, ensure_ascii=False)

# ===== DYNAMIC MAP FUNCTIONS =====

def generate_dynamic_map(location_name, lat=None, lon=None):
    """
    Generate a dynamic map using OpenStreetMap/Nominatim
    
    Args:
        location_name (str): Name of the location to display
        lat (float, optional): Latitude. If None, will fetch from Nominatim
        lon (float, optional): Longitude. If None, will fetch from Nominatim
    
    Returns:
        dict: Contains map HTML and location data
    """
    
    # If coordinates not provided, fetch from Nominatim
    if lat is None or lon is None:
        location_data = fetch_location_for_map(location_name)
        if location_data and 'error' not in location_data:
            lat = location_data.get('latitude', 0.0)
            lon = location_data.get('longitude', 0.0)
            address = location_data.get('address', location_name)
        else:
            # Default to Goa coordinates if location not found
            lat, lon = 15.2993, 74.1240
            address = location_name
    else:
        address = location_name
    
    # Create map HTML using OpenStreetMap
    map_html = create_osm_map_html(lat, lon, location_name, address)
    
    return {
        'map_html': map_html,
        'latitude': lat,
        'longitude': lon,
        'address': address,
        'location_name': location_name
    }

def fetch_location_for_map(location_name):
    """
    Fetch location data from Nominatim specifically for map generation
    """
    url = "https://nominatim.openstreetmap.org/search"
    
    # Prioritize Indian locations
    search_queries = [
        f"{location_name}, Goa, India",
        f"{location_name}, India",
        location_name
    ]
    
    for search_query in search_queries:
        params = {
            "q": search_query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }
        
        try:
            response = requests.get(url, params=params, headers={
                "User-Agent": "TravelGuideBot/1.0 (contact@travelguide.com)"
            }, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data:
                location = data[0]
                return {
                    "address": location.get("display_name", location_name),
                    "latitude": float(location["lat"]),
                    "longitude": float(location["lon"])
                }
        except Exception as e:
            continue
    
    return {"error": "Location not found", "address": location_name}

def create_osm_map_html(lat, lon, location_name, address):
    """
    Create OpenStreetMap HTML with marker for the location
    """
    map_html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>{location_name}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
        <style>
            #map {{ 
                height: 400px; 
                width: 100%;
                border-radius: 10px;
                border: 2px solid #ddd;
            }}
            .map-container {{
                margin: 10px 0;
            }}
            .location-info {{
                background: #f8f9fa;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 10px;
                font-family: Arial, sans-serif;
            }}
        </style>
    </head>
    <body>
        <div class="map-container">
            <div class="location-info">
                <strong>ðŸ“ {location_name}</strong><br>
                <small>{address}</small><br>
                <small>Coordinates: {lat:.6f}, {lon:.6f}</small>
            </div>
            <div id="map"></div>
        </div>
        
        <script>
            // Initialize the map
            var map = L.map('map').setView([{lat}, {lon}], 15);
            
            // Add OpenStreetMap tiles
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: 'Â© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 18
            }}).addTo(map);
            
            // Add marker for the location
            var marker = L.marker([{lat}, {lon}]).addTo(map);
            marker.bindPopup("<b>{location_name}</b><br>{address}").openPopup();
            
            // Add circle to highlight the area
            var circle = L.circle([{lat}, {lon}], {{
                color: 'red',
                fillColor: '#f03',
                fillOpacity: 0.1,
                radius: 200
            }}).addTo(map);
        </script>
    </body>
    </html>
    '''
    return map_html

def get_map_for_existing_document(document):
    """
    Generate map for an existing document with location data
    """
    if not document:
        return None
    
    location_data = document.get('location', {})
    lat = location_data.get('latitude')
    lon = location_data.get('longitude')
    address = location_data.get('address')
    title = document.get('title', 'Unknown Location')
    
    if lat and lon:
        return generate_dynamic_map(title, lat, lon)
    elif address:
        return generate_dynamic_map(title)
    else:
        return None

# ===== SMART UPDATE FUNCTIONS =====

def get_document_by_topic(topic, goa_db):
    if goa_db is None:
        return None
    collection = goa_db["OUTPUT"]
    slug = topic.lower().replace(' ', '-')
    document = collection.find_one({"slug": slug})
    if document:
        return document
    document = collection.find_one({"title": {"$regex": f"^{topic}$", "$options": "i"}})
    return document

def is_content_outdated(created_at, days_threshold=60):
    if not created_at:
        return True
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except:
            return True
    return (datetime.now() - created_at).days > days_threshold

def contains_wrong_location(content, user_topic):
    if not content or not user_topic:
        return False
    content_lower = content.lower()
    user_topic_lower = user_topic.lower()
    wrong_locations = ["mumbai", "delhi", "bangalore", "kolkata", "chennai", "hyderabad", "maharashtra", "karnataka", "tamil nadu", "kerala", "andhra pradesh", "punjab", "rajasthan", "uttar pradesh", "bihar", "west bengal"]
    if 'goa' in user_topic_lower or any(beach in user_topic_lower for beach in ['beach', 'miramar', 'baga', 'calangute', 'anjuna']):
        if any(location in content_lower for location in wrong_locations):
            return True
    return False

def contains_generic_phrases(content):
    if not content:
        return True
    content_lower = content.lower()
    generic_phrases = ["this is a nice place", "popular destination", "famous location", "well known", "great spot", "beautiful place", "good area", "this location is", "visit this place", "famous spot", "this is a place", "this destination", "well-known destination"]
    return any(phrase in content_lower for phrase in generic_phrases)

def missing_topic_name(content, user_topic):
    if not content or not user_topic:
        return True
    return user_topic.lower() not in content.lower()

def contains_outdated_years(content):
    if not content:
        return False
    return any(year in content.lower() for year in ["2023", "2022", "2021", "2020"])

def needs_field_update(field_content, user_topic, created_at, is_content_field=False):
    if not field_content or not field_content.strip():
        return True
    if is_content_outdated(created_at, 60):
        return True
    if contains_wrong_location(field_content, user_topic):
        return True
    if contains_generic_phrases(field_content):
        return True
    if missing_topic_name(field_content, user_topic):
        return True
    if is_content_field and contains_outdated_years(field_content):
        return True
    return False

def update_document_partial(goa_db, slug, updates):
    if goa_db is None:
        return False
    try:
        collection = goa_db["OUTPUT"]
        update_data = {"$set": updates}
        update_data["$set"]["updatedAt"] = datetime.utcnow()
        result = collection.update_one({"slug": slug}, update_data)
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating document: {e}")
        return False
    
# ===== ORIGINAL HELPER FUNCTIONS (KEPT AS IS) =====
# Helper function to convert image to WEBP and encode as base64
def convert_image_to_webp_and_encode_base64(image: Image.Image, target_width=800, target_height=600) -> str:
    image = image.resize((target_width, target_height), Image.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=80)
    buffer.seek(0)
    encoded_bytes = base64.b64encode(buffer.read())
    data_uri = f"data:image/webp;base64,{encoded_bytes.decode('utf-8')}"
    return data_uri

# MongoDB Connection
def get_mongodb_connection():
    """Establish MongoDB connections for goa-app database"""
    try:
        mongo_uri = os.getenv("mongodb+srv://nomorevenxm_db_user:<db_password>@cluster0.l3nhk4f.mongodb.net/?appName=Cluster0")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        goa_db = client['goa-app']
        return goa_db
    except Exception:
        return None

# Save to MongoDB
def insert_into_mongodb(output, goa_db):
    """Insert or update document in MongoDB goa-app database (OUTPUT collection)"""
    if goa_db is None:
        return
    try:
        goa_db.client.admin.command('ping')
    except Exception:
        return
    try:
        if "slug" not in output:
            return
        collection = goa_db["OUTPUT"]
        if "createdAt" in output and isinstance(output["createdAt"], str):
            try:
                output["createdAt"] = datetime.fromisoformat(output["createdAt"].replace("Z", "+00:00"))
            except:
                output["createdAt"] = datetime.utcnow()
        elif "createdAt" not in output:
            output["createdAt"] = datetime.utcnow()
        if collection.find_one({"slug": output["slug"]}):
            collection.update_one(
                {"slug": output["slug"]},
                {"$set": output}
            )
        else:
            collection.insert_one(output)
    except Exception:
        pass

# ===== LOCATION VALIDATION SYSTEM =====
def create_location_validator_agent(model, current_date):
    """Agent that validates if fetched location matches the topic"""
    return AssistantAgent(
        name="location_validator_agent",
        description="Validates if location data matches the topic correctly",
        system_message=f'''You are an expert location validator for INDIAN travel destinations as of {current_date}. 

VALIDATION RULES:
- ✅ CORRECT: Location name matches topic (e.g., topic "Colva Beach" = location "Colva Beach, Goa")
- ✅ CORRECT: Location is in appropriate Indian state (Goa, Maharashtra, Karnataka, etc.)
- ✅ CORRECT: Location type matches topic type (beach topic = coastal location, restaurant = urban area)
- ❌ WRONG: Location name doesn't match topic (e.g., topic "Colva Beach" = location "Calangute Beach")
- ❌ WRONG: Location is in wrong Indian state
- ❌ WRONG: Location type mismatch (beach topic = inland location)

SPECIAL CASES:
- For events: Location should match event location mentioned in topic
- For restaurants: Should be in populated areas, not remote locations
- For beaches: Should be coastal locations in appropriate states

Respond ONLY with JSON in this exact format:
{{"is_valid": true|false, "reason": "brief explanation", "should_retry": true|false}}
''',
        model_client=model
    )

async def validate_existing_location_in_db(document, user_topic, content_type, model):
    """
    Validate if the existing location in database is correct for the topic
    """
    if not document or not document.get('location'):
        return {"is_valid": False, "needs_update": True, "reason": "No location data in document"}
    
    location_data = document.get('location', {})
    address = location_data.get('address', '')
    
    if not address:
        return {"is_valid": False, "needs_update": True, "reason": "Empty address in location data"}
    
    current_date = datetime.now().strftime("%B %d, %Y")
    validator_agent = create_location_validator_agent(model, current_date)
    
    validation_task = f'''
    Topic: {user_topic}
    Content Type: {content_type}
    Existing Database Location: {address}
    Coordinates: {location_data.get('latitude', 'N/A')}, {location_data.get('longitude', 'N/A')}
    
    Validate if this existing location in our database correctly matches the topic.
    '''
    
    try:
        validation_result = await safe_run(validator_agent, validation_task)
        
        if isinstance(validation_result, dict):
            return {
                "is_valid": validation_result.get("is_valid", False),
                "needs_update": not validation_result.get("is_valid", False),
                "reason": validation_result.get("reason", "Validation failed"),
                "should_retry": validation_result.get("should_retry", False)
            }
    except Exception as e:
        print(f"⚠️ Location validation error: {e}")
    
    return {"is_valid": True, "needs_update": False, "reason": "Validation passed"}

async def fetch_and_validate_location(user_topic, search_query, content_type, model, max_retries=3):
    """Fetch location with validation and retries"""
    current_date = datetime.now().strftime("%B %d, %Y")
    
    validator_agent = create_location_validator_agent(model, current_date)
    
    for attempt in range(max_retries):
        print(f"📍 Location fetch attempt {attempt + 1}/{max_retries} for '{user_topic}'")
        
        # Use the FIXED location fetch function
        location_data = fetch_location(search_query)
        
        # Check for errors
        if location_data.get("error"):
            print(f"❌ Location fetch error: {location_data.get('error')}")
            if attempt < max_retries - 1:
                print("🔄 Retrying...")
                time.sleep(2)  # Wait before retry
                continue
            else:
                return location_data
        
        # Skip validation if no address
        if not location_data.get("address"):
            print("❌ No address in location data")
            if attempt < max_retries - 1:
                continue
            else:
                return location_data
        
        # Validate the location
        validation_task = f'''
        Topic: {user_topic}
        Content Type: {content_type}
        Fetched Location: {location_data.get('address', 'Unknown')}
        Coordinates: {location_data.get('latitude', 'N/A')}, {location_data.get('longitude', 'N/A')}
        
        Validate if this location correctly matches the topic.
        '''
        
        try:
            validation_result = await safe_run(validator_agent, validation_task)
            
            if isinstance(validation_result, dict) and validation_result.get("is_valid", False):
                print(f"✅ Location validated: {validation_result.get('reason', 'Valid location')}")
                return location_data
            else:
                print(f"❌ Location invalid: {validation_result.get('reason', 'Unknown reason')}")
                
                # If should retry and we have more attempts
                if validation_result.get("should_retry", True) and attempt < max_retries - 1:
                    print("🔄 Retrying with different search strategy...")
                    # Modify search query for retry
                    search_query = modify_search_query_for_retry(user_topic, content_type, attempt)
                    continue
                else:
                    print("🚫 Max retries reached or no retry requested")
                    return location_data
                    
        except Exception as e:
            print(f"⚠️ Validation error: {e}")
            if attempt < max_retries - 1:
                continue
    
    return location_data

def modify_search_query_for_retry(user_topic, content_type, attempt):
    """Modify search query for retry attempts"""
    base_query = user_topic
    
    if attempt == 0:
        # First retry: Add state if not present
        if "goa" not in user_topic.lower():
            return f"{user_topic}, Goa"
        else:
            return user_topic
    
    elif attempt == 1:
        # Second retry: Be more specific based on content type
        if content_type == "beach":
            return f"{user_topic} Beach"
        elif content_type == "restaurant":
            return f"{user_topic} Restaurant"
        elif content_type == "event":
            return f"{user_topic} Festival"
        else:
            return user_topic
    
    else:
        # Final attempt: Use just the core name
        words = user_topic.split()
        return words[0] if words else user_topic
    
# Retrieve document with ordered fields
def get_document(slug, goa_db):
    """Retrieve a document from MongoDB with fields in the desired order."""
    if goa_db is None:
        return None
    collection = goa_db["OUTPUT"]
    projection = {
        "_id": 1,
        "gallery": 1,
        "tags": 1,
        "categories": 1,
        "active": 1,
        "featured": 1,
        "postType": 1,
        "title": 1,
        "slug": 1,
        "shortDescription": 1,
        "seoTitle": 1,
        "icon": 1,
        "text": 1,
        "guidelines": 1,
        "location": 1,
        "ways": 1,
        "typeId": 1,
        "city": 1,
        "author": 1,
        "thumbnail": 1,
        "createdAt": 1,
        "rating": 1,
        "likes": 1,
        "views": 1,
        "__v": 1,
        "hasPickup": 1,
        "internal": 1,
        "area": 1,
        "bestSeller": 1,
        "coupleFriendly": 1,
        "groupFriendly": 1,
        "hasOffer": 1,
        "isGuestInfoNeeded": 1,
        "isOpen": 1,
        "kidsFriendly": 1,
        "monsoon": 1,
        "offerCount": 1,
        "promote": 1,
        "state": 1,
        "trending": 1
    }
    document = collection.find_one({"slug": slug}, projection)
    return document

# Format document as JSON with specific field order
def format_document(document):
    """Format a MongoDB document to JSON with specific field order."""
    if not document:
        return None
    ordered_doc = OrderedDict([
        ("_id", str(document.get("_id"))),
        ("gallery", document.get("gallery", [])),
        ("tags", document.get("tags", [])),
        ("categories", [str(c) for c in document.get("categories", [])]),
        ("active", document.get("active", False)),
        ("featured", document.get("featured", False)),
        ("postType", document.get("postType", "")),
        ("title", document.get("title", "")),
        ("slug", document.get("slug", "")),
        ("shortDescription", document.get("shortDescription", "")),
        ("seoTitle", document.get("seoTitle", "")),
        ("icon", document.get("icon", "")),
        ("text", document.get("text", "")),
        ("guidelines", document.get("guidelines", "")),
        ("location", document.get("location", {})),
        ("ways", document.get("ways", {})),
        ("typeId", str(document.get("typeId")) if document.get("typeId") else None),
        ("city", str(document.get("city")) if document.get("city") else None),
        ("author", str(document.get("author")) if document.get("author") else None),
        ("thumbnail", document.get("thumbnail", "")),
        ("createdAt", document.get("createdAt").isoformat() if document.get("createdAt") else ""),
        ("rating", str(document.get("rating")) if document.get("rating") else None),
        ("likes", str(document.get("likes")) if document.get("likes") else None),
        ("views", str(document.get("views")) if document.get("views") else None),
        ("_v", document.get("_v", 0)),
        ("hasPickup", document.get("hasPickup", False)),
        ("internal", document.get("internal", False)),
        ("area", str(document.get("area")) if document.get("area") else None),
        ("bestSeller", document.get("bestSeller", False)),
        ("coupleFriendly", document.get("coupleFriendly", False)),
        ("groupFriendly", document.get("groupFriendly", False)),
        ("hasOffer", document.get("hasOffer", False)),
        ("isGuestInfoNeeded", document.get("isGuestInfoNeeded", False)),
        ("isOpen", document.get("isOpen", False)),
        ("kidsFriendly", document.get("kidsFriendly", False)),
        ("monsoon", document.get("monsoon", False)),
        ("offerCount", document.get("offerCount", 0)),
        ("promote", document.get("promote", False)),
        ("state", str(document.get("state")) if document.get("state") else None),
        ("trending", document.get("trending", False))
    ])
    return json.dumps(ordered_doc, indent=2)

# Find place IDs
def find_place_ids(address, goa_db):
    """Query goa-app database to find city, area, and state IDs based on address"""
    if not address or goa_db is None:
        return {"city_id": None, "area_id": None, "state_id": None}
    address_parts = [part.strip().lower() for part in address.split(',') if part.strip()]
    cities_col = goa_db["cities"]
    areas_col = goa_db["areas"]
    states_col = goa_db["states"]
    for part in address_parts:
        city = cities_col.find_one({"name": {"$regex": f"^{part}$", "$options": "i"}})
        if city:
            return {
                "city_id": str(city["_id"]),
                "area_id": str(city.get("area", None)) if city.get("area") else None,
                "state_id": str(city.get("state", None)) if city.get("state") else None
            }
        area = areas_col.find_one({"name": {"$regex": f"^{part}$", "$options": "i"}})
        if area:
            return {
                "city_id": None,
                "area_id": str(area["_id"]),
                "state_id": str(area.get("state", None)) if area.get("state") else None
            }
        state = states_col.find_one({"name": {"$regex": f"^{part}$", "$options": "i"}})
        if state:
            return {
                "city_id": None,
                "area_id": None,
                "state_id": str(state["_id"])
            }
    return {"city_id": None, "area_id": None, "state_id": None}

# Fetch location data
def fetch_location_precise(query: str):
    time.sleep(1.1)  # Respect Nominatim policy
    params = {
        "q": query,
        "format": "json",
        "limit": 20,
        "countrycodes": "in",
        "addressdetails": 1,
        "bounded": 1,
        "viewbox": "73.65,14.90,74.45,15.85",      
        "viewboxlbrt": "73.65,14.90,74.45,15.85",
        "extratags": 1
    }
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            timeout=15
        )
        if r.status_code != 200 or not r.json():
            return None

        results = r.json()

        # STEP 1: Prefer high-importance places (cities, towns, villages, beaches)
        candidates = [
            res for res in results
            if res.get("importance", 0) > 0.5 and "goa" in res.get("display_name", "").lower()
        ]
        if candidates:
            best = max(candidates, key=lambda x: x.get("importance", 0))
            return {
                "address": best["display_name"],
                "latitude": float(best["lat"]),
                "longitude": float(best["lon"]),
                "source": "nominatim_precise"
            }

        # STEP 2: If no high-importance, take any result inside Goa (sorted by importance)
        goa_results = [res for res in results if "goa" in res.get("display_name", "").lower()]
        if goa_results:
            best = max(goa_results, key=lambda x: x.get("importance", 0))
            return {
                "address": best["display_name"],
                "latitude": float(best["lat"]),
                "longitude": float(best["lon"]),
                "source": "nominatim_precise"
            }

    except Exception as e:
        print(f"   Nominatim error: {e}")

    return None

def verify_by_reverse_geocode(lat: float, lon: float, expected_words: list) -> bool:
    time.sleep(1.1)
    try:
        params = {"lat": lat, "lon": lon, "format": "json", "zoom": 16}
        r = requests.get("https://nominatim.openstreetmap.org/reverse", params=params,timeout=10)
        if r.status_code == 200:
            data = r.json()
            reverse_name = data.get("display_name", "").lower()
            return any(word in reverse_name for word in expected_words)
    except:
        pass
    return False

def fetch_location(address: str):
    """Enhanced location lookup that prioritizes Indian locations"""
    if not address:
        return {"address": None, "latitude": 0.0, "longitude": 0.0}
    url = "https://nominatim.openstreetmap.org/search"
    search_strategies = [
        f"{address}, India",
        *[f"{address}{state}" for state in [
            ", Goa, India", ", Maharashtra, India", ", Karnataka, India",
            ", Kerala, India", ", Tamil Nadu, India", ", Andhra Pradesh, India",
            ", Odisha, India", ", West Bengal, India", ", Gujarat, India",
            ", Andaman and Nicobar Islands, India"
        ]],
        f"{address} beach, India" if "beach" not in address.lower() else address,
        *[f"{address} beach{state}" for state in [
            ", Goa, India", ", Maharashtra, India", ", Karnataka, India",
            ", Kerala, India", ", Tamil Nadu, India", ", Andhra Pradesh, India",
            ", Odisha, India", ", West Bengal, India", ", Gujarat, India",
            ", Andaman and Nicobar Islands, India"
        ] if "beach" not in address.lower()],
        address,
        f"{address} beach" if "beach" not in address.lower() else address
    ]
    unique_strategies = list(dict.fromkeys(search_strategies))
    best_indian_result = None
    for search_query in unique_strategies:
        params = {
            "q": search_query,
            "format": "json",
            "limit": 5,
            "addressdetails": 1,
            "_": str(int(datetime.now().timestamp()))  # Cache busting
        }
        try:
            response = requests.get(url, params=params, headers={
                "User-Agent": "TravelGuideBot/1.0 (contact@travelguide.com)"
            })
            response.raise_for_status()
            data = response.json()
            if data:
                indian_results = [loc for loc in data if 'india' in loc.get('display_name', '').lower() or loc.get('address', {}).get('country_code', '').lower() == 'in']
                if indian_results:
                    location_data = indian_results[0]
                    return {
                        "address": location_data.get("display_name", address),
                        "latitude": float(location_data["lat"]),
                        "longitude": float(location_data["lon"])
                    }
                elif not best_indian_result:
                    location_data = data[0]
                    best_indian_result = {
                        "address": location_data.get("display_name", address),
                        "latitude": float(location_data["lat"]),
                        "longitude": float(location_data["lon"])
                    }
        except Exception:
            continue
    if best_indian_result:
        return best_indian_result
    return {"error": "Location not found", "address": address}


# Get or create category ID
def get_category_id(goa_db, category_name):
    """Get or create category ID from MongoDB goa-app database"""
    if goa_db is None:
        return ObjectId()
    try:
        categories_collection = goa_db['categories']
        category = categories_collection.find_one({"name": category_name.lower()})
        if category:
            return category['_id']
        else:
            new_category = {
                "name": category_name.lower(),
                "displayName": category_name.title(),
                "slug": category_name.lower().replace(' ', '-'),
                "active": True,
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            }
            result = categories_collection.insert_one(new_category)
            return result.inserted_id
    except Exception:
        return ObjectId()

# Create smart location agent
def create_smart_location_agent(model, current_date):
    """Agent that determines if a location should be fetched"""
    return AssistantAgent(
        name="smart_location_agent",
        description="Determines if location data should be fetched and what to search for",
        system_message=f'''You are an expert location analyzer for INDIAN travel destinations as of {current_date}. Analyze the topic and determine:
1. Should we fetch location data?
2. What exact search query should we use for the location API?

RULES FOR FETCHING LOCATION:
- YES: For beaches, landmarks, tourist spots, specific places, restaurants, events with locations (e.g., 'Shigmo Utsav, Goa', 'Shigmo Utsav, Ponda', 'Shigmo Utsav Ponda Goa')
- YES: For ANY beach name (e.g., 'Miramar', 'Baga', 'Calangute', 'Anjuna')
- YES: For events with a state (e.g., 'Shigmo Utsav, Goa') or city (e.g., 'Shigmo Utsav, Ponda')
- NO: For events without a specific location (e.g., 'Shigmo Utsav', 'Sunburn')
- NO: For general concepts ('pizza', 'music'), food items ('momos', 'burger')

RULES FOR SEARCH QUERY:
- For events with state (e.g., 'Shigmo Utsav, Goa'): Use only the state name (e.g., 'Goa')
- For events with city or city and state (e.g., 'Shigmo Utsav, Ponda', 'Shigmo Utsav Ponda Goa'): Use the city name (e.g., 'Ponda')
- For other Indian locations: Use just the name (e.g., 'Miramar', 'Baga Beach')
- DO NOT add 'India' or state names unless part of the event location logic
- The system will automatically prioritize Indian locations
- For restaurants: Use just the restaurant name

IMPORTANT: This is for INDIAN travel guide, so we want Indian locations only.

Respond ONLY with JSON in this exact format:
{{"should_fetch": true|false, "search_query": "exact query to use"}}
If should_fetch is false, search_query should be an empty string.
''',
        model_client=model
    )

# Create classifier agent
def create_classifier_agent(model, current_date):
    """Agent that categorizes topics into multiple content types"""
    return AssistantAgent(
        name="content_classifier_agent",
        description="Categorizes topics into appropriate content types",
        system_message=f'''You are an expert content classifier as of {current_date}. Analyze the given topic and determine its type:

Available categories:
- 'event': Festivals, concerts, shows, parties, temporary activities
- 'restaurant': Specific eating establishments with proper names (e.g., 'McDonald's', 'Joe's Pizza')
- 'blog': General topics, food items (like 'momos', 'pizza'), travel tips, guides, informational content
- 'beach': Beaches, coastal destinations
- 'waterfall': Natural waterfalls
- 'fort': Historical forts, castles
- 'religion': Temples, churches, mosques, shrines, religious practices
- 'travel': Tours, travel experiences, itineraries
- 'water-sport': Activities like jet skiing, parasailing, kayaking, scuba diving
- 'boat-party': Cruise parties, boat events
- 'guide-tour': Guided tours and trails (e.g., trekking tours, city tours)
- 'dining-fine': Fine dining restaurants
- 'dining-casual': Casual dining spots
- 'dining-family': Family-style restaurants
- 'dining-seafood': Seafood-specialized restaurants
- 'dining-bar': Bars, pubs, bar-restaurants
- 'dining-chinese': Chinese-specialized restaurants
- 'entertainment': Movies, clubs, amusement parks, nightlife, concerts

IMPORTANT RULES:
1. If the input is a general food item (like 'momos', 'pizza', 'burger'), categorize it as 'blog'.
2. If the input doesn't refer to a specific restaurant or location, categorize it as 'blog'.
3. Only categorize as 'restaurant' when it's clearly a named establishment (e.g., 'Taj Hotel').
4. For dining categories (fine, casual, family, seafood, bar, Chinese), prefer them over 'restaurant' if the style is clear.
5. Use the most specific category available (e.g., 'beach' instead of 'travel').

Respond ONLY with JSON in this exact format:
{{"type": "beach|waterfall|fort|religion|travel|event|restaurant|blog|water-sport|boat-party|guide-tour|dining-fine|dining-casual|dining-family|dining-seafood|dining-bar|dining-chinese|entertainment", "confidence": 0.95}}
''',
        model_client=model
    )

# Team configuration
def teamConfig():
    current_date = datetime.now().strftime("%B %d, %Y")
    openrouter_key = os.getenv("OPENROUTER_KEY")
    if not openrouter_key:
        if os.path.exists("api.txt"):
            openrouter_key = open("api.txt").read().strip()
        else:
            raise RuntimeError("No OpenRouter API key found. Set OPENROUTER_KEY or create api.txt.")
    model = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=500
    )
    content_classifier_agent = create_classifier_agent(model, current_date)
    smart_location_agent = create_smart_location_agent(model, current_date)
    description_agent = AssistantAgent(
        name="description_agent",
        description="Writes type-specific descriptions",
        system_message=f'''You are an expert content writer specializing in travel and tourism as of {current_date}. 
Write a short, engaging description (1-2 sentences) based on the content type:
- For PLACES (beach, waterfall, fort, religion): Focus on location, atmosphere, and key features
- For EVENTS (event, boat-party, entertainment): Highlight timing, experience, and uniqueness
- For RESTAURANTS (restaurant, dining-fine, dining-casual, dining-family, dining-seafood, dining-bar, dining-chinese): Emphasize cuisine, ambiance, and specialties
- For BLOGS (blog): Create informative, engaging overviews
- For ACTIVITIES (water-sport, guide-tour, travel): Highlight activities, experiences, and key features
Respond ONLY with plain text.
''',
        model_client=model
    )
    tags_agent = AssistantAgent(
        name="tags_agent",
        description="Generates topic-specific SEO tags with hashtags",
        system_message=f'''You are an SEO expert as of {current_date}. Generate 8-12 highly relevant tags with hashtags based ONLY on the exact topic.

    CRITICAL RULES:
    1. Add # at the beginning of EVERY tag
    2. DO NOT add generic travel tags like '#travel', '#tourism', '#vacation' unless explicitly part of the topic
    3. Focus ONLY on the core topic and its direct variations
    4. Make tags search-friendly (no spaces, use camelCase or underscores if needed)

    FORMATTING:
    - Use camelCase for multi-word tags: #GoaBeaches not #goa beaches
    - Or use underscores: #south_goa
    - Remove special characters and spaces

    Examples:
    - For 'Colva Beach': {{"tags": ["#ColvaBeach", "#ColvaBeachGoa", "#SouthGoaBeaches", "#ColvaBeachActivities", "#GoaBeachLife", "#ColvaSunset", "#BeachGoa", "#GoaTourism"]}}
    - For 'Sunburn Festival': {{"tags": ["#SunburnFestival", "#SunburnGoa", "#EDMFestivalIndia", "#SunburnTickets", "#MusicFestivalGoa", "#Sunburn2024", "#EDMIndia", "#GoaFestivals"]}}
    - For 'Italian Restaurant': {{"tags": ["#ItalianRestaurant", "#Pasta", "#Pizza", "#ItalianCuisine", "#FineDining", "#ItalianFood", "#RestaurantReview", "#Foodie"]}}

    ALWAYS return valid JSON: {{"tags": ["#tag1", "#tag2", ...]}}
    ''',
        model_client=model
    )
    content_agent = AssistantAgent(
        name="content_agent",
        description="Writes detailed, type-specific long-form HTML content",
        system_message=f'''You are an expert travel and lifestyle content writer as of October 01, 2025. Your goal is to generate long, detailed, and engaging HTML content for the given topic, ensuring all sections and paragraphs are complete without truncation or mid-sentence breaks. The output must include at least 5 full paragraphs, each with 4-5 sentences, and the final paragraph must be fully concluded with no abrupt endings. Use <p>, <ul>, <ol>, <li>, <strong>, <em>, <h2>, and <h3> tags for proper formatting. Do NOT include <html>, <head>, or <body> tags.

    ### WRITING RULES ###
    - Write at least 5 complete paragraphs, each containing 4-5 sentences, ensuring the final paragraph is fully concluded without truncation or incomplete sentences.
    - Verify content continuity before finalizing to prevent mid-sentence breaks, incomplete lists, or unfinished sections.
    - Use <h2> and <h3> subheadings to organize content into clear, logical sections (e.g., history, activities, practical details).
    - Provide detailed, informative, and engaging content, covering background/history, cultural or local significance, and practical details (e.g., how to reach, costs, safety tips).
    - Include current information (events, trends, seasonal notes) relevant to October 01, 2025, to ensure timeliness.
    - End with a <p><em>Travel Tip:</em> [Practical, topic-specific advice].</p>.
    - Ensure all HTML tags are correctly opened and closed, with no formatting errors.

    ### TYPE-SPECIFIC CONTENT GUIDELINES ###
    - PLACES (beach, waterfall, fort, religious sites): Detail how to reach, history, attractions, activities, best time to visit, local culture, and safety tips. Include specific directions, entry fees, and seasonal considerations.
    - EVENTS: Include schedule, location, ticket information, highlights, target audience, and future related events if the event is past. Provide clear dates and logistical details.
    - RESTAURANTS: Describe cuisine, menu highlights, chef background, ambience, customer reviews, pricing, and seasonal specials. Mention reservation policies and dietary options.
    - BLOGS: Provide guides, do's and don'ts, hidden gems, travel hacks, and comparisons with similar destinations. Include actionable, unique insights.
    - ACTIVITIES: Explain what the activity involves, costs, gear needed, skill level, risks, safety measures, and ideal seasons. Highlight options for beginners and experts.

    ### ADDITIONAL CONSTRAINTS ###
    - Ensure content is culturally accurate and sensitive, reflecting the topic's local significance.
    - Avoid filler content; every sentence must add value through historical context, practical advice, or cultural insights.
    - Complete all lists (<ul> or <ol>) with at least 3-4 relevant, detailed items.
    - Double-check that the final paragraph is engaging, conclusive, and not cut off mid-sentence.
    - For seasonal topics, specify the best times to visit or participate, tied to October 01, 2025.

    By adhering to these rules, produce polished, complete, and engaging HTML content that avoids truncation and provides a seamless, professional reading experience.
    ''',
        model_client=model
    )
    guidelines_agent = AssistantAgent(
        name="guidelines_agent",
        description="Provides type-specific guidelines",
        system_message=f'''You are a travel and safety expert as of {current_date}. Provide 4-6 practical guidelines based on type, considering current date for timeliness:
- PLACES (beach, waterfall, fort, religion): Travel tips, safety, local customs
- EVENTS (event, boat-party, entertainment): Timing, preparation, what to bring
- RESTAURANTS (restaurant, dining-fine, dining-casual, dining-family, dining-seafood, dining-bar, dining-chinese): Dining etiquette, reservations, dietary info
- BLOGS (blog): General travel advice and tips
- ACTIVITIES (water-sport, guide-tour, travel): Safety tips, equipment, preparation
Plain text only, no formatting.
''',
        model_client=model
    )
    image_prompt_agent = AssistantAgent(
        name="image_prompt_agent",
        description="Creates highly detailed and topic-specific image generation prompts",
        system_message=f'''You are an expert AI image prompt writer specialized in creating detailed and highly relevant prompts for generating high-quality, photorealistic images as of {current_date}.

Generate a detailed image prompt (60-80 words) that vividly describes the core subject of the user topic with precise context.

- For PLACES (beach, waterfall, fort, religion): Describe scenic views, architecture, landscapes, atmosphere, time of day, and important landmarks.
- For EVENTS (event, boat-party, entertainment): Describe the crowd, stage, decorations, activities, energy, and atmosphere.
- For RESTAURANTS (restaurant, dining-fine, dining-casual, dining-family, dining-seafood, dining-bar, dining-chinese): Describe the interior, food presentation, ambiance, architecture, people dining, or outdoor seating.
- For BLOGS (blog): Create a conceptual, informative image focusing purely on the topic in an illustrative or infographic style.
- For ACTIVITIES (water-sport, guide-tour, travel): Describe the activity, setting, equipment, and participants.

Ensure the prompt is focused only on the exact topic without generic elements, with a photorealistic style.

Examples:
- For 'Colva Beach': 'Photorealistic image of Colva Beach at sunset, golden sands, calm waves, palm trees, serene atmosphere, high-resolution.'
- For 'Sunburn Festival': 'Large crowd at Sunburn Festival with colorful stage lights, people dancing, energetic atmosphere, professional photography style.'
- For 'Joe's Pizza NYC': 'Cozy interior of Joe's Pizza, wooden tables, delicious pizza slices, warm lighting, photorealistic.'

Always return a coherent, descriptive prompt as plain text without quotes or extra formatting
''',
        model_client=model
    )
    thumbnail_prompt_agent = AssistantAgent(
        name="thumbnail_prompt_agent",
        description="Creates highly precise thumbnail-specific image prompts",
        system_message=f'''You are an expert at creating prompts for eye-catching thumbnail images designed to attract clicks as of {current_date}.

Generate a concise, focused prompt (20-30 words) for a square thumbnail image that directly represents the user topic in a highly relevant and specific way.

- Focus only on the core subject (event, place, restaurant, blog, activity).
- Avoid generic or unrelated concepts.
- Use vibrant colors, professional photography style, and clearly describe the subject.

Examples:
- For 'Colva Beach': 'Vibrant photo of Colva Beach, golden sands, calm waves, palm trees, high resolution.'
- For 'Sunburn Festival': 'Crowd at Sunburn Festival with colorful stage lights, energetic atmosphere, photorealistic.'
- For 'Joe's Pizza, NYC': 'Joe's Pizza storefront, neon sign, delicious pizza displayed, high-quality photography.'

Always return a single coherent sentence as plain text without quotes or extra formatting
''',
        model_client=model
    )
    
    seo_title_agent = AssistantAgent(
            name="seo_title_agent",
            description="Generates polished, SEO-optimized titles with proper grammar",
            system_message=f'''You are an SEO and content critic as of {current_date}. 
    Your job is to create two alternative titles for the given topic and content type. 
    Each title must:
    - Be concise, SEO-optimized, and grammatically correct.
    - Be 8-12 words, under 70 characters.
    - Clearly describe the topic with precise information.
    - Include strong keywords that improve search ranking.
    - Avoid repetition, fluff, or vague terms.

    ### TYPE-SPECIFIC RULES ###
    - PLACES (beach, waterfall, fort, religion): Include location, attractions, 'guide', 'travel tips'.
    - EVENTS (event, boat-party, entertainment): 
    - For festivals (e.g., Navratri, Diwali, Holi), focus on cultural significance, location, 'festival', 'celebration'.
    - Avoid 'tickets' or 'dates' unless explicitly mentioned in the topic.
    - For non-festival events, include event name, 'festival', 'experience', or 'tickets' if relevant.
    - For past events (before 2025), suggest a similar upcoming event.
    - RESTAURANTS: Include name, cuisine, 'menu', 'dining'.
    - BLOGS: Focus on topic, 'guide', 'tips', 'how-to'.
    - ACTIVITIES: Include activity, location, 'guide', 'experience'.

    ### OUTPUT FORMAT ###
    Return exactly 2 lines of plain text, each line being one polished SEO title.
    ''',
            model_client=model
        )

    transportation_options_agent = AssistantAgent(
        name="transportation_options_agent",
        description="Determines transportation options based on location",
        system_message=f'''You are an expert in travel logistics for Indian destinations as of {current_date}. 
Based on the provided topic, content type, and location data, determine the following transportation options:
- walkingOnly: Is the location accessible by walking only (e.g., pedestrian-only areas)?
- byBoat: Is the location accessible by boat (e.g., coastal or island destinations)?
- byCar: Is the location accessible by car (e.g., has roads or parking)?
- byPublicTransport: Is the location accessible by public transport (e.g., buses, trains, metro)?

Consider the location's characteristics (e.g., urban, rural, coastal, remote) and typical accessibility for Indian destinations.
Return ONLY a JSON object in this format:
{{"walkingOnly": true|false, "byBoat": true|false, "byCar": true|false, "byPublicTransport": true|false}}
''',
        model_client=model
    )
    return (content_classifier_agent, smart_location_agent, description_agent, tags_agent, content_agent,
            guidelines_agent, image_prompt_agent, thumbnail_prompt_agent, seo_title_agent,
            transportation_options_agent), model

# Safe run agent with retries
async def safe_run(agent, task, retries=2):
    """Safely runs an agent with retries and returns its output""" 
    for attempt in range(retries):
        try:
            result = await agent.run(task=task)
            if result:
                if isinstance(result, dict):
                    return result
                if hasattr(result, "messages") and result.messages and result.messages[-1].content.strip():
                    content = result.messages[-1].content.strip()
                    if content.startswith('{') and content.endswith('}'):
                        try:
                            return json.loads(content)
                        except:
                            pass
                    return content
        except Exception:
            continue
    if agent.name == "smart_location_agent":
        return {"should_fetch": False, "search_query": ""}
    return ""

# Get boolean options
async def get_boolean_options(content_type, user_topic, model):
    """Determine boolean options for the content""" 
    current_date = datetime.now().strftime("%B %d, %Y")
    options = {
        "active": False,
        "featured": False,
        "hasPickup": False,
        "internal": False,
        "bestSeller": False,
        "coupleFriendly": False,
        "groupFriendly": False,
        "hasOffer": False,
        "isGuestInfoNeeded": False,
        "isOpen": False,
        "kidsFriendly": False,
        "monsoon": datetime.now().month in [6, 7, 8, 9],  # Monsoon season in India (June-September)
        "promote": False,
        "trending": False,
        "offerCount": 0
    }
    if content_type in ["beach", "waterfall", "fort", "religion", "event", "restaurant", "boat-party", "guide-tour", "dining-fine", "dining-casual", "dining-family", "dining-seafood", "dining-bar", "dining-chinese", "entertainment"]:
        boolean_agent = AssistantAgent(
            name="boolean_options_agent",
            description="Determines specific boolean options for content",
            system_message=f'''You are an expert in travel and tourism content configuration as of {current_date}. 
For the given topic and content type, determine the following boolean options:
- coupleFriendly: Is this suitable for couples (romantic settings, private experiences)?
- groupFriendly: Is this suitable for groups (large spaces, group activities)?
- isOpen: Is this currently open or available (consider typical operating status as of {current_date})?
- kidsFriendly: Is this suitable for families with children (kid-friendly activities, safety)?

Topic: {user_topic}
Content Type: {content_type}

Return ONLY a JSON object in this format:
{{"coupleFriendly": true|false, "groupFriendly": true|false, "isOpen": true|false, "kidsFriendly": true|false}}
''',
            model_client=model
        )
        agent_result = await safe_run(boolean_agent, f"Determine boolean options for {content_type}: {user_topic}")
        if isinstance(agent_result, dict):
            options.update({
                "coupleFriendly": agent_result.get("coupleFriendly", False),
                "groupFriendly": agent_result.get("groupFriendly", False),
                "isOpen": agent_result.get("isOpen", False),
                "kidsFriendly": agent_result.get("kidsFriendly", False)
            })
    return options

# Generate images
def generate_image_pollinations(prompt, filename, width=1024, height=1024, seed=None, model="flux"):
    try:
        if seed is None:
            seed = int(datetime.now().timestamp() % 1000)
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width={width}&height={height}&seed={seed}&model={model}"
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        if img.height > 50:
            img = img.crop((0, 0, img.width, img.height - 50))
        data_url = convert_image_to_webp_and_encode_base64(img, target_width=800, target_height=600)
        img.save(filename.replace(".png", ".webp"), format="WEBP", quality=80)
        return data_url, filename.replace(".png", ".webp")
    except Exception:
        return "", ""
    
# Get type-specific content
def get_type_specific_content(content_type, user_topic):
    """Return type-specific content variations""" 
    type_configs = {
        "event": {"icon": "fa-duotone fa-calendar-star"},
        "restaurant": {"icon": "fa-duotone fa-utensils"},
        "blog": {"icon": "fa-duotone fa-book-open"},
        "beach": {"icon": "fa-duotone fa-umbrella-beach"},
        "waterfall": {"icon": "fa-duotone fa-water"},
        "fort": {"icon": "fa-duotone fa-fort"},
        "religion": {"icon": "fa-duotone fa-place-of-worship"},
        "travel": {"icon": "fa-duotone fa-plane-departure"},
        "water-sport": {"icon": "fa-duotone fa-person-swimming"},
        "boat-party": {"icon": "fa-duotone fa-ship"},
        "guide-tour": {"icon": "fa-duotone fa-map-signs"},
        "dining-fine": {"icon": "fa-duotone fa-glass-cheers"},
        "dining-casual": {"icon": "fa-duotone fa-utensils"},
        "dining-family": {"icon": "fa-duotone fa-users"},
        "dining-seafood": {"icon": "fa-duotone fa-fish"},
        "dining-bar": {"icon": "fa-duotone fa-cocktail"},
        "dining-chinese": {"icon": "fa-duotone fa-utensils"},
        "entertainment": {"icon": "fa-duotone fa-theater-masks"}
    }
    return type_configs.get(content_type, {"icon": "fa-duotone fa-book-open"})

# Clean tags
def clean_tags(tags, user_topic, content_type):
    """Ensure tags are strictly topic-related"""
    if not tags or not isinstance(tags, list):
        base_tag = user_topic.lower()
        if content_type in ["beach", "waterfall", "fort", "religion", "guide-tour"]:
            return [base_tag, f"{base_tag} location", f"{base_tag} guide", f"visit {base_tag}"]
        elif content_type in ["event", "boat-party", "entertainment"]:
            festival_keywords = ["navratri", "diwali", "holi", "sangod utsav", "shigmo utsav", "goa carnival"]
            if any(keyword in base_tag for keyword in festival_keywords):
                return [base_tag, f"{base_tag} festival", f"{base_tag} celebration", f"{base_tag} culture"]
            return [base_tag, f"{base_tag} tickets", f"{base_tag} dates", f"{base_tag} festival"]
        elif content_type in ["restaurant", "dining-fine", "dining-casual", "dining-family", "dining-seafood", "dining-bar", "dining-chinese"]:
            return [base_tag, f"{base_tag} menu", f"{base_tag} dining", f"{base_tag} food"]
        elif content_type in ["water-sport", "travel"]:
            return [base_tag, f"{base_tag} activities", f"{base_tag} experience", f"{base_tag} guide"]
        else:
            return [base_tag, f"{base_tag} guide", f"{base_tag} tips", f"{base_tag} information"]
    generic_tags = ['travel', 'tourism', 'vacation', 'holiday', 'trip', 'tour']
    cleaned_tags = []
    for tag in tags:
        tag_lower = tag.lower()
        if (user_topic.lower() in tag_lower or
            any(keyword in tag_lower for keyword in user_topic.lower().split()) or
            not any(gen in tag_lower for gen in generic_tags)):
            cleaned_tags.append(tag)
    if len(cleaned_tags) < 4:
        base_tag = user_topic.lower()
        additional_tags = [
            f"{base_tag} information",
            f"{base_tag} details",
            f"{base_tag} experience",
            f"{base_tag} visit"
        ]
        cleaned_tags.extend(additional_tags[:4-len(cleaned_tags)])
    return list(set(cleaned_tags))[:12]

# ===== ORIGINAL RUN AGENT FUNCTION (RENAMED) =====

async def run_agent_original(user_topic: str, more_details: str = None):
    """Runs all agents to generate content for a given topic using MagenticOneGroupChat""" 
    current_date = datetime.now().strftime("%B %d, %Y")
    goa_db = get_mongodb_connection()
    (content_classifier_agent, smart_location_agent, description_agent, tags_agent, content_agent,
     guidelines_agent, image_prompt_agent, thumbnail_prompt_agent, seo_title_agent,
     transportation_options_agent), model = teamConfig()

    # List of agents for the team
    agents = [
        content_classifier_agent, 
        smart_location_agent, 
        description_agent, 
        tags_agent, 
        content_agent, 
        guidelines_agent, 
        image_prompt_agent, 
        thumbnail_prompt_agent, 
        seo_title_agent, 
        transportation_options_agent
    ]

    # Create the MagenticOneGroupChat team without tools
    team = MagenticOneGroupChat(agents, model_client=model)

    # Run the team with the task
    task = f'''Generate travel content for topic: {user_topic}. Additional details: {more_details or 'None'}.

1. Use content_classifier_agent to classify the type as one of: beach, waterfall, fort, religion, travel, event, restaurant, blog, water-sport, boat-party, guide-tour, dining-fine, dining-casual, dining-family, dining-seafood, dining-bar, dining-chinese, entertainment.
2. Use smart_location_agent to determine if location data should be fetched and the exact search query.
3. If should_fetch is true, fetch location data (address, latitude, longitude) for the search_query.
4. Use description_agent to generate a short description (1-2 sentences) based on the classified type.
5. Use tags_agent to generate 8-12 SEO tags relevant to the topic.
6. Use content_agent to generate detailed HTML content with at least 5 paragraphs, using <p>, <ul>, <ol>, <li>, <strong>, <em>, <h2>, and <h3> tags.
7. Use guidelines_agent to generate 4-6 practical guidelines as plain text.
8. Use image_prompt_agent to generate a detailed image prompt (60-80 words) for a photorealistic image.
9. Use thumbnail_prompt_agent to generate a concise thumbnail prompt (20-30 words) for a square image.
10. Use seo_title_agent to generate two SEO-optimized titles (8-12 words each, under 70 characters).
11. Use transportation_options_agent to generate transportation options (walkingOnly, byBoat, byCar, byPublicTransport).

Return a single JSON object with the following keys:
- content_type: The classified type
- should_fetch_location: Boolean from smart_location_agent
- search_query: Search query from smart_location_agent
- location: Location data (address, latitude, longitude)
- description: Short description from description_agent
- tags: List of tags from tags_agent
- content: HTML content from content_agent
- guidelines: Guidelines from guidelines_agent
- image_prompt: Image prompt from image_prompt_agent
- thumbnail_prompt: Thumbnail prompt from thumbnail_prompt_agent
- seo_title: List of two SEO titles from seo_title_agent
- transportation_options: Transportation options from transportation_options_agent
'''

    # Run individual agents to ensure complete output
    content_type_result = await safe_run(content_classifier_agent, f"Classify the type for topic: {user_topic}")
    content_type = content_type_result.get("type", "beach" if "beach" in user_topic.lower() else "blog") if isinstance(content_type_result, dict) else "beach"

    location_result = await safe_run(smart_location_agent, f"Determine if location data should be fetched for topic: {user_topic}")
    should_fetch_location = location_result.get("should_fetch", True if "beach" in user_topic.lower() else False) if isinstance(location_result, dict) else True
    search_query = location_result.get("search_query", user_topic) if isinstance(location_result, dict) else user_topic

    # Manually fetch location if needed
    location = {"address": None, "latitude": 0.0, "longitude": 0.0}
    if should_fetch_location:
        location = fetch_location(search_query)

    description = await safe_run(description_agent, f"Generate a short description for {content_type}: {user_topic}")
    tags_result = await safe_run(tags_agent, f"Generate 8-12 SEO tags for {content_type}: {user_topic}")
    content = await safe_run(content_agent, f"Generate detailed HTML content for {content_type}: {user_topic}")
    guidelines = await safe_run(guidelines_agent, f"Generate 4-6 guidelines for {content_type}: {user_topic}")
    image_prompt = await safe_run(image_prompt_agent, f"Generate a detailed image prompt for {content_type}: {user_topic}")
    thumbnail_prompt = await safe_run(thumbnail_prompt_agent, f"Generate a thumbnail prompt for {content_type}: {user_topic}")
    seo_title = await safe_run(seo_title_agent, f"Generate two SEO titles for {content_type}: {user_topic}")
    transportation_options = await safe_run(transportation_options_agent, f"Generate transportation options for {content_type}: {user_topic}")

    # Process team result for additional context
    team_result = await team.run(task=task)
    parsed_result = {}
    if team_result.messages:
        last_message = team_result.messages[-1].content
        try:
            parsed_result = json.loads(last_message)
        except json.JSONDecodeError:
            pass

    # Combine individual agent results with team result, prioritizing individual results
    content_type = parsed_result.get("content_type", content_type)
    should_fetch_location = parsed_result.get("should_fetch_location", should_fetch_location)
    search_query = parsed_result.get("search_query", search_query)
    location = parsed_result.get("location", location)
    description = parsed_result.get("description", description if description else f"Explore {user_topic}, a stunning {content_type} destination.")
    tags_raw = parsed_result.get("tags", tags_result if isinstance(tags_result, dict) else {"tags": []})
    content = parsed_result.get("content", content if content else f"<p><strong>{user_topic}</strong>: No content generated.</p>")
    guidelines = parsed_result.get("guidelines", guidelines if guidelines else f"Follow local guidelines when visiting {user_topic}.")
    image_prompt = parsed_result.get("image_prompt", image_prompt if image_prompt else f"Photorealistic image of {user_topic} at sunset, serene atmosphere, high-resolution.")
    thumbnail_prompt = parsed_result.get("thumbnail_prompt", thumbnail_prompt if thumbnail_prompt else f"Vibrant square photo of {user_topic}, high resolution.")
    seo_title = parsed_result.get("seo_title", seo_title.split('\n') if isinstance(seo_title, str) and seo_title else [f"Explore {user_topic} in 2025", f"{user_topic} Travel Guide"])
    transportation_options = parsed_result.get("transportation_options", transportation_options if isinstance(transportation_options, dict) else {
        "walkingOnly": False, "byBoat": False, "byCar": True, "byPublicTransport": True
    })

    # Get boolean options
    try:
        boolean_options = await get_boolean_options(content_type, user_topic, model)
    except Exception as e:
        print(f"Error fetching boolean options: {e}")
        boolean_options = {
            "active": False,
            "featured": False,
            "hasPickup": False,
            "internal": False,
            "bestSeller": False,
            "coupleFriendly": True,
            "groupFriendly": True,
            "hasOffer": False,
            "isGuestInfoNeeded": False,
            "isOpen": True,
            "kidsFriendly": True,
            "monsoon": datetime.now().month in [6, 7, 8, 9],
            "promote": False,
            "trending": False,
            "offerCount": 0
        }

    # Handle location fetch if needed
    if should_fetch_location and not isinstance(location, dict):
        location = fetch_location(search_query)

    # Handle outdated event years
    if content_type == "event" and "2023" in user_topic:
        user_topic = user_topic.replace("2023", "2025")
        if "makharoutsav" in user_topic.lower():
            user_topic = "Goa Carnival 2025"

    # Get category ID
    category_id = get_category_id(goa_db, content_type)

    # Override location for events
    if content_type == "event" and should_fetch_location and isinstance(location, dict) and "address" in location and not location.get("error"):
        if ',' in user_topic:
            parts = [part.strip() for part in user_topic.split(',')]
            if len(parts) == 2 and parts[1].lower() in ['goa', 'maharashtra', 'karnataka']:
                location["address"] = parts[1].title()
            elif len(parts) >= 2:
                city = parts[-2].title() if len(parts) >= 2 else parts[-1].title()
                state = parts[-1].title() if len(parts) >= 3 and parts[-1].lower() in ['goa', 'maharashtra', 'karnataka'] else ''
                location["address"] = f"{city}{', ' + state if state else ''}"

    # Retry location fetch if non-Indian
    if should_fetch_location and isinstance(location, dict) and "address" in location and location.get("address") and not location.get("error"):
        location_address = location.get("address", "").lower()
        indian_indicators = ["india", "goa", "maharashtra", "karnataka", "kerala", "tamil nadu", "andhra pradesh", "odisha", "west bengal", "gujarat", "andaman"]
        is_indian_location = any(indicator in location_address for indicator in indian_indicators)
        if not is_indian_location:
            retry_location = fetch_location(f"{search_query}, India")
            if isinstance(retry_location, dict) and "address" in retry_location and not retry_location.get("error"):
                retry_address = retry_location.get("address", "").lower()
                retry_is_indian = any(indicator in retry_address for indicator in indian_indicators)
                if retry_is_indian:
                    location = retry_location
                    if content_type == "event" and ',' in user_topic:
                        parts = [part.strip() for part in user_topic.split(',')]
                        if len(parts) == 2 and parts[1].lower() in ['goa', 'maharashtra', 'karnataka']:
                            location["address"] = parts[1].title()
                        elif len(parts) >= 2:
                            city = parts[-2].title() if len(parts) >= 2 else parts[-1].title()
                            state = parts[-1].title() if len(parts) >= 3 and parts[-1].lower() in ['goa', 'maharashtra', 'karnataka'] else ''
                            location["address"] = f"{city}{', ' + state if state else ''}"
                else:
                    location["warning"] = "Non-Indian location detected"

    # Process tags
    tags = []
    if isinstance(tags_raw, dict):
        tags = tags_raw.get("tags", [])
    elif isinstance(tags_raw, str):
        try:
            tags = json.loads(tags_raw).get("tags", [])
        except:
            tags = [user_topic.lower()]
    tags = clean_tags(tags, user_topic, content_type)

    # Generate images
    main_filename = f"{content_type}-{user_topic.lower().replace(' ', '-')}.png"
    thumbnail_filename = f"thumbnail-{content_type}-{user_topic.lower().replace(' ', '-')}.png"
    image_data_url, saved_file = generate_image_pollinations(image_prompt, main_filename)
    thumbnail_data_url, thumbnail_file = generate_image_pollinations(thumbnail_prompt, thumbnail_filename, 512, 512)

    # Set location data
    type_config = get_type_specific_content(content_type, user_topic)
    if content_type in ["blog", "water-sport", "travel"] or (content_type == "event" and not should_fetch_location):
        location_data = {"address": None, "latitude": 0.0, "longitude": 0.0}
    elif isinstance(location, dict) and "error" not in location:
        location_data = location
        location_data["latitude"] = float(location_data.get("latitude", 0.0))
        location_data["longitude"] = float(location_data.get("longitude", 0.0))
    else:
        location_data = {"address": None, "latitude": 0.0, "longitude": 0.0}

    # Fetch city, area, and state IDs
    place_ids = {"city_id": None, "area_id": None, "state_id": None}
    if should_fetch_location and isinstance(location, dict) and "address" in location and location.get("address") and not location.get("error"):
        place_ids = find_place_ids(location["address"], goa_db)

    gallery_urls = []
    if image_data_url and image_data_url.startswith("data:image/webp;base64,"):
        gallery_urls.append(image_data_url)
    
    thumbnail_url = []
    if thumbnail_data_url and thumbnail_data_url.startswith("data:image/webp;base64,"):
        thumbnail_url.append(thumbnail_data_url)

    # Build final output
    output = {
        "_id": ObjectId(),
        "gallery": gallery_urls,
        "tags": tags,
        "categories": [ObjectId(category_id)] if category_id else [ObjectId()],
        "active": boolean_options.get("active", False),
        "featured": boolean_options.get("featured", False),
        "postType": content_type,
        "title": user_topic.title(),
        "slug": user_topic.lower().replace(' ', '-'),
        "shortDescription": description if description else f"Explore {user_topic}, a stunning {content_type} destination.",
        "seoTitle": seo_title[0] if isinstance(seo_title, list) and seo_title else f"Explore {user_topic} in 2025",
        "icon": type_config["icon"],
        "text": content if content else f"<p><strong>{user_topic}</strong>: No content generated.</p>",
        "guidelines": guidelines if guidelines else f"Follow local guidelines when visiting {user_topic}.",
        "location": location_data,
        "ways": transportation_options,
        "typeId": ObjectId(),
        "city": ObjectId(place_ids["city_id"]) if place_ids["city_id"] else None,
        "author": ObjectId(),
        "thumbnail": thumbnail_url,
        "createdAt": datetime.utcnow(),
        "rating": ObjectId(),
        "likes": ObjectId(),
        "views": ObjectId(),
        "__v": 0,
        "hasPickup": boolean_options.get("hasPickup", False),
        "internal": boolean_options.get("internal", False),
        "area": ObjectId(place_ids["area_id"]) if place_ids["area_id"] else None,
        "bestSeller": boolean_options.get("bestSeller", False),
        "coupleFriendly": boolean_options.get("coupleFriendly", False),
        "groupFriendly": boolean_options.get("groupFriendly", False),
        "hasOffer": boolean_options.get("hasOffer", False),
        "isGuestInfoNeeded": boolean_options.get("isGuestInfoNeeded", False),
        "isOpen": boolean_options.get("isOpen", False),
        "kidsFriendly": boolean_options.get("kidsFriendly", False),
        "monsoon": boolean_options.get("monsoon", False),
        "offerCount": boolean_options.get("offerCount", 0),
        "promote": boolean_options.get("promote", False),
        "state": ObjectId(place_ids["state_id"]) if place_ids["state_id"] else None,
        "trending": boolean_options.get("trending", False)
    }

    # Save output to JSON file
    json_output = json.loads(json.dumps(output, default=str))
    filename_json = f"{content_type}-{user_topic.lower().replace(' ', '_')}_output.json"
    with open(filename_json, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)

    # Insert into MongoDB
    insert_into_mongodb(output, goa_db)

    # Retrieve and format document
    document = get_document(output["slug"], goa_db)
    formatted_json = format_document(document) if document else None

    return output, saved_file, thumbnail_file, filename_json, content_type, goa_db, formatted_json

async def run_agent_original_with_validation(user_topic: str, more_details: str = None):
    """Enhanced version with proper location validation and NO double-fetching"""
    current_date = datetime.now().strftime("%B %d, %Y")
    goa_db = get_mongodb_connection()

    # Get model
    openrouter_key = os.getenv("OPENROUTER_KEY")
    if not openrouter_key:
        if os.path.exists("api.txt"):
            openrouter_key = open("api.txt").read().strip()
        else:
            raise RuntimeError("No OpenRouter API key found.")

    model = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=openrouter_key,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=500
    )

    print("🤖 Classifying content type...")
    content_type_result = await safe_run(create_classifier_agent(model, current_date), f"Classify the type for topic: {user_topic}")
    content_type = content_type_result.get("type", "blog") if isinstance(content_type_result, dict) else "blog"
    print(f"📝 Content type: {content_type}")

    print("📍 Deciding if location is needed...")
    location_decision = await safe_run(create_smart_location_agent(model, current_date), f"Determine if location data should be fetched for topic: {user_topic}")
    should_fetch_location = location_decision.get("should_fetch", True)
    search_query = location_decision.get("search_query", user_topic).strip()

    print(f"📍 Should fetch: {should_fetch_location} | Query: '{search_query}'")

    # THIS IS THE KEY: Use validated location fetch
    location_data = {"address": None, "latitude": 0.0, "longitude": 0.0}
    if should_fetch_location and search_query:
        location_data = await fetch_and_validate_location(user_topic, search_query, content_type, model)
        if location_data.get("error") or not location_data.get("address"):
            print("⚠️ Falling back to basic fetch...")
            location_data = fetch_location(f"{search_query}, Goa, India")  # Final fallback
    else:
        print("ℹ️ Location not needed for this content type")

    # Now run all other agents (same as before)
    (content_classifier_agent, smart_location_agent, description_agent, tags_agent, content_agent,
     guidelines_agent, image_prompt_agent, thumbnail_prompt_agent, seo_title_agent,
     transportation_options_agent), model_full = teamConfig()

    description = await safe_run(description_agent, f"Generate a short description for {content_type}: {user_topic}")
    tags_result = await safe_run(tags_agent, f"Generate 8-12 SEO tags for {content_type}: {user_topic}")
    content = await safe_run(content_agent, f"Generate detailed HTML content for {content_type}: {user_topic}")
    guidelines = await safe_run(guidelines_agent, f"Generate 4-6 guidelines for {content_type}: {user_topic}")
    image_prompt = await safe_run(image_prompt_agent, f"Generate a detailed image prompt for {content_type}: {user_topic}")
    thumbnail_prompt = await safe_run(thumbnail_prompt_agent, f"Generate a thumbnail prompt for {content_type}: {user_topic}")
    seo_title = await safe_run(seo_title_agent, f"Generate two SEO titles for {content_type}: {user_topic}")
    transportation_options = await safe_run(transportation_options_agent, f"Generate transportation options for {content_type}: {user_topic}")
    boolean_options = await get_boolean_options(content_type, user_topic, model_full)

    # Process tags
    tags = []
    if isinstance(tags_result, dict):
        tags = tags_result.get("tags", [])
    elif isinstance(tags_result, str):
        try:
            tags = json.loads(tags_result).get("tags", [])
        except:
            pass
    tags = clean_tags(tags, user_topic, content_type)

    # Generate images
    main_filename = f"{content_type}-{user_topic.lower().replace(' ', '-')}.png"
    thumbnail_filename = f"thumbnail-{content_type}-{user_topic.lower().replace(' ', '-')}.png"
    image_data_url, saved_file = generate_image_pollinations(image_prompt, main_filename)
    thumbnail_data_url, thumbnail_file = generate_image_pollinations(thumbnail_prompt, thumbnail_filename, 512, 512)

    # Use OUR validated location_data — DO NOT refetch!
    final_location = {
        "address": location_data.get("address"),
        "latitude": float(location_data.get("latitude", 0.0)),
        "longitude": float(location_data.get("longitude", 0.0))
    } if location_data.get("address") else {"address": None, "latitude": 0.0, "longitude": 0.0}

    # Find place IDs
    place_ids = find_place_ids(final_location.get("address"), goa_db) if final_location.get("address") else {"city_id": None, "area_id": None, "state_id": None}

    # Build output
    type_config = get_type_specific_content(content_type, user_topic)
    category_id = get_category_id(goa_db, content_type)

    output = {
        "_id": ObjectId(),
        "gallery": [image_data_url] if image_data_url else [],
        "tags": tags,
        "categories": [ObjectId(category_id)] if category_id else [],
        "active": True,
        "featured": False,
        "postType": content_type,
        "title": user_topic.title(),
        "slug": user_topic.lower().replace(' ', '-'),
        "shortDescription": description or f"Discover {user_topic}, a beautiful destination in Goa.",
        "seoTitle": seo_title[0] if isinstance(seo_title, list) and seo_title else f"Explore {user_topic} - Goa Travel Guide",
        "icon": type_config.get("icon", "fa-duotone fa-book-open"),
        "text": content or f"<p>Explore {user_topic} – a must-visit spot in Goa.</p>",
        "guidelines": guidelines or "Always respect local rules and nature.",
        "location": final_location,
        "ways": transportation_options or {"walkingOnly": False, "byBoat": False, "byCar": True, "byPublicTransport": True},
        "typeId": ObjectId(),
        "city": ObjectId(place_ids["city_id"]) if place_ids["city_id"] else None,
        "author": ObjectId(),
        "thumbnail": [thumbnail_data_url] if thumbnail_data_url else [],
        "createdAt": datetime.utcnow(),
        **boolean_options
    }

    # Save
    json_output = json.loads(json.dumps(output, default=str))
    filename_json = f"{content_type}-{user_topic.lower().replace(' ', '_')}_output.json"
    with open(filename_json, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)

    insert_into_mongodb(output, goa_db)
    document = get_document(output["slug"], goa_db)
    formatted_json = format_document(document) if document else None

    return output, saved_file, thumbnail_file, filename_json, content_type, goa_db, formatted_json

# ===== FALLBACK CONTENT GENERATION FUNCTION =====
async def generate_basic_fallback(user_topic: str, more_details: str, goa_db):
    """Simple backup content when main generator fails"""
    print("🔄 Using fallback content generation...")
    
    # Create basic content without any AI agents
    basic_content = {
        "_id": ObjectId(),
        "gallery": [],
        "tags": [user_topic.lower(), f"{user_topic} guide", f"visit {user_topic}"],
        "categories": [get_category_id(goa_db, "blog")], 
        "active": True,
        "featured": False,
        "postType": "blog", 
        "title": user_topic.title(),
        "slug": user_topic.lower().replace(' ', '-'),
        "shortDescription": f"{user_topic} is a popular destination worth exploring.",
        "seoTitle": f"Visit {user_topic} - Travel Guide",
        "icon": "fa-duotone fa-book-open",
        "text": f"<p>Welcome to {user_topic}. This destination offers unique experiences for travelers.</p><p>Plan your visit and explore the local attractions.</p>",
        "guidelines": f"Check local guidelines before visiting {user_topic}.",
        "location": {"address": None, "latitude": 0.0, "longitude": 0.0},
        "ways": {"walkingOnly": False, "byBoat": False, "byCar": True, "byPublicTransport": True},
        "typeId": ObjectId(),
        "city": None,
        "author": ObjectId(),
        "thumbnail": [],
        "createdAt": datetime.utcnow(),
        "rating": ObjectId(),
        "likes": ObjectId(),
        "views": ObjectId(),
        "__v": 0,
        "hasPickup": False,
        "internal": False,
        "area": None,
        "bestSeller": False,
        "coupleFriendly": False,
        "groupFriendly": False,
        "hasOffer": False,
        "isGuestInfoNeeded": False,
        "isOpen": False,
        "kidsFriendly": False,
        "monsoon": False,
        "offerCount": 0,
        "promote": False,
        "state": None,
        "trending": False
    }
    
    # Save to database
# In generate_basic_fallback, add try-catch around MongoDB operations
    try:
        # Save to database
        insert_into_mongodb(basic_content, goa_db)
        
        # Create JSON file
        filename_json = f"fallback-{user_topic.lower().replace(' ', '_')}_output.json"
        with open(filename_json, "w", encoding="utf-8") as f:
            json.dump(basic_content, f, indent=2, ensure_ascii=False, default=str)
        
        formatted_json = format_document(basic_content) if get_document(basic_content["slug"], goa_db) else None
        
        return basic_content, None, None, filename_json, "blog", goa_db, formatted_json
    except Exception as e:
        print(f"❌ Fallback generation error: {e}")
        # Return minimal content as last resort
        return basic_content, None, None, None, "blog", goa_db, None

# ===== SMART CONTENT GENERATION FUNCTION =====

async def smart_content_generation(user_topic: str, more_details: str = None):
    """Smart content generation with location validation"""
    current_date = datetime.now()
    goa_db = get_mongodb_connection()
    
    # First, check if content already exists
    existing_doc = get_document_by_topic(user_topic, goa_db)
    
    if existing_doc:
        print(f"✅ Found existing content for: '{user_topic}'")
        
        # Initialize agents for validation and updates
        (content_classifier_agent, smart_location_agent, description_agent, tags_agent, content_agent,
         guidelines_agent, image_prompt_agent, thumbnail_prompt_agent, seo_title_agent,
         transportation_options_agent), model = teamConfig()
        
        # VALIDATE EXISTING LOCATION IN DATABASE
        print("🔍 Validating existing location in database...")
        location_validation = await validate_existing_location_in_db(
            existing_doc, user_topic, existing_doc.get('postType', 'blog'), model
        )
        
        created_at = existing_doc.get('createdAt')
        updated_fields = {}
        updates_made = []
        
        # 1. Check and Update LOCATION if invalid
        if location_validation.get("needs_update", False):
            print(f"📍 Existing location invalid: {location_validation.get('reason', 'Unknown reason')}")
            print("🔄 Updating location...")
            
            location_result = await safe_run(smart_location_agent, f"Determine if location data should be fetched for topic: {user_topic}")
            should_fetch_location = location_result.get("should_fetch", True)
            search_query = location_result.get("search_query", user_topic)
            
            if should_fetch_location:
                print(f"🔍 Fetching new location with query: '{search_query}'")
                new_location = await fetch_and_validate_location(user_topic, search_query, existing_doc.get('postType', 'blog'), model)
                
                if new_location and not new_location.get("error") and new_location.get("address"):
                    updated_fields['location'] = {
                        "address": new_location.get("address"),
                        "latitude": new_location.get("latitude", 0.0),
                        "longitude": new_location.get("longitude", 0.0)
                    }
                    updates_made.append('location')
                    print(f"✅ Location updated to: {new_location.get('address')}")
                else:
                    print("❌ Failed to fetch valid location")
        
        # 2. Check and Update DESCRIPTION
        old_description = existing_doc.get('shortDescription', '')
        if needs_field_update(old_description, user_topic, created_at, is_content_field=False):
            print("🔄 Updating description...")
            new_description = await safe_run(description_agent, f"Generate accurate description for {user_topic}")
            if new_description and new_description.strip():
                updated_fields['shortDescription'] = new_description
                updates_made.append('description')
                print("✅ Description updated")
        
        # 3. Check and Update CONTENT
        old_content = existing_doc.get('text', '')
        if needs_field_update(old_content, user_topic, created_at, is_content_field=True):
            print("🔄 Updating content...")
            content_type = existing_doc.get('postType', 'blog')
            new_content = await safe_run(content_agent, f"Generate accurate content for {content_type}: {user_topic}")
            if new_content and new_content.strip():
                updated_fields['text'] = new_content
                updates_made.append('content')
                print("✅ Content updated")
        
        # 4. Check and Update GUIDELINES
        old_guidelines = existing_doc.get('guidelines', '')
        if needs_field_update(old_guidelines, user_topic, created_at, is_content_field=False):
            print("🔄 Updating guidelines...")
            content_type = existing_doc.get('postType', 'blog')
            new_guidelines = await safe_run(guidelines_agent, f"Generate accurate guidelines for {content_type}: {user_topic}")
            if new_guidelines and new_guidelines.strip():
                updated_fields['guidelines'] = new_guidelines
                updates_made.append('guidelines')
                print("✅ Guidelines updated")
        
        # Update the document if any fields were updated
        if updated_fields:
            slug = existing_doc.get('slug', user_topic.lower().replace(' ', '-'))
            print(f"💾 Updating database for slug: {slug}")
            success = update_document_partial(goa_db, slug, updated_fields)
            if success:
                print(f"✅ Database updated with: {', '.join(updates_made)}")
            else:
                print("❌ Failed to update database")
            
            # Refresh the document
            updated_doc = get_document_by_topic(user_topic, goa_db)
            formatted_json = format_document(updated_doc) if updated_doc else None
            
            return updated_doc, None, None, None, updated_doc.get('postType', 'blog'), goa_db, formatted_json
        else:
            print("✅ No updates needed - returning existing content")
            formatted_json = format_document(existing_doc)
            return existing_doc, None, None, None, existing_doc.get('postType', 'blog'), goa_db, formatted_json
    
    else:
        # No existing content - do full generation with validated location
        print(f"🆕 No existing content found, generating new content for: '{user_topic}'")
        try:
            # Use enhanced version that validates location
            return await run_agent_original_with_validation(user_topic, more_details)
        except Exception as e:
            print(f"❌ Generation failed: {e}")
            print("🔄 Switching to fallback content generation...")
            return await generate_basic_fallback(user_topic, more_details, goa_db)
                
# ===== MAIN FUNCTION (UPDATED) =====

def main():
    """Gets user topic and starts SMART content generation"""
    parser = argparse.ArgumentParser(description="Generate travel content for a topic.")
    parser.add_argument("topic", nargs='?', default=None, help="Topic for content generation (e.g., 'Colva Beach')")
    parser.add_argument("details", nargs='?', default=None, help="Additional details about the topic (optional)")
    args = parser.parse_args()

    try:
        if args.topic:
            user_topic = args.topic.strip()
            more_details = args.details.strip() if args.details else None
        else:
            print("🔹 Enter a topic (or press Ctrl+C to exit): ", end="", flush=True)
            try:
                user_topic = input().strip()
            except EOFError:
                print("\n❌ Input failed - running in non-interactive mode. Use: python travel_content_generator.py 'topic' ['details']")
                return
            if not user_topic:
                print("❌ No topic entered. Exiting.")
                return
            print("🔹 Enter more about the topic (optional, press enter to skip): ", end="", flush=True)
            more_details = input().strip() or None

        print(f"🔍 [Smart Mode] Processing: '{user_topic}'")
        output, saved_file, thumbnail_file, json_file, content_type, goa_db, formatted_json = asyncio.run(smart_content_generation(user_topic, more_details))
        
        print(f"\n✅ Smart generation complete! Type: {content_type}")
        
        # Check if this was an update or new generation
        existing = get_document_by_topic(user_topic, goa_db)
        if existing:
            print("📊 Content was RETURNED/IMPROVED from database")
        else:
            print("🆕 Content was GENERATED as new")
        
        print("\n📦 Final Output:")
        print(json.dumps(output, default=str, indent=2))
        
        if saved_file:
            print(f"\n🖼 Main image: {saved_file}")
        if thumbnail_file:
            print(f"📸 Thumbnail: {thumbnail_file}")
        if json_file:
            print(f"📄 JSON file: {json_file}")
            
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
    # End of script
