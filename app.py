import streamlit as st
import asyncio
import json
from datetime import datetime
from io import BytesIO
from PIL import Image
import base64

# Import the necessary functions and classes from the provided script
from optimizetreavel import (
   smart_content_generation, get_mongodb_connection, get_document, format_document
)

# Streamlit App Configuration
st.set_page_config(
    page_title="AI Powered Travel Guide ",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar for instructions and configuration
st.sidebar.header("Quick Guide")
st.sidebar.markdown("""
- Enter a topic (e.g., "Colva Beach")
""")

# Custom CSS for map
st.markdown("""
<style>
.map-container {
    border-radius: 10px;
    border: 2px solid #ddd;
    margin: 10px 0;
    overflow: hidden;
}
.map-responsive {
    width: 100%;
    height: 400px;
    border: none;
}
.location-info {
    background: #000000;
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 10px;
    font-family: Arial, sans-serif;
}
</style>
""", unsafe_allow_html=True)

# Main App
st.title("AI Powered Travel Guide")
st.markdown("Ask about travel guides, event details, restaurant reviews, and more for Indian hotspots.")

# Integrated Search Section
st.subheader("Search or Create Content")

# Create input section with single Search button
col1, col2 = st.columns([3, 1])
with col1:
    topic = st.text_input(
        "Enter topic",
        placeholder="e.g., Colva Beach or Shigmo Utsav, Goa",
        value="",
        label_visibility="collapsed"
    )
with col2:
    search_btn = st.button("Search", type="primary", use_container_width=True)

col3, col4 = st.columns([3, 1])
with col3:
    details = st.text_area(
        "Additional Details (Optional)",
        placeholder="e.g., state, city ",
        height=50,
        label_visibility="collapsed"
    )
with col4:
    if st.button("Clear", type="secondary", use_container_width=True):
        # Clear session state
        for key in ['generated', 'output', 'saved_file', 'thumbnail_file', 
                   'json_file', 'content_type', 'goa_db', 'formatted_json']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

# Helper function to check if document exists
def check_document_exists(topic, goa_db):
    """Check if a document exists for the given topic"""
    if goa_db is None:
        return None
    
    try:
        collection = goa_db["OUTPUT"]
        
        # Try to find by slug
        slug = topic.lower().replace(' ', '-')
        document = collection.find_one({"slug": slug})
        
        # If not found, try by title
        if not document:
            document = collection.find_one({"title": {"$regex": f"^{topic}$", "$options": "i"}})
        
        return document
    except Exception:
        return None

# Process Search button
if search_btn and topic.strip():
    with st.spinner("Searching and processing..."):
        try:
            # Use smart_content_generation which checks if content exists
            output, saved_file, thumbnail_file, json_file, content_type, goa_db, formatted_json = asyncio.run(
                smart_content_generation(topic.strip(), details.strip() if details.strip() else None)
            )

            # Store in session state
            st.session_state.generated = True
            st.session_state.output = output
            st.session_state.saved_file = saved_file
            st.session_state.thumbnail_file = thumbnail_file
            st.session_state.json_file = json_file
            st.session_state.content_type = content_type
            st.session_state.goa_db = goa_db
            st.session_state.formatted_json = formatted_json

            # Check if this was existing content or newly generated
            existing_doc = check_document_exists(topic.strip(), goa_db)
            
            # Determine message based on whether content existed before
            if existing_doc and existing_doc.get('_id'):
                st.success(f" Found existing content for '{topic}'! Type: {content_type}")
            else:
                st.success(f"Generated new content for '{topic}'! Type: {content_type}")

            # Refresh to show map
            st.rerun()

        except Exception as e:
            st.error(f"Error during processing: {str(e)}")
            st.exception(e)



# Display map if content is available
if 'generated' in st.session_state and st.session_state.generated and st.session_state.output:
    output = st.session_state.output
    
        # SEO Titles
    st.subheader("Titles")
    seo_titles = output.get("seoTitle", [])
    if isinstance(seo_titles, list):
        for i, title in enumerate(seo_titles[:2], 1):
            st.write(f"{i}. {title}")
    else:
        st.write(seo_titles)


    # Display dynamic map if location data is available
    location = output.get("location", {})
    if location and location.get("latitude") and location.get("longitude"):
        st.subheader(" Location Map")
        
        # Create map HTML using OpenStreetMap
        lat = float(location.get("latitude", 0))
        lon = float(location.get("longitude", 0))
        address = location.get("address", output.get("title", "Location"))
        
        map_html = f'''
        <div class="map-container">
            <div class="location-info">
                <strong> {output.get("title", "Location")}</strong><br>
                <small>{address}</small><br>
                <small>Coordinates: {lat:.6f}, {lon:.6f}</small>
            </div>
            <iframe 
                class="map-responsive"
                src="https://www.openstreetmap.org/export/embed.html?bbox={lon-0.01}%2C{lat-0.01}%2C{lon+0.01}%2C{lat+0.01}&layer=mapnik&marker={lat}%2C{lon}"
                scrolling="no">
            </iframe>
            <br/>
            <small>
                <a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=15/{lat}/{lon}">View Larger Map</a>
            </small>
        </div>
        '''
        st.markdown(map_html, unsafe_allow_html=True)
    # Location
    st.subheader("Location Details")
    if location.get("address"):
        st.write(f"Address: {location['address']}")
        st.write(f"Lat/Lng: {location.get('latitude', 0.0)}, {location.get('longitude', 0.0)}")
    else:
        st.write("No specific location data.")

    # Display Key Outputs
    st.header("Content Overview")


    # Short Description
    st.subheader("Short Description")
    st.write(output.get("shortDescription", "No description available."))


    # Transportation Options
    st.subheader("Transportation Options")
    ways = output.get("ways", {})
    if isinstance(ways, dict):
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        with col_t1: st.metric("Walking Only", "Yes" if ways.get("walkingOnly", False) else "No")
        with col_t2: st.metric("By Boat", "Yes" if ways.get("byBoat", False) else "No")
        with col_t3: st.metric("By Car", "Yes" if ways.get("byCar", False) else "No")
        with col_t4: st.metric("Public Transport", "Yes" if ways.get("byPublicTransport", False) else "No")

    # Guidelines
    st.subheader("Guidelines")
    guidelines = output.get("guidelines", "No guidelines available.")
    st.write(guidelines)

    # Main Content
    st.subheader("Detailed Content")
    content = output.get("text", "<p>No content generated.</p>")
    st.markdown(content, unsafe_allow_html=True)

    # Images
    st.subheader("Images")
    col_thumb, col_gallery = st.columns([1, 3])
    with col_thumb:
        st.subheader("Thumbnail")
        thumbnail = output.get("thumbnail", [])
        if thumbnail and len(thumbnail) > 0:
            try:
                thumb_img = thumbnail[0]
                if isinstance(thumb_img, str) and (thumb_img.startswith('data:') or thumb_img.startswith('http')):
                    st.image(thumb_img, caption="Thumbnail", width=300)
                else:
                    st.warning("Thumbnail data invalid - skipping display.")
            except Exception as img_err:
                st.warning(f"Error displaying thumbnail: {str(img_err)}")
        else:
            st.info("No thumbnail generated.")
    with col_gallery:
        st.subheader("Gallery")
        gallery = output.get("gallery", [])
        if gallery:
            cols = st.columns(1)
            for i, img_data_url in enumerate(gallery[:1]):
                try:
                    if isinstance(img_data_url, str) and (img_data_url.startswith('data:') or img_data_url.startswith('http')):
                        with cols[i]:
                            st.image(img_data_url, caption=f"Gallery Image {i+1}", width=300)
                    else:
                        st.warning(f"Gallery image {i+1} data invalid - skipping.")
                except Exception as img_err:
                    st.warning(f"Error displaying gallery image {i+1}: {str(img_err)}")
        else:
            st.info("No gallery images generated.")

# Tags
    st.subheader("Tags")
    tags = output.get("tags", [])
    if tags:
        for tag in tags:
            st.write(tag)
    else:
        st.write("No tags generated.")

    # Boolean Options
    st.subheader("Content Flags")
    flags = {
        "Active": output.get("active", False),
        "Featured": output.get("featured", False),
        "Couple Friendly": output.get("coupleFriendly", False),
        "Group Friendly": output.get("groupFriendly", False),
        "Kids Friendly": output.get("kidsFriendly", False),
        "Trending": output.get("trending", False),
        "Monsoon Suitable": output.get("monsoon", False),
        "Open Now": output.get("isOpen", False)
    }
    for key, value in flags.items():
        st.write(f"{key}: {'Yes' if value else 'No'}")

    if hasattr(st.session_state, 'json_file') and st.session_state.json_file:
        st.info(f"Files saved locally:\n- JSON: {st.session_state.json_file}")
        if hasattr(st.session_state, 'saved_file') and st.session_state.saved_file:
            st.write(f"- Main Image: {st.session_state.saved_file}")
        if hasattr(st.session_state, 'thumbnail_file') and st.session_state.thumbnail_file:
            st.write(f"- Thumbnail: {st.session_state.thumbnail_file}")

    if st.session_state.goa_db is not None:
        st.info("Connected to MongoDB - Data saved!")
    else:
        st.info("MongoDB not connected - Data saved to JSON only.")

# Footer
st.markdown("---")
st.markdown("Developed by Suraj Gawas")