import pandas as pd
from sqlalchemy import create_engine, text
import os

DB_USER = 'groez_user'
DB_PASSWORD = 'groez09'
DB_HOST = 'localhost'
DB_PORT = 3306

def get_data_path(filename):
    """Constructs the full path to a data file."""
    base_dir = 'data'
    dataset_dir = 'output_datasets'
    return os.path.join(base_dir, dataset_dir, filename)

def load_db1(engine):
    """Loads Weather and Soil data into DB1."""
    print("\n--- Loading Data for DB1 (Weather & Soil) ---")
    
    try:
        weather_df = pd.read_csv(get_data_path('weather_data.csv'))
        soil_df = pd.read_csv(get_data_path('soil_data.csv'))
        print("CSV files for DB1 read successfully.")
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure the CSV files are in the 'data/output_datasets' directory.")
        return False

    # Create a unified districts table from the soil data
    districts = soil_df[['district', 'state']].drop_duplicates().reset_index(drop=True)
    districts['district_id'] = districts.index + 1
    
    # Merge with source dataframes to get the new district_id foreign key
    soil_merged = pd.merge(soil_df, districts, on=['district', 'state'])
    weather_merged = pd.merge(weather_df, districts, on=['district', 'state'])

    # Prepare final dataframes for database tables
    districts_final = districts[['district_id', 'district', 'state']]
    soil_final = soil_merged[['district_id', 'soil_type', 'ph_level', 'nitrogen_ppm', 'phosphorus_ppm', 'potassium_ppm']]
    weather_final = weather_merged[['district_id', 'year', 'month', 'avg_temp_celsius', 'avg_rainfall_mm']]
    
    with engine.connect() as connection:
        # Load tables. 'replace' will drop the table if it exists and create a new one.
        districts_final.to_sql('Districts', con=connection, if_exists='replace', index=False)
        print("Table 'Districts' loaded.")
        soil_final.to_sql('Soil_Conditions', con=connection, if_exists='replace', index=False)
        print("Table 'Soil_Conditions' loaded.")
        weather_final.to_sql('Weather_Data', con=connection, if_exists='replace', index=False)
        print("Table 'Weather_Data' loaded.")
        
        # Add primary and foreign keys for relational integrity
        connection.execute(text('ALTER TABLE Districts ADD PRIMARY KEY (district_id);'))
        connection.execute(text('ALTER TABLE Soil_Conditions ADD FOREIGN KEY (district_id) REFERENCES Districts(district_id);'))
        connection.execute(text('ALTER TABLE Weather_Data ADD FOREIGN KEY (district_id) REFERENCES Districts(district_id);'))
        print("Primary and Foreign keys set for DB1.")

    print("\nDB1 loading complete.")
    return True

def load_db2(engine):
    """Loads Crops and Yields data into DB2."""
    print("\n--- Loading Data for DB2 (Crops & Yields) ---")

    try:
        yield_df = pd.read_csv(get_data_path('crop_yields.csv'))
        # DB2 also needs district info to map yields correctly
        soil_df = pd.read_csv(get_data_path('soil_data.csv')) 
        print("CSV files for DB2 read successfully.")
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure the CSV files are in the 'data/output_datasets' directory.")
        return False

    # Create reference tables for districts and crops
    districts = soil_df[['district', 'state']].drop_duplicates().reset_index(drop=True)
    districts['district_id'] = districts.index + 1
    
    crops = yield_df[['crop_name']].drop_duplicates().reset_index(drop=True)
    crops['crop_id'] = crops.index + 1
    
    # Merge to get foreign keys
    yield_merged = pd.merge(yield_df, districts, on=['district', 'state'])
    yield_merged = pd.merge(yield_merged, crops, on='crop_name')

    # Prepare final dataframes for database tables
    districts_final = districts[['district_id', 'district', 'state']]
    crops_final = crops[['crop_id', 'crop_name']]
    yields_final = yield_merged[['district_id', 'crop_id', 'year', 'yield_ton_per_hectare', 'area_hectares', 'production_tonnes']]

    with engine.connect() as connection:
        districts_final.to_sql('Districts', con=connection, if_exists='replace', index=False)
        print("Table 'Districts' loaded.")
        crops_final.to_sql('Crops', con=connection, if_exists='replace', index=False)
        print("Table 'Crops' loaded.")
        yields_final.to_sql('Historical_Yields', con=connection, if_exists='replace', index=False)
        print("Table 'Historical_Yields' loaded.")
        
        # Add primary and foreign keys
        connection.execute(text('ALTER TABLE Districts ADD PRIMARY KEY (district_id);'))
        connection.execute(text('ALTER TABLE Crops ADD PRIMARY KEY (crop_id);'))
        connection.execute(text('ALTER TABLE Historical_Yields ADD FOREIGN KEY (district_id) REFERENCES Districts(district_id);'))
        connection.execute(text('ALTER TABLE Historical_Yields ADD FOREIGN KEY (crop_id) REFERENCES Crops(crop_id);'))
        print("Primary and Foreign keys set for DB2.")

    print("\nDB2 loading complete.")
    return True

if __name__ == '__main__':
    choice = input("Which database to load? (1 for DB1: Weather/Soil, 2 for DB2: Crops/Yields): ")

    db_name = ''
    if choice == '1':
        db_name = 'groez_db1'
    elif choice == '2':
        db_name = 'groez_db2'
    else:
        print("Invalid choice. Exiting.")
        exit()

    try:
        # Create the connection 'engine' using SQLAlchemy
        connection_string = f'mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db_name}'
        engine = create_engine(connection_string)
        
        # Test connection before proceeding
        with engine.connect() as connection:
            print(f"Successfully connected to MySQL database '{db_name}'!")

        if choice == '1':
            success = load_db1(engine)
        else:
            success = load_db2(engine)
            
        if success:
            print(f"\nPhase 1 is complete! The '{db_name}' database is set up and loaded.")
            print("Please commit this 'db_loader.py' script to GitHub so your partner has it.")

    except Exception as e:
        print("\n--- An Error Occurred ---")
        print("Could not connect to or load the database. Please check the following:")
        print("1. Is your MySQL server application running?")
        print(f"2. Are the DB_USER ('{DB_USER}') and DB_PASSWORD ('{DB_PASSWORD}') settings at the top of the script correct?")
        print(f"3. Did you create the database ('{db_name}') and grant privileges correctly?")
        print(f"Error details: {e}")