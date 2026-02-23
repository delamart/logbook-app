
CREATE TABLE logentry (
	id SERIAL NOT NULL, 
	user_id VARCHAR, 
	date DATE NOT NULL, 
	departure_place VARCHAR, 
	departure_time VARCHAR, 
	arrival_place VARCHAR, 
	arrival_time VARCHAR, 
	aircraft_model VARCHAR, 
	aircraft_registration VARCHAR, 
	single_pilot_se INTEGER NOT NULL, 
	single_pilot_me INTEGER NOT NULL, 
	multi_pilot INTEGER NOT NULL, 
	total_flight_time INTEGER NOT NULL, 
	name_pic VARCHAR, 
	landings_day INTEGER NOT NULL, 
	landings_night INTEGER NOT NULL, 
	time_night INTEGER NOT NULL, 
	time_ifr INTEGER NOT NULL, 
	time_pic INTEGER NOT NULL, 
	time_copi INTEGER NOT NULL, 
	time_dual INTEGER NOT NULL, 
	time_instructor INTEGER NOT NULL, 
	remarks VARCHAR, 
	page_image_path VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
)


