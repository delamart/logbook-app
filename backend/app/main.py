from fastapi import FastAPI, UploadFile, File, Request, Form
from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, create_engine, Session, select
from datetime import date
from typing import List, Optional
from .models import LogEntry
import shutil
import os
import hashlib
# Import OCR engine instance directly
from .ocr import ocr_engine
import airportsdata
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

airports_db = airportsdata.load('ICAO')

# Database Setup
# Database Setup
sqlite_file_name = "backend/data/logbook.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
# Use DATABASE_URL from environment for Supabase/Postgres
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("WARNING: DATABASE_URL not found, falling back to SQLite")
    engine = create_engine(sqlite_url, echo=True)
else:
    # Ensure compat with psycopg2
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(database_url, echo=True)

# Supabase Client Setup
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
else:
    print("WARNING: SUPABASE_URL or SUPABASE_KEY not set.")

def upload_to_supabase(file_content: bytes, filename: str, content_type: str) -> str:
    """Uploads file to Supabase Storage and returns Public URL"""
    if not supabase:
        raise Exception("Supabase not configured")
    
    bucket_name = "uploads"
    try:
        # Upload
        supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=file_content,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        # Get Public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(filename)
        return public_url
    except Exception as e:
        print(f"Supabase Upload Error: {e}")
        # Fallback? Or Re-raise?
        raise e

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

# Mount Static & Template
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="frontend/templates")

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"request": request, "page": "dashboard"})

@app.get("/dashboard")
def read_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"request": request, "page": "dashboard"})

@app.get("/logbook")
def read_logbook(request: Request):
    return templates.TemplateResponse(request, "logbook.html", {"request": request, "page": "logbook"})

@app.get("/map")
def read_map(request: Request):
    return templates.TemplateResponse(request, "map.html", {"request": request, "page": "map"})

@app.get("/tools")
def read_tools(request: Request):
    return templates.TemplateResponse(request, "tools.html", {"request": request, "page": "tools"})

@app.get("/prompt")
def get_prompt():
    """Returns the current default prompt used by the AI."""
    return {"prompt": ocr_engine.DEFAULT_PROMPT}

@app.get("/api/models")
def get_models():
    """Returns a list of available Gemini models."""
    return {"models": ocr_engine.get_available_models()}

@app.post("/upload/")
async def upload_image(
    file: UploadFile = File(...), 
    custom_prompt: Optional[str] = Form(None),
    model: Optional[str] = Form("models/gemini-2.0-flash")
):
    # Read file content to calculate hash
    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()
    
    # Get extension
    ext = os.path.splitext(file.filename)[1]
    if not ext:
        ext = ".png" # Default fallback
        
    hashed_filename = f"{file_hash}{ext}"
    
    # 1. Upload to Supabase Storage (if configured)
    public_url = None
    if supabase:
        try:
            public_url = upload_to_supabase(content, hashed_filename, file.content_type or "image/png")
            print(f"Uploaded to Supabase: {public_url}")
        except Exception as e:
            print(f"Failed to upload to Supabase: {e}")
    
    # 2. Save locally (cached) for OCR processing
    # Even if using Supabase, we might need a local copy for the Gemini API if passing path
    # OR we can update ocr.py to accept bytes? 
    # For now, keep local cache behavior for OCR engine compatibility and speed
    file_location = f"uploads/{hashed_filename}"
    
    # Save only if not exists (deduplication)
    if not os.path.exists(file_location):
        with open(file_location, "wb+") as file_object:
            file_object.write(content)
    
    # Process image with optional prompt override and selected model
    extracted_data, raw_json = ocr_engine.process_image(
        file_location, 
        prompt_override=custom_prompt,
        model_name=model
    )
    
    # Inject Public URL into extracted data
    if public_url:
        for entry in extracted_data:
            entry['page_image_path'] = public_url

    # Return extracted data WITHOUT saving to DB yet
    return {
        "info": f"file processed (hash: {file_hash})", 
        "extracted_entries": extracted_data,
        "raw_json": raw_json,
        "model_used": model,
        "public_url": public_url
    }

from typing import List

@app.post("/save_entries/")
async def save_entries(entries: List[LogEntry]):
    with Session(engine) as session:
        saved_entries = []
        for item in entries:
            # item is already a LogEntry model because of Pydantic
            # ensure created_at is set if missing
            if not item.created_at:
                item.created_at = str(date.today())
            session.add(item)
            saved_entries.append(item)
        session.commit()
    return {"message": f"Saved {len(saved_entries)} entries"}

@app.get("/entries/", response_model=List[LogEntry])
async def get_entries():
    with Session(engine) as session:
        # Sort by date descending
        entries = session.exec(select(LogEntry).order_by(LogEntry.date.desc())).all()
        return entries

@app.delete("/entries/all")
async def delete_all_entries():
    with Session(engine) as session:
        from sqlmodel import delete
        statement = delete(LogEntry)
        result = session.exec(statement)
        session.commit()
        return {"message": f"Deleted {result.rowcount} entries"}

@app.delete("/entries/{entry_id}")
async def delete_entry(entry_id: int):
    with Session(engine) as session:
        entry = session.get(LogEntry, entry_id)
        if not entry:
            return {"error": "Entry not found"}
        session.delete(entry)
        session.commit()
    return {"message": "Entry deleted"}

@app.put("/entries/{entry_id}")
async def update_entry(entry_id: int, entry_data: LogEntry):
    with Session(engine) as session:
        db_entry = session.get(LogEntry, entry_id)
        if not db_entry:
            return {"error": "Entry not found"}
        
        # Update fields
        entry_data_dict = entry_data.model_dump(exclude_unset=True)
        for key, value in entry_data_dict.items():
            if key != "id": # Don't update ID
                setattr(db_entry, key, value)
        
        session.add(db_entry)
        session.commit()
        session.refresh(db_entry)
        return db_entry

@app.post("/entries/create")
async def create_entry(entry: LogEntry):
    with Session(engine) as session:
        if not entry.created_at:
            entry.created_at = str(date.today())
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

@app.get("/map_data")
async def get_map_data():
    with Session(engine) as session:
         entries = session.exec(select(LogEntry)).all()
         used_icaos = set()
         for e in entries:
             # Sanitize: uppercase, strip
             if e.departure_place: used_icaos.add(e.departure_place.upper().strip())
             if e.arrival_place: used_icaos.add(e.arrival_place.upper().strip())
         
         data = {}
         import re
         
         def parse_coordinate(coord_str):
             """
             Parses coordinate strings like "56.46°N/12.70°E" or "56.46N/12.70E"
             Returns [lat, lon] or None
             """
             try:
                 # Remove degree symbols and whitespace
                 clean = coord_str.replace('°', '').strip()
                 # Regex for "LatN/LonE" format
                 # Matches: number, N/S, separator, number, E/W
                 match = re.search(r'([0-9.]+)([NS])[\/\s,]*([0-9.]+)([EW])', clean, re.IGNORECASE)
                 if match:
                     lat, lat_dir, lon, lon_dir = match.groups()
                     lat = float(lat)
                     lon = float(lon)
                     if lat_dir.upper() == 'S': lat = -lat
                     if lon_dir.upper() == 'W': lon = -lon
                     return [lat, lon]
                 
                 # Basic "Lat, Lon" check
                 if ',' in clean:
                     parts = clean.split(',')
                     if len(parts) == 2:
                         return [float(parts[0]), float(parts[1])]
             except:
                 pass
             return None

         for code in used_icaos:
             if code in airports_db:
                 apt = airports_db[code]
                 data[code] = {'lat': apt['lat'], 'lon': apt['lon'], 'name': apt.get('name', 'Unknown')}
             else:
                 # Try parsing as coordinate
                 coords = parse_coordinate(code)
                 if coords:
                     data[code] = {'lat': coords[0], 'lon': coords[1], 'name': 'GPS Waypoint'}
                     
         return data

import csv
import io

@app.post("/import/foreflight")
async def import_foreflight_csv(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # DEBUG: Save file to inspect
        debug_path = "uploads/foreflight_debug.csv"
        with open(debug_path, "wb") as f:
            f.write(content)
        
        # Decode assuming utf-8, handling BOM
        text = content.decode("utf-8-sig")
        lines = text.splitlines()

        # 1. First Pass: Find and Parse Aircraft Table (Type Mapping)
        aircraft_map = {} # Registration -> {type: str, class: str}
        ac_start_index = -1
        
        for i, line in enumerate(lines):
            if line.strip().startswith("Aircraft Table"):
                ac_start_index = i + 1
                break
        
        if ac_start_index != -1:
            # Read until empty line or next table
            ac_lines = []
            for line in lines[ac_start_index:]:
                if not line.strip() or "Table" in line: break
                ac_lines.append(line)
            
            if ac_lines:
                ac_reader = csv.DictReader(io.StringIO("\n".join(ac_lines)))
                for row in ac_reader:
                    reg = row.get('AircraftID')
                    if reg:
                        # Capture Class (e.g. airplane_single_engine_land) from FAA or EASA column
                        ac_class = row.get('aircraftClass (FAA)') or row.get('aircraftClass (EASA)') or ''
                        aircraft_map[reg] = {
                            'code': row.get('TypeCode') or '',
                            'class': ac_class.lower()
                        }
                print(f"DEBUG: Aircraft Map: {aircraft_map}")

        # 2. Find section start for Flights Table
        start_index = 0
        found_table = False
        
        # Scan for "Flights Table", then scan for the actual header
        flights_table_found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("Flights Table"):
                flights_table_found = True
                continue # Header should be after this
            
            if flights_table_found:
                # Look for the header line
                if "Date" in stripped and "AircraftID" in stripped:
                    start_index = i
                    found_table = True
                    print(f"DEBUG: Found Header at line {i}: {line}")
                    break
        
        # Fallback for simple CSVs (no "Flights Table" marker)
        if not found_table:
             for i, line in enumerate(lines[:20]):
                 if "Date" in line and "AircraftID" in line:
                     start_index = i
                     found_table = True
                     break
                 
        if not found_table:
             return {"message": "Invalid ForeFlight CSV: Could not find 'Flights Table' or valid headers.", "error": True}

        # Parse CSV from the identified start
        # limit to just this table? We should stop if we hit another empty line or table?
        # DictReader doesn't stop automatically. We need to handle this in loop.
        
        csv_text = "\n".join(lines[start_index:])
        # Use register_dialect or just standard? ForeFlight is standard CSV usually.
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        print(f"DEBUG: CSV Headers: {csv_reader.fieldnames}")

        entries = []
        for row in csv_reader:
            # Check for end of table (empty Date or new table header)
            raw_date = row.get('Date')
            if not raw_date:
                # Could be empty line or end of table
                continue
                
            raw_date = raw_date.strip()
            if not raw_date or "Table" in raw_date:
                # Stop parsing if we hit "Expenses Table" or similar
                print(f"DEBUG: Stopping at line: {row}")
                break

            def parse_duration(val):
                """Converts 'HH:MM' string or decimal hours to integer total minutes."""
                if not val: return 0
                if isinstance(val, str):
                    val = val.strip()
                if not val: return 0
                try:
                    if ':' in val:
                        parts = val.split(':')
                        hours = int(parts[0])
                        minutes = int(parts[1])
                        return (hours * 60) + minutes
                    else:
                        # Convert float hours to int minutes
                        return int(round(float(val) * 60))
                except:
                    return 0

            # Helper to safely get string
            def get_str(key):
                val = row.get(key)
                return val.strip() if val else ''

            # ForeFlight Header Mappings
            def get_int(key):
                try: return int(row.get(key) or 0)
                except: return 0
                
            day_ldgs = get_int('DayLandingsFullStop') or get_int('LandingsDay')
            night_ldgs = get_int('NightLandingsFullStop') or get_int('LandingsNight')
            all_ldgs = get_int('AllLandings')
            
            if day_ldgs == 0 and night_ldgs == 0 and all_ldgs > 0:
                day_ldgs = all_ldgs

            # TimeOut/In are usually HH:MM
            dep_time = get_str('TimeOut')
            arr_time = get_str('TimeIn')
            
            reg = get_str('AircraftID')
            ac_info = aircraft_map.get(reg, {'code': '', 'class': ''})
            model_code = ac_info['code']
            ac_class = ac_info['class']
            
            total_time = parse_duration(row.get('TotalTime'))
            
            # Determine correct column for time (SE, ME, Multi-Pilot)
            # Default to SE if unknown
            se_time = 0
            me_time = 0
            mp_time = 0
            
            # Check for multi-pilot first (Logbook rules may vary, simplified logic here)
            # If SIC time exists, assume Multi Pilot? 
            # Or use "aircraftClass" from mapping.
            
            sic_time = parse_duration(row.get('SIC'))
            pic_time = parse_duration(row.get('PIC'))
            
            if sic_time > 0:
                 mp_time = total_time # Simplified assumption
            elif "multi" in ac_class:
                 me_time = total_time
            else:
                 se_time = total_time

            entry_obj = LogEntry(
                date=raw_date,
                departure_place=get_str('From'),
                departure_time=dep_time,
                arrival_place=get_str('To'),
                arrival_time=arr_time,
                aircraft_model=model_code,
                aircraft_registration=reg,
                
                # Times
                total_flight_time=total_time,
                single_pilot_se=se_time,
                single_pilot_me=me_time,
                multi_pilot=mp_time,
                
                name_pic=get_str('PIC'), 
                
                landings_day=day_ldgs,
                landings_night=night_ldgs,
                
                time_night=parse_duration(row.get('Night')),
                time_ifr=parse_duration(row.get('ActualInstrument')), # + SimulatedInstrument?
                
                time_pic=pic_time,
                time_copi=sic_time,
                time_dual=parse_duration(row.get('DualReceived')),
                time_instructor=parse_duration(row.get('DualGiven')),
                
                remarks=get_str('Comments') or get_str('PilotComments') or get_str('Remarks')
            )
            entries.append(entry_obj)

        # Return entries for preview (Frontend will use showValidation)
        # Convert LogEntry objects to dicts
        entries_data = [entry.model_dump() for entry in entries]
        
        result = {
            "extract_count": len(entries),
            "extracted_entries": entries_data,
            "raw_json": {"csv_headers": csv_reader.fieldnames, "sample_row": entries_data[0] if entries_data else {}}
        }
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"message": f"Server Error: {str(e)}", "error": True}
