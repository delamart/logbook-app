from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import date

class LogEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 1. Basic Info
    date: str
    departure_place: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_place: Optional[str] = None
    arrival_time: Optional[str] = None
    
    # 2. Aircraft
    aircraft_model: Optional[str] = None
    aircraft_registration: Optional[str] = None # previously aircraft_ident
    
    # 3. Single/Multi Pilot Times (Durations)
    single_pilot_se: float = Field(default=0.0)
    single_pilot_me: float = Field(default=0.0)
    multi_pilot: float = Field(default=0.0)
    
    # 4. Totals
    total_flight_time: float = Field(default=0.0)
    name_pic: Optional[str] = None
    
    # 5. Landings
    landings_day: int = Field(default=0)
    landings_night: int = Field(default=0)
    
    # 6. Operational Condition
    time_night: float = Field(default=0.0)
    time_ifr: float = Field(default=0.0)
    
    # 7. Pilot Function
    time_pic: float = Field(default=0.0)
    time_copi: float = Field(default=0.0)
    time_dual: float = Field(default=0.0)
    time_instructor: float = Field(default=0.0)
    
    # 8. Remarks
    remarks: Optional[str] = None
    
    # Metadata
    page_image_path: Optional[str] = None
    created_at: str
