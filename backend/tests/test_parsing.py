from backend.app.ocr import OCREngine
import json
import unittest

class TestOCRParsing(unittest.TestCase):
    def setUp(self):
        self.engine = OCREngine()
        # Mock data representing the new EASA/JAR schema
        self.mock_json = {
            "entries": [
                {
                    "date": "2023-10-15",
                    "departure_place": "LSGG",
                    "departure_time": "10:00",
                    "arrival_place": "LSZH",
                    "arrival_time": "11:30",
                    "aircraft_model": "C172",
                    "aircraft_registration": "HB-KLZ",
                    "single_pilot_se": "1:30",
                    "single_pilot_me": None,
                    "multi_pilot": None,
                    "total_flight_time": "1:30",
                    "name_pic": "Self",
                    "landings_day": 1,
                    "landings_night": 0,
                    "time_night": None,
                    "time_ifr": "0:20", # simulated hood
                    "time_pic": "1:30",
                    "time_copi": None,
                    "time_dual": None,
                    "time_instructor": None,
                    "remarks": "Nice flight"
                },
                {
                    "date": "invalid-date",
                    "departure_place": "LSZH",
                    "total_flight_time": 1.5, # Float input test
                    "name_pic": "Instructor"
                }
            ]
        }

    def test_parse_easa_fields(self):
        """Verify that EASA specific fields are parsed correctly"""
        parsed = self.engine.parse_logbook_data(self.mock_json)
        self.assertEqual(len(parsed), 2)
        
        entry1 = parsed[0]
        
        # Check Strings
        self.assertEqual(entry1['departure_place'], "LSGG")
        self.assertEqual(entry1['aircraft_registration'], "HB-KLZ")
        
        # Check Durations (1:30 -> 90)
        self.assertEqual(entry1['single_pilot_se'], 90)
        self.assertEqual(entry1['total_flight_time'], 90)
        self.assertEqual(entry1['time_ifr'], 20) # 20 mins is 20
        
        # Check Nulls became 0
        self.assertEqual(entry1['single_pilot_me'], 0)
        self.assertEqual(entry1['multi_pilot'], 0)
        
    def test_date_fallback(self):
        """Test date sanitization"""
        parsed = self.engine.parse_logbook_data(self.mock_json)
        entry2 = parsed[1]
        # Should fallback to today's date if invalid
        self.assertRegex(entry2['date'], r"^\d{4}-\d{2}-\d{2}$")

    def test_float_duration_input(self):
        """Test that float inputs for duration work directly"""
        parsed = self.engine.parse_logbook_data(self.mock_json)
        entry2 = parsed[1]
        self.assertEqual(entry2['total_flight_time'], 90)

    def test_space_separated_durations(self):
        """Test parsing of 'HH MM' format (e.g., '1 06')"""
        # Create a mock entry with space-separated duration
        bad_json = {
            "entries": [{
                "date": "2023-10-15",
                "total_flight_time": "1 06",  # Should be 1h 6m = 1.1
                "single_pilot_se": "1 30",    # Should be 1.5
                "time_pic": "0 45"            # Should be 0.75
            }]
        }
        parsed = self.engine.parse_logbook_data(bad_json)
        entry = parsed[0]
        
        self.assertEqual(entry['total_flight_time'], 66)
        self.assertEqual(entry['single_pilot_se'], 90)
        self.assertEqual(entry['time_pic'], 45)
