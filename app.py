import streamlit as st
from supabase import create_client, Client
import random
import time
import io
import uuid
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
from datetime import datetime
import os

# --- Initial Setup ---
st.set_page_config(
    page_title="Number Assignment System",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- CSS Styling ---
st.markdown("""
<style>
    .main-header {text-align: center; margin-bottom: 30px;}
    .number-display {font-size: 72px; text-align: center; margin: 30px 0;}
    .success-msg {background-color: #d4edda; color: #155724; padding: 10px; border-radius: 5px;}
    .error-msg {background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# --- Functions ---

def get_supabase_client() -> Client:
    """Establishes a connection to Supabase using environment variables."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        st.error("Supabase credentials not configured in the environment.")
        return None
    try:
        client = create_client(supabase_url, supabase_key)
        client.table("_dummy").select("*").limit(1).execute()
        return client
    except Exception as e:
        st.error(f"Error connecting to Supabase: {str(e)}")
        return None

def check_table_exists(supabase, table_name):
    """Checks if a specific table exists in Supabase."""
    try:
        supabase.table(table_name).select("*").limit(1).execute()
        return True
    except Exception:
        return False

def create_meeting_table(supabase, table_name, meeting_name, max_number=999):
    """Creates a new table for a meeting in Supabase and registers metadata."""
    try:
        # Step 1: Register meeting metadata
        response_metadata = supabase.table("meetings_metadata").insert({
            "table_name": table_name,
            "meeting_name": meeting_name,
            "created_at": datetime.now().isoformat(),
            "max_number": max_number
        }).execute()

        # Step 2: Create the table dynamically via RPC
        create_table_query = f"""
        CREATE TABLE public.{table_name} (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            number INTEGER NOT NULL,
            assigned BOOLEAN DEFAULT FALSE,
            assigned_at TIMESTAMPTZ,
            user_id TEXT
        );
        """
        supabase.rpc("execute_sql", {"query": create_table_query}).execute()

        # Wait briefly for propagation
        time.sleep(1)
        if not check_table_exists(supabase, table_name):
            raise Exception(f"Table {table_name} was not created successfully in Supabase.")

        # Step 3: Insert numbers into the new table in batches
        batch_size = 100
        for i in range(0, max_number, batch_size):
            end = min(i + batch_size, max_number)
            data = [{"number": j, "assigned": False, "assigned_at": None, "user_id": None} 
                    for j in range(i+1, end+1)]
            supabase.table(table_name).insert(data).execute()
        
        return True
    except Exception as e:
        st.error(f"Error creating meeting table: {str(e)}")
        try:
            supabase.table("meetings_metadata").delete().eq("table_name", table_name).execute()
            supabase.rpc("execute_sql", {"query": f"DROP TABLE IF EXISTS public.{table_name}"}).execute()
        except Exception as rollback_e:
            st.error(f"Rollback error: {str(rollback_e)}")
        return False

def get_available_meetings(supabase):
    """Retrieves the list of available meetings from the metadata table."""
    try:
        response = supabase.table("meetings_metadata").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"Error retrieving meetings: {str(e)}")
        return []

def generate_number_image(number):
    """Generates an image with only the assigned number."""
    width, height = 600, 300
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Gradient background
    for y in range(height):
        r = int(220 - y/3)
        g = int(240 - y/3)
        b = 255
        for x in range(width):
            draw.point((x, y), fill=(r, g, b))
    
    # Load font
    try:
        font = ImageFont.truetype("Arial.ttf", 200)
    except IOError:
        font = ImageFont.load_default()
    
    # Center the number
    number_text = str(number)
    bbox = draw.textbbox((0, 0), number_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_position = ((width - text_width) // 2, (height - text_height) // 2)
    draw.text(text_position, number_text, font=font, fill=(0, 0, 100))
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return img_buffer

def generate_participant_link(table_name):
    """Generates a link for participants to access the meeting."""
    base_url = "https://app-number.streamlit.app"
    return f"{base_url}/?table={table_name}&mode=participant"

# --- Initialize Session Variables ---
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

# --- Check Mode (Master or Participant) ---
query_params = st.query_params
mode = query_params.get("mode", "master")
table_name_from_url = query_params.get("table", None)

if mode == "participant" and table_name_from_url:
    # --- Participant Mode ---
    st.markdown("<h1 class='main-header'>Get Your Number</h1>", unsafe_allow_html=True)
    supabase = get_supabase_client()
    if not supabase:
        st.stop()
    
    if not check_table_exists(supabase, table_name_from_url):
        st.error("Meeting not found or invalid.")
        st.stop()
    
    try:
        meeting_info = supabase.table("meetings_metadata").select("*").eq("table_name", table_name_from_url).execute()
        meeting_name = meeting_info.data[0]["meeting_name"] if meeting_info.data else "Meeting"
        st.subheader(f"Meeting: {meeting_name}")
    except Exception:
        st.subheader("Get a number for the meeting")

    user_id = st.session_state["user_id"]
    try:
        existing = supabase.table(table_name_from_url).select("*").eq("user_id", user_id).execute()
        if existing.data:
            st.session_state["assigned_number"] = existing.data[0]["number"]
            st.markdown(f"""
            <div class='success-msg'>
                <p>You already have an assigned number:</p>
                <div class='number-display'>{st.session_state['assigned_number']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            if "assigned_number" not in st.session_state:
                with st.spinner("Assigning a number..."):
                    response = supabase.table(table_name_from_url).select("*").eq("assigned", False).execute()
                    if response.data:
                        available_numbers = [row["number"] for row in response.data]
                        assigned_number = random.choice(available_numbers)
                        supabase.table(table_name_from_url).update({
                            "assigned": True,
                            "assigned_at": datetime.now().isoformat(),
                            "user_id": user_id
                        }).eq("number", assigned_number).execute()
                        st.session_state["assigned_number"] = assigned_number
                    else:
                        st.error("All numbers have been assigned!")
                        st.stop()
            st.markdown(f"""
            <div class='success-msg'>
                <p>Your assigned number is:</p>
                <div class='number-display'>{st.session_state['assigned_number']}</div>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error assigning number: {str(e)}")
        st.stop()
    
    if st.button("Save as Image"):
        with st.spinner("Generating image..."):
            img_buffer = generate_number_image(st.session_state["assigned_number"])
            st.image(img_buffer)
            st.download_button(
                "Download Image",
                img_buffer,
                file_name=f"my_number_{st.session_state['assigned_number']}.png",
                mime="image/png"
            )

else:
    # --- Master Mode ---
    valid_pages = ["Manage Meetings", "Share Meeting Link", "View Statistics"]
    if "page" not in st.session_state or st.session_state["page"] not in valid_pages:
        st.session_state["page"] = "Manage Meetings"

    st.sidebar.title("Menu (Master)")
    page = st.sidebar.radio("Choose an option", valid_pages, index=valid_pages.index(st.session_state["page"]))

    # --- Page 1: Manage Meetings ---
    if page == "Manage Meetings":
        st.session_state["page"] = "Manage Meetings"
        st.markdown("<h1 class='main-header'>Manage Meetings</h1>", unsafe_allow_html=True)
        supabase = get_supabase_client()
        if not supabase:
            st.stop()
        
        with st.form("create_meeting_form"):
            st.subheader("Create New Meeting")
            meeting_name = st.text_input("Meeting Name")
            max_number = st.number_input("Maximum Number", min_value=10, max_value=10000, value=999)
            submit_button = st.form_submit_button("Create Meeting")
            
            if submit_button:
                if meeting_name:
                    table_name = f"meeting_{int(time.time())}_{meeting_name.lower().replace(' ', '_')}"
                    if check_table_exists(supabase, table_name):
                        st.error("A meeting with this name already exists. Try another name.")
                    else:
                        with st.spinner("Creating meeting..."):
                            success = create_meeting_table(supabase, table_name, meeting_name, max_number)
                            if success:
                                participant_link = generate_participant_link(table_name)
                                st.success(f"Meeting '{meeting_name}' created successfully!")
                                st.markdown(f"**Participant Link:** [{participant_link}]({participant_link})")
                                st.session_state["selected_table"] = table_name
                                st.session_state["page"] = "Share Meeting Link"
                                st.rerun()
                            else:
                                st.error("Failed to create the meeting.")
                else:
                    st.warning("Please enter a meeting name.")
        
        st.subheader("Existing Meetings")
        meetings = get_available_meetings(supabase)
        if meetings:
            meeting_data = []
            for meeting in meetings:
                if "table_name" in meeting and "meeting_name" in meeting:
                    table_name = meeting["table_name"]
                    if check_table_exists(supabase, table_name):
                        try:
                            count_response = supabase.table(table_name).select("*", count="exact").eq("assigned", True).execute()
                            assigned_count = count_response.count if hasattr(count_response, 'count') else 0
                            participant_link = generate_participant_link(table_name)
                            meeting_data.append({
                                "Name": meeting.get("meeting_name", "No name"),
                                "Table": table_name,
                                "Link": participant_link,
                                "Created At": meeting.get("created_at", "")[:16].replace("T", " "),
                                "Assigned Numbers": assigned_count,
                                "Total Numbers": meeting.get("max_number", 0)
                            })
                        except Exception as e:
                            st.warning(f"Error processing meeting {table_name}: {str(e)}")
                    else:
                        st.warning(f"Table {table_name} does not exist in the database.")
            if meeting_data:
                df = pd.DataFrame(meeting_data)
                st.dataframe(df)
            else:
                st.info("No valid meetings found.")
        else:
            st.info("No meetings available or error accessing Supabase.")

    # --- Page 2: Share Meeting Link (Master) ---
    elif page == "Share Meeting Link":
        st.session_state["page"] = "Share Meeting Link"
        st.markdown("<h1 class='main-header'>Share Meeting Link</h1>", unsafe_allow_html=True)
        
        supabase = get_supabase_client()
        if not supabase:
            st.stop()
        
        meetings = get_available_meetings(supabase)
        if not meetings:
            st.info("No meetings available. Create a meeting first.")
            st.stop()
        
        options = {f"{m['meeting_name']} ({m['table_name']})": m["table_name"] 
                   for m in meetings if "table_name" in m and "meeting_name" in m}
        selected = st.selectbox("Select a meeting to share:", list(options.keys()))
        
        if selected:
            selected_table = options[selected]
            participant_link = generate_participant_link(selected_table)
            st.markdown(f"**Participant Link:** [{participant_link}]({participant_link})")
            if st.button("Copy Link"):
                st.write("Link copied to clipboard!")
                st.code(participant_link)  # Display the link for manual copying if needed
                # Note: Streamlit doesn't natively copy to clipboard; users can copy manually from the text

    # --- Page 3: View Statistics ---
    elif page == "View Statistics":
        st.session_state["page"] = "View Statistics"
        st.markdown("<h1 class='main-header'>Meeting Statistics</h1>", unsafe_allow_html=True)
        supabase = get_supabase_client()
        if not supabase:
            st.stop()
        
        meetings = get_available_meetings(supabase)
        if not meetings:
            st.info("No meetings available for analysis.")
            st.stop()
        
        options = {f"{m['meeting_name']} ({m['table_name']})": m["table_name"] 
                   for m in meetings if "table_name" in m and "meeting_name" in m}
        selected = st.selectbox("Select a meeting:", list(options.keys()))
        
        if selected:
            selected_table = options[selected]
            try:
                total_response = supabase.table(selected_table).select("*", count="exact").execute()
                total_numbers = total_response.count if hasattr(total_response, 'count') else 0
                assigned_response = supabase.table(selected_table).select("*", count="exact").eq("assigned", True).execute()
                assigned_numbers = assigned_response.count if hasattr(assigned_response, 'count') else 0
                percentage = (assigned_numbers / total_numbers) * 100 if total_numbers > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Numbers", total_numbers)
                with col2:
                    st.metric("Assigned Numbers", assigned_numbers)
                with col3:
                    st.metric("Assigned Percentage", f"{percentage:.1f}%")
                
                try:
                    time_data_response = supabase.table(selected_table).select("*").eq("assigned", True).order("assigned_at").execute()
                    if time_data_response.data:
                        time_data = []
                        for item in time_data_response.data:
                            if item.get("assigned_at"):
                                time_data.append({
                                    "time": item.get("assigned_at")[:16].replace("T", " "),
                                    "count": 1
                                })
                        if time_data:
                            df = pd.DataFrame(time_data)
                            df["time"] = pd.to_datetime(df["time"])
                            df["hour"] = df["time"].dt.floor("H")
                            hourly_counts = df.groupby("hour").count().reset_index()
                            hourly_counts["hour_str"] = hourly_counts["hour"].dt.strftime("%m/%d %H:00")
                            st.subheader("Number Assignments per Hour")
                            st.bar_chart(data=hourly_counts, x="hour_str", y="count")
                except Exception:
                    st.info("Temporal data not available for this meeting.")
                
                if st.button("Export Data"):
                    try:
                        all_data_response = supabase.table(selected_table).select("*").execute()
                        if all_data_response.data:
                            df = pd.DataFrame(all_data_response.data)
                            csv = df.to_csv(index=False)
                            st.download_button(
                                "Download CSV",
                                csv,
                                file_name=f"{selected_table}_export.csv",
                                mime="text/csv"
                            )
                    except Exception as e:
                        st.error(f"Error exporting data: {str(e)}")
            except Exception as e:
                st.error(f"Error retrieving statistics: {str(e)}")

if __name__ == "__main__":
    pass  # O Streamlit executa o script diretamente
