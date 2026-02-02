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

airports_db = airportsdata.load('ICAO')

# Database Setup
sqlite_file_name = "backend/data/logbook.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=True)

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
    return templates.TemplateResponse(request, "index.html")

@app.get("/prompt")
def get_prompt():
    """Returns the current default prompt used by the AI."""
    return {"prompt": ocr_engine.DEFAULT_PROMPT}

@app.post("/upload/")
async def upload_image(
    file: UploadFile = File(...), 
    custom_prompt: Optional[str] = Form(None)
):
    # Read file content to calculate hash
    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()
    
    # Get extension
    ext = os.path.splitext(file.filename)[1]
    if not ext:
        ext = ".png" # Default fallback
        
    hashed_filename = f"{file_hash}{ext}"
    file_location = f"uploads/{hashed_filename}"
    
    # Save only if not exists (deduplication)
    if not os.path.exists(file_location):
        with open(file_location, "wb+") as file_object:
            file_object.write(content)
    
    # Process image with optional prompt override
    extracted_data, raw_json = ocr_engine.process_image(file_location, prompt_override=custom_prompt)
    
    # Return extracted data WITHOUT saving to DB yet
    return {
        "info": f"file processed (hash: {file_hash})", 
        "extracted_entries": extracted_data,
        "raw_json": raw_json
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
        for i, line in enumerate(lines):
            # ForeFlight exports usually have "Flights Table" before the header
            if line.strip().startswith("Flights Table"):
                start_index = i + 1 # Header is the next line
                found_table = True
                break
        
        # Fallback for simple CSVs or different formats
        if not found_table:
             # Try to find the header row by looking for key columns
             for i, line in enumerate(lines[:20]): # Check first 20 lines
                 if "Date" in line and "AircraftID" in line:
                     start_index = i
                     found_table = True
                     break
                 
             if not found_table:
                 return {"message": "Invalid ForeFlight CSV: Could not find 'Flights Table' or valid headers.", "error": True}

        # Parse CSV from the identified start
        csv_text = "\n".join(lines[start_index:])
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        print(f"DEBUG: CSV Headers: {csv_reader.fieldnames}")

        entries = []
        for row in csv_reader:
            if not row.get('Date') or not row.get('Date').strip():
                continue

            def parse_duration(val):
                """Converts 'HH:MM' string to float hours."""
                if not val: return 0.0
                val = val.strip()
                if not val: return 0.0
                try:
                    if ':' in val:
                        parts = val.split(':')
                        hours = float(parts[0])
                        minutes = float(parts[1])
                        return hours + (minutes / 60.0)
                    else:
                        return float(val)
                except:
                    return 0.0

            # ForeFlight Header Mappings
            # Note: "LandingsAll" is often "DayLandingsFullStop" + "NightLandingsFullStop"
            day_ldgs = int(parse_duration(row.get('DayLandingsFullStop') or row.get('LandingsDay') or '0'))
            night_ldgs = int(parse_duration(row.get('NightLandingsFullStop') or row.get('LandingsNight') or '0'))
            all_ldgs = int(parse_duration(row.get('AllLandings') or '0'))
            
            if day_ldgs == 0 and night_ldgs == 0 and all_ldgs > 0:
                day_ldgs = all_ldgs

            # TimeOut/In are usually HH:MM
            dep_time = row.get('TimeOut', '').strip()
            arr_time = row.get('TimeIn', '').strip()
            
            reg = row.get('AircraftID')
            ac_info = aircraft_map.get(reg, {'code': '', 'class': ''})
            model_code = ac_info['code']
            ac_class = ac_info['class']
            
            total_time = parse_duration(row.get('TotalTime'))
            
            # Determine correct column for time (SE, ME, Multi-Pilot)
            # Default to SE if unknown
            se_time = 0.0
            me_time = 0.0
            mp_time = 0.0
            
            # Check for multi-pilot first (Logbook rules may vary, simplified logic here)
            # If SIC time exists, assume Multi Pilot Operation? Or checking boolean columns?
            # ForeFlight doesn't strictly enforce "Multi Pilot" column usage often.
            
            if 'multi' in ac_class or 'me' in ac_class:
                 me_time = total_time
            else:
                 se_time = total_time

            entry = LogEntry(
                date=row.get('Date'),
                aircraft_registration=reg,
                aircraft_model=model_code, # Set mapped type code
                departure_place=row.get('From'),
                arrival_place=row.get('To'),
                departure_time=dep_time,
                arrival_time=arr_time,
                total_flight_time=total_time,
                single_pilot_se=se_time,
                single_pilot_me=me_time,
                multi_pilot=mp_time,
                name_pic="SELF", 
                # Derive Day time
                time_day=parse_duration(row.get('Day', '0')) if parse_duration(row.get('Night', '0')) == 0 else (parse_duration(row.get('TotalTime', '0')) - parse_duration(row.get('Night', '0')) if parse_duration(row.get('TotalTime')) else 0),
                time_night=parse_duration(row.get('Night')),
                time_ifr=parse_duration(row.get('ActualInstrument')),
                time_pic=parse_duration(row.get('PIC')),
                time_copi=parse_duration(row.get('SIC')),
                time_dual=parse_duration(row.get('DualReceived')),
                time_instructor=parse_duration(row.get('Instructor')),
                landings_day=day_ldgs,
                landings_night=night_ldgs,
                remarks=row.get('PilotComments') or row.get('Comments') or row.get('Remarks', ''),
                created_at=str(date.today())
            )
            entries.append(entry)
        
        with Session(engine) as session:
            for e in entries:
                session.add(e)
            session.commit()
        
        return {"message": f"Successfully imported {len(entries)} entries from ForeFlight CSV."}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"message": f"Server Error: {str(e)}", "error": True}
