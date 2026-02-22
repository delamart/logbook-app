
import unittest
import json
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool
from backend.app.main import app
import backend.app.main as main_module
from backend.app.models import LogEntry

class TestAPI(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database for testing, with StaticPool
        self.test_engine = create_engine(
            "sqlite://", 
            connect_args={"check_same_thread": False}, 
            poolclass=StaticPool,
            echo=False
        )
        SQLModel.metadata.create_all(self.test_engine)
        
        # Patch the engine in the main module
        self.original_engine = main_module.engine
        main_module.engine = self.test_engine
        
        self.client = TestClient(app)

    def tearDown(self):
        # Restore the original engine
        main_module.engine = self.original_engine
        SQLModel.metadata.drop_all(self.test_engine)

    def test_read_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Logbook Scanner", response.text)

    def test_get_prompt(self):
        response = self.client.get("/prompt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("prompt", response.json())

    def test_create_and_get_entry(self):
        # 1. Create Entry
        new_entry = {
            "date": "2023-01-01",
            "departure_place": "TEST",
            "arrival_place": "DEST",
            "total_flight_time": 90,
            "remarks": "Test Flight"
        }
        response = self.client.post("/entries/create", json=new_entry)
        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertEqual(created["departure_place"], "TEST")
        self.assertIsNotNone(created["id"])
        entry_id = created["id"]

        # 2. Get All Entries
        response = self.client.get("/entries/")
        self.assertEqual(response.status_code, 200)
        entries = response.json()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], entry_id)

    def test_save_bulk_entries(self):
        entries = [
            {"date": "2023-01-01", "total_flight_time": 60, "remarks": "Bulk 1"},
            {"date": "2023-01-02", "total_flight_time": 120, "remarks": "Bulk 2"}
        ]
        response = self.client.post("/save_entries/", json=entries)
        self.assertEqual(response.status_code, 200)
        
        # Verify
        response = self.client.get("/entries/")
        self.assertEqual(len(response.json()), 2)

    def test_update_entry(self):
        # Create initial
        create_resp = self.client.post("/entries/create", json={"date": "2023-01-01", "remarks": "Original"})
        entry_id = create_resp.json()["id"]

        # Update
        update_data = {"remarks": "Updated", "total_flight_time": 300}
        response = self.client.put(f"/entries/{entry_id}", json=update_data)
        self.assertEqual(response.status_code, 200)
        updated = response.json()
        self.assertEqual(updated["remarks"], "Updated")
        self.assertEqual(updated["total_flight_time"], 300)

        # Verify persistence
        get_resp = self.client.get("/entries/")
        self.assertEqual(get_resp.json()[0]["remarks"], "Updated")

    def test_delete_entry(self):
        create_resp = self.client.post("/entries/create", json={"date": "2023-01-01"})
        entry_id = create_resp.json()["id"]
        
        # Delete
        response = self.client.delete(f"/entries/{entry_id}")
        self.assertEqual(response.status_code, 200)
        
        # Verify gone
        response = self.client.get("/entries/")
        self.assertEqual(len(response.json()), 0)

    def test_delete_all_entries(self):
        # Create multiple
        self.client.post("/entries/create", json={"date": "2023-01-01"})
        self.client.post("/entries/create", json={"date": "2023-01-02"})
        
        # Verify count is 2
        self.assertEqual(len(self.client.get("/entries/").json()), 2)
        
        # Delete All
        response = self.client.delete("/entries/all")
        self.assertEqual(response.status_code, 200)
        
        # Verify empty
        self.assertEqual(len(self.client.get("/entries/").json()), 0)

    def test_upload_image_mock(self):
        # Mocking the file upload is a bit complex due to the OCR engine interaction.
        # But we can test the endpoint structure.
        # Ideally we would mock `ocr_engine.process_image` to avoid calling Gemini.
        
        from unittest.mock import patch
        
        with patch("backend.app.main.ocr_engine.process_image") as mock_process:
            mock_process.return_value = ([{"date": "2023-01-01"}], {"raw": "json"})
            
            # Create a dummy file
            file_content = b"fake image content"
            files = {"file": ("test.png", file_content, "image/png")}
            
            response = self.client.post("/upload/", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("extracted_entries", data)
            self.assertEqual(data["extracted_entries"][0]["date"], "2023-01-01")

    def test_map_data(self):
        # 1. Create entries with known airports (ZRH = LSZH, GVA = LSGG)
        # Using uppercase and whitespace to test sanitization
        self.client.post("/entries/create", json={"date": "2023-01-01", "departure_place": "LSZH", "arrival_place": "lsgg "})
        
        # 2. Call map_data
        response = self.client.get("/map_data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 3. Verify LSZH (Zurich) and LSGG (Geneva) are present
        self.assertIn("LSZH", data)
        self.assertIn("LSGG", data)
        
        # 4. Verify coordinates matches new structure (dict)
        # LSZH: ~47.46, 8.55
        self.assertAlmostEqual(data["LSZH"]["lat"], 47.46, places=1)
        self.assertAlmostEqual(data["LSZH"]["lon"], 8.55, places=1)
        self.assertIn("name", data["LSZH"])
        
        # 5. Verify GPS Coordinate parsing ("GPS Waypoint")
        self.client.post("/entries/create", json={"date": "2023-01-03", "departure_place": "46.2N/8.8E"})
        response = self.client.get("/map_data")
        data = response.json()
        self.assertIn("46.2N/8.8E", data)
        self.assertEqual(data["46.2N/8.8E"]["name"], "GPS Waypoint")
        self.assertAlmostEqual(data["46.2N/8.8E"]["lat"], 46.2, places=1)

    def test_import_foreflight(self):
        # Create a mock ForeFlight CSV
        csv_content = (
            "Aircraft Table\n"
            "AircraftID,TypeCode,aircraftClass (FAA)\n"
            "HB-KPG,P2006T,airplane_multi_engine_land\n"
            "\n"
            "Flights Table\n"
            "Date,AircraftID,From,To,TimeOut,TimeIn,TotalTime,DayLandingsFullStop,NightLandingsFullStop,Comments\n"
            "2023-05-01,HB-KPG,LSGC,LSZH,10:00,11:30,1.5,1,0,Test Flight\n"
            "2023-05-02,HB-KPG,LSZH,LSGC,14:00,15:00,1:00,0,1,Return\n" # Test HH:MM duration
        )
        
        files = {"file": ("logbook.csv", csv_content, "text/csv")}
        response = self.client.post("/import/foreflight", files=files)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        print(f"DEBUG: Test received data: {data}")
        self.assertEqual(data["extract_count"], 2)
        
        # Save Entries
        entries_to_save = data["extracted_entries"]
        response = self.client.post("/save_entries/", json=entries_to_save)
        self.assertEqual(response.status_code, 200)

        # Verify Database
        response = self.client.get("/entries/")
        entries = response.json()
        self.assertEqual(len(entries), 2)
        
        # Check Entry 1 (Decimal duration)
        entry1 = next(e for e in entries if e["date"] == "2023-05-01")
        self.assertEqual(entry1["total_flight_time"], 90)
        self.assertEqual(entry1["departure_place"], "LSGC")
        self.assertEqual(entry1["aircraft_model"], "P2006T") # Mapped from Aircraft Table
        self.assertEqual(entry1["single_pilot_me"], 90) # ME Class -> ME Time
        
        # Check Entry 2 (HH:MM duration)
        entry2 = next(e for e in entries if e["date"] == "2023-05-02")
        self.assertEqual(entry2["total_flight_time"], 60)
        self.assertEqual(entry2["landings_night"], 1)

if __name__ == '__main__':
    unittest.main()
