from PIL import Image
import hashlib
import warnings
# Suppress the "support has ended" warning from google-generativeai
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import google.generativeai as genai

import os
import json
from datetime import date
from dotenv import load_dotenv

# Load env variables (API Key)
load_dotenv()

class OCREngine:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("WARNING: GEMINI_API_KEY not found in .env file.")
        else:
            genai.configure(api_key=api_key)
            # Use 'gemini-2.0-flash' as confirmed by list_models
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            print("Gemini AI Engine Initialized.")


                


    DEFAULT_PROMPT = """
    Analyze this pilot logbook page. Extract the flight rows into a JSON array. 
    For each row, identify ONLY these fields:
    - date (YYYY-MM-DD)
    - departure_place (Airport Code)
    - departure_time (HH:MM)
    - arrival_place (Airport Code)
    - arrival_time (HH:MM)
    - aircraft_model (Type)
    - aircraft_registration (Registration/Ident)
    - single_pilot_se (Duration HH:MM)
    - single_pilot_me (Duration HH:MM)
    - multi_pilot (Duration HH:MM)
    - total_flight_time (Duration HH:MM)
    - name_pic (Name of Pilot in Command)
    - landings_day (Integer)
    - landings_night (Integer)
    - time_night (Duration HH:MM - Operational Condition)
    - time_ifr (Duration HH:MM - Operational Condition)
    - time_pic (Duration HH:MM - Pilot Function)
    - time_copi (Duration HH:MM - Pilot Function)
    - time_dual (Duration HH:MM - Pilot Function)
    - time_instructor (Duration HH:MM - Pilot Function)
    - remarks (Text)
    
    Important:
    - Combine separate Hour and Minute columns into "HH:MM". 
    - If a duration is just minutes (e.g. 40), format as "0:40".
    - If a duration is "1" hour and "06" minutes, format as "1:06".
    
    Return ONLY raw JSON. No markdown. Array key 'entries'.
    """

    
    def get_available_models(self):
        """
        Fetches available Gemini models that support content generation.
        """
        try:
            models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                    models.append(m.name)
            return sorted(models, reverse=True) # Newest first usually
        except Exception as e:
            print(f"Error fetching models: {e}")
            return ["models/gemini-2.0-flash"] # Fallback

    def process_image(self, image_path: str, prompt_override: str = None, model_name: str = "models/gemini-2.0-flash"):
        """
        Sends the image to Google Gemini to extract logbook entries.
        Uses advanced caching: Cache Key = MD5(ImageFileHash + PromptHash + ModelName).
        """
        print(f"Processing: {image_path} with model: {model_name}")
        
        # Determine Prompt
        prompt = prompt_override if prompt_override else self.DEFAULT_PROMPT
        
        # Calculate Cache Key
        image_id = os.path.basename(image_path)
        # Include model name in hash so different models have different caches
        cache_key_content = f"{prompt}{model_name}"
        prompt_hash = hashlib.md5(cache_key_content.encode('utf-8')).hexdigest()
        
        cache_filename = f"{image_id}.{prompt_hash}.json"
        cache_path = os.path.join(os.path.dirname(image_path), cache_filename)
        
        print(f"Cache Path: {cache_path}")
        
        raw_data = None
        
        # 1. Check Cache
        if os.path.exists(cache_path):
            print("Using Cached Response (No API Cost)")
            try:
                with open(cache_path, "r") as f:
                    content = f.read().strip()
                    try:
                        raw_data = json.loads(content)
                    except json.JSONDecodeError:
                        print("Cache was not valid JSON, ignoring.")
                        raw_data = None
            except Exception as e:
                print(f"Cache Corrupt, falling back to API: {e}")

        # 2. Call API if no cache
        if not raw_data:
            try:
                print(f"Calling Gemini API ({model_name})...")
                img = Image.open(image_path)
                
                # Use specified model
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([prompt, img])
                
                # Clean response
                text_response = response.text.strip()
                if text_response.startswith("```"):
                    text_response = text_response.strip("`")
                    if text_response.startswith("json"):
                        text_response = text_response[4:]
                
                # 3. Parse & Inject Prompt for Cache
                try:
                    raw_data = json.loads(text_response)
                    
                    # Ensure it's a dict to add metadata
                    cache_data = raw_data
                    if isinstance(cache_data, list):
                        cache_data = {"entries": raw_data}
                    elif not isinstance(cache_data, dict):
                        cache_data = {"entries": [], "raw_content": str(raw_data)}
                        
                    # Inject metadata
                    cache_data['_debug_prompt'] = prompt
                    cache_data['_meta'] = {"model": model_name}
                    
                    # Save Cache
                    with open(cache_path, "w") as f:
                        json.dump(cache_data, f, indent=2)
                        
                    raw_data = cache_data
                    
                except json.JSONDecodeError:
                    print(f"Warning: Gemini returned invalid JSON: {text_response}")
                    with open(cache_path + ".err", "w") as f:
                        f.write(text_response)
                    return [], {"error": "Invalid JSON from AI"}
                except Exception as e:
                    print(f"Warning: Could not save cache: {e}")

            except Exception as e:
                error_msg = str(e)
                print(f"Gemini Error: {error_msg}")
                return [], {"error": error_msg}

        # 4. Process Data
        return self.parse_logbook_data(raw_data), raw_data

    def parse_logbook_data(self, raw_data):
        """
        Pure function to parse raw JSON into structured LogEntry dictionaries.
        Designed for strict content validation and unit testing.
        """
        entries = []
        if isinstance(raw_data, dict):
            entries = raw_data.get("entries", [])
        elif isinstance(raw_data, list):
            entries = raw_data
        
        def sanitize_date(d):
            try:
                date.fromisoformat(str(d))
                return str(d)
            except ValueError:
                return str(date.today())

        def parse_duration(value):
            """Converts 'HH:MM' string or decimal hours to integer total minutes."""
            if not value: return 0
            
            s = str(value).strip()
            
            # Robustly handle separators (space, dot, etc -> colon)
            # "1 06" -> "1:06"
            s = s.replace(" ", ":")
            
            # Handle HH:MM format
            if ":" in s:
                try:
                    parts = s.split(":")
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    return (hours * 60) + minutes
                except (ValueError, IndexError):
                    pass
            
            # Handle standard float/int
            try:
                return int(round(float(s) * 60))
            except ValueError:
                return 0

        processed_entries = []
        for e in entries:
            processed_entries.append({
                "date": sanitize_date(e.get("date", "")),
                "departure_place": e.get("departure_place"),
                "departure_time": e.get("departure_time"),
                "arrival_place": e.get("arrival_place"),
                "arrival_time": e.get("arrival_time"),
                
                "aircraft_model": e.get("aircraft_model"),
                "aircraft_registration": e.get("aircraft_registration") or e.get("aircraft_ident"), # Fallback for old cache
                
                "single_pilot_se": parse_duration(e.get("single_pilot_se")),
                "single_pilot_me": parse_duration(e.get("single_pilot_me")),
                "multi_pilot": parse_duration(e.get("multi_pilot")),
                
                "total_flight_time": parse_duration(e.get("total_flight_time") or e.get("duration")), # Fallback
                "name_pic": e.get("name_pic"),
                
                "landings_day": int(e.get("landings_day") or 0),
                "landings_night": int(e.get("landings_night") or 0),
                
                "time_night": parse_duration(e.get("time_night") or e.get("night")),
                "time_ifr": parse_duration(e.get("time_ifr") or e.get("if_actual")),
                
                "time_pic": parse_duration(e.get("time_pic") or e.get("pic")),
                "time_copi": parse_duration(e.get("time_copi") or e.get("sic")),
                "time_dual": parse_duration(e.get("time_dual") or e.get("dual_received")),
                "time_instructor": parse_duration(e.get("time_instructor")),
                
                "remarks": e.get("remarks", ""),
            })
            
        return processed_entries

ocr_engine = OCREngine()
