import streamlit as st
import asyncio
import json
from datetime import datetime
from io import BytesIO
from PIL import Image
import base64

# Import the necessary functions and classes from the provided script
from optimizetreavel import (
    run_agent, get_mongodb_connection, insert_into_mongodb, get_document, format_document
)

# Streamlit App Configuration
st.set_page_config(
    page_title="Travel Content Generator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar for instructions and configuration
st.sidebar.header("Quick Guide")
st.sidebar.markdown("""
- Enter a topic (e.g., "Colva Beach").
- Add optional details for customization.
- Click Generate to create content.
- Results include JSON, images, and MongoDB (if connected).

Setup: Ensure API keys and dependencies (autogen, pymongo) are configured.
""")

# Main App
st.title("Travel Content Generator")
st.markdown("Ask about travel guides, event details, restaurant reviews, and more for Indian hotspots.")

# Session state to manage form submission
if 'generated' not in st.session_state:
    st.session_state.generated = False

# Tabs for Generate vs. Search
tab1, tab2 = st.tabs(["Generate New", "Search Existing"])

with tab1:
    # Input Fields
    topic = st.text_input("Enter Topic", placeholder="e.g., Colva Beach or Shigmo Utsav, Goa", value="")
    details = st.text_area("Additional Details (Optional)", placeholder="e.g., Focus on water sports", height=50)

    if st.button("Generate Content", type="primary", use_container_width=True):
        if not topic.strip():
            st.error("Please enter a topic!")
        else:
            with st.spinner("Running AI agents... This may take 1-2 minutes."):
                try:
                    # Run the async function
                    output, saved_file, thumbnail_file, json_file, content_type, goa_db, formatted_json = asyncio.run(
                        run_agent(topic.strip(), details.strip() if details.strip() else None)
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

                    st.success(f"Content generated for '{topic}'! Type: {content_type}")

                    # Display Key Outputs
                    st.header("Generated Content Overview")

                    # Short Description
                    st.subheader("Short Description")
                    st.write(st.session_state.output.get("shortDescription", "No description available."))

                    # SEO Titles
                    st.subheader("SEO Titles")
                    seo_titles = st.session_state.output.get("seoTitle", [])
                    if isinstance(seo_titles, list):
                        for i, title in enumerate(seo_titles[:2], 1):
                            st.write(f"{i}. {title}")
                    else:
                        st.write(seo_titles)

                    # Tags
                    st.subheader("SEO Tags")
                    tags = st.session_state.output.get("tags", [])
                    if tags:
                        for tag in tags:
                            st.write(tag)
                    else:
                        st.write("No tags generated.")

                    # Location
                    st.subheader("Location Details")
                    location = st.session_state.output.get("location", {})
                    if location.get("address"):
                        st.write(f"Address: {location['address']}")
                        st.write(f"Lat/Lng: {location.get('latitude', 0.0)}, {location.get('longitude', 0.0)}")
                    else:
                        st.write("No specific location data.")

                    # Transportation Options
                    st.subheader("Transportation Options")
                    ways = st.session_state.output.get("ways", {})
                    if isinstance(ways, dict):
                        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                        with col_t1: st.metric("Walking Only", "Yes" if ways.get("walkingOnly", False) else "No")
                        with col_t2: st.metric("By Boat", "Yes" if ways.get("byBoat", False) else "No")
                        with col_t3: st.metric("By Car", "Yes" if ways.get("byCar", False) else "No")
                        with col_t4: st.metric("Public Transport", "Yes" if ways.get("byPublicTransport", False) else "No")

                    # Guidelines
                    st.subheader("Practical Guidelines")
                    guidelines = st.session_state.output.get("guidelines", "No guidelines available.")
                    st.write(guidelines)

                    # Main Content
                    st.subheader("Detailed Content")
                    content = st.session_state.output.get("text", "<p>No content generated.</p>")
                    st.markdown(content, unsafe_allow_html=True)

                    # Images
                    st.subheader("Generated Images")
                    col_thumb, col_gallery = st.columns([1, 3])
                    with col_thumb:
                        st.subheader("Featured Thumbnail")
                        thumbnail = st.session_state.output.get("thumbnail", [])
                        if thumbnail and len(thumbnail) > 0:
                            try:
                                thumb_img = thumbnail[0]
                                if isinstance(thumb_img, str) and (thumb_img.startswith('data:') or thumb_img.startswith('http')):
                                    st.image(thumb_img, caption="Thumbnail", width=200)
                                else:
                                    st.warning("Thumbnail data invalid - skipping display.")
                            except Exception as img_err:
                                st.warning(f"Error displaying thumbnail: {str(img_err)}")
                        else:
                            st.info("No thumbnail generated.")
                    with col_gallery:
                        st.subheader("Gallery")
                        gallery = st.session_state.output.get("gallery", [])
                        if gallery:
                            cols = st.columns(3)
                            for i, img_data_url in enumerate(gallery[:3]):
                                try:
                                    if isinstance(img_data_url, str) and (img_data_url.startswith('data:') or img_data_url.startswith('http')):
                                        with cols[i]:
                                            st.image(img_data_url, caption=f"Gallery Image {i+1}", width=200)
                                    else:
                                        st.warning(f"Gallery image {i+1} data invalid - skipping.")
                                except Exception as img_err:
                                    st.warning(f"Error displaying gallery image {i+1}: {str(img_err)}")
                        else:
                            st.info("No gallery images generated.")

                    # Boolean Options
                    st.subheader("Content Flags")
                    flags = {
                        "Active": st.session_state.output.get("active", False),
                        "Featured": st.session_state.output.get("featured", False),
                        "Couple Friendly": st.session_state.output.get("coupleFriendly", False),
                        "Group Friendly": st.session_state.output.get("groupFriendly", False),
                        "Kids Friendly": st.session_state.output.get("kidsFriendly", False),
                        "Trending": st.session_state.output.get("trending", False),
                        "Monsoon Suitable": st.session_state.output.get("monsoon", False),
                        "Open Now": st.session_state.output.get("isOpen", False)
                    }
                    for key, value in flags.items():
                        st.write(f"{key}: {'Yes' if value else 'No'}")

                    # Expanders for Heavy Outputs
                    with st.expander("Full JSON Output (Raw)", expanded=False):
                        st.json(st.session_state.output)

                    if st.session_state.formatted_json is not None:
                        with st.expander("Formatted MongoDB Output", expanded=False):
                            st.code(st.session_state.formatted_json, language="json")

                    st.info(f"Files saved locally:\n- JSON: {st.session_state.json_file}\n- Main Image: {st.session_state.saved_file}\n- Thumbnail: {st.session_state.thumbnail_file}")

                    if st.session_state.goa_db is not None:
                        st.info("Connected to MongoDB - Data inserted!")
                    else:
                        st.info("MongoDB not connected - Data saved to JSON only.")

                except Exception as e:
                    st.error(f"Error during generation: {str(e)}")
                    st.exception(e)

with tab2:
    # Search Existing Content
    st.subheader("Search Existing Content")
    search_topic = st.text_input("Enter Topic/Slug to Search", placeholder="e.g., colva-beach or Colva Beach")

    if st.button("Search", type="secondary", use_container_width=True) and search_topic.strip():
        goa_db = get_mongodb_connection()
        if goa_db is not None:
            slug = search_topic.lower().replace(" ", "-")
            doc = get_document(slug, goa_db)
            if not doc:
                from pymongo import MongoClient
                client = MongoClient(goa_db.client.address)
                collection = client['goa-app']['OUTPUT']
                doc = collection.find_one({"title": {"$regex": search_topic, "$options": "i"}})

            if doc:
                st.success(f"Found: {doc.get('title', 'Unknown')}")

                st.subheader("Retrieved Content")
                st.subheader("Short Description")
                st.write(doc.get("shortDescription", "No description."))

                st.subheader("Detailed Content")
                st.markdown(doc.get("text", "<p>No content.</p>"), unsafe_allow_html=True)

                st.subheader("Images")
                col_thumb, col_gallery = st.columns([1, 3])
                with col_thumb:
                    st.subheader("Featured Thumbnail")
                    thumbnail = doc.get("thumbnail", [])
                    if thumbnail and len(thumbnail) > 0:
                        try:
                            thumb_img = thumbnail[0]
                            if isinstance(thumb_img, str) and (thumb_img.startswith('data:') or thumb_img.startswith('http')):
                                st.image(thumb_img, caption="Thumbnail", width=200)
                            else:
                                st.warning("Thumbnail data invalid - skipping display.")
                        except Exception as img_err:
                            st.warning(f"Error displaying thumbnail: {str(img_err)}")
                    else:
                        st.info("No thumbnail available.")
                with col_gallery:
                    st.subheader("Gallery")
                    gallery = doc.get("gallery", [])
                    if gallery:
                        cols = st.columns(3)
                        for i, img_data_url in enumerate(gallery[:3]):
                            try:
                                if isinstance(img_data_url, str) and (img_data_url.startswith('data:') or img_data_url.startswith('http')):
                                    with cols[i]:
                                        st.image(img_data_url, caption=f"Gallery Image {i+1}", width=200)
                                else:
                                    st.warning(f"Gallery image {i+1} data invalid - skipping.")
                            except Exception as img_err:
                                st.warning(f"Error displaying gallery image {i+1}: {str(img_err)}")

                st.subheader("Tags")
                tags = doc.get("tags", [])
                if tags:
                    for tag in tags:
                        st.write(tag)
                else:
                    st.write("No tags available.")

                with st.expander("Full Retrieved JSON"):
                    formatted = format_document(doc)
                    st.code(formatted, language="json")
            else:
                st.warning("No matching content found. Try generating it!")
        else:
            st.error("MongoDB not connected - can't search.")

# Footer
st.markdown("---")
st.markdown("Developed by Suraj Gawas")