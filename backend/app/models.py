from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import date as dt_date
from datetime import datetime
import sqlalchemy as sa
from pydantic import field_validator

class LogEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    
    # 1. Basic Info
    date: dt_date = Field(index=True)
    
    @field_validator("date", mode="before")
    def parse_date(cls, v):
        if isinstance(v, str):
            # Parse YYYY-MM-DD
            return datetime.strptime(v, "%Y-%m-%d").date()
        return v
        
    departure_place: Optional[str] = Field(default=None, index=True)
    departure_time: Optional[str] = None
    arrival_place: Optional[str] = Field(default=None, index=True)
    arrival_time: Optional[str] = None
    
    # 2. Aircraft
    aircraft_model: Optional[str] = None
    aircraft_registration: Optional[str] = Field(default=None, index=True) # previously aircraft_ident
    
    # 3. Single/Multi Pilot Times (Durations)
    single_pilot_se: int = Field(default=0)
    single_pilot_me: int = Field(default=0)
    multi_pilot: int = Field(default=0)
    
    # 4. Totals
    total_flight_time: int = Field(default=0)
    name_pic: Optional[str] = None
    
    # 5. Landings
    landings_day: int = Field(default=0)
    landings_night: int = Field(default=0)
    
    # 6. Operational Condition
    time_night: int = Field(default=0)
    time_ifr: int = Field(default=0)
    
    # 7. Pilot Function
    time_pic: int = Field(default=0)
    time_copi: int = Field(default=0)
    time_dual: int = Field(default=0)
    time_instructor: int = Field(default=0)
    
    # 8. Remarks
    remarks: Optional[str] = None
    
    # Metadata
    page_image_path: Optional[str] = None
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"server_default": sa.text("CURRENT_TIMESTAMP")}
    )
