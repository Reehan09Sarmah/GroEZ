import pandas as pd
import numpy as np
from faker import Faker
import random
import os

# Initialize Faker for Indian context
fake = Faker('en_IN')

# --- Configuration ---
YEARS = range(2015, 2025)
STATES = ["Punjab", "Maharashtra"]
CROPS = ["Wheat", "Rice", "Sugarcane"]

# Define districts for each state
DISTRICTS = {
    "Punjab": ["Amritsar", "Ludhiana", "Jalandhar", "Patiala", "Bathinda"],
    "Maharashtra": ["Pune", "Nashik", "Nagpur", "Aurangabad", "Satara"]
}

# Base yield (tons per hectare) and weather stats for each crop
CROP_PROFILES = {
    "Wheat": {"base_yield": 3.5, "temp_opt": 21, "rain_opt": 75},
    "Rice": {"base_yield": 2.5, "temp_opt": 27, "rain_opt": 150},
    "Sugarcane": {"base_yield": 70, "temp_opt": 28, "rain_opt": 120}
}

# Soil profiles for districts
SOIL_PROFILES = {
    "Amritsar": {"soil_type": "Alluvial", "base_ph": 7.2, "base_n": 140},
    "Ludhiana": {"soil_type": "Loamy", "base_ph": 7.5, "base_n": 155},
    "Jalandhar": {"soil_type": "Alluvial", "base_ph": 7.3, "base_n": 145},
    "Patiala": {"soil_type": "Clay Loam", "base_ph": 7.8, "base_n": 130},
    "Bathinda": {"soil_type": "Sandy Loam", "base_ph": 8.0, "base_n": 120},
    "Pune": {"soil_type": "Clay", "base_ph": 6.8, "base_n": 160},
    "Nashik": {"soil_type": "Red Loam", "base_ph": 6.5, "base_n": 150},
    "Nagpur": {"soil_type": "Black Clay", "base_ph": 7.0, "base_n": 170},
    "Aurangabad": {"soil_type": "Clay Loam", "base_ph": 7.5, "base_n": 140},
    "Satara": {"soil_type": "Lateritic", "base_ph": 6.2, "base_n": 135}
}

def generate_weather_data():
    """Generates synthetic monthly weather data for all districts."""
    data = []
    for year in YEARS:
        for state, districts in DISTRICTS.items():
            for district in districts:
                for month in range(1, 13):
                    # Simulate seasonal temperature variations
                    if month in [1, 2, 12]: temp = random.uniform(15, 22)
                    elif month in [3, 4, 10, 11]: temp = random.uniform(25, 32)
                    else: temp = random.uniform(28, 35) # Monsoon/Summer
                    
                    # Simulate monsoon rainfall
                    if month in [6, 7, 8, 9]: rainfall = random.uniform(100, 350)
                    else: rainfall = random.uniform(10, 50)
                    
                    data.append({
                        "year": year,
                        "month": month,
                        "state": state,
                        "district": district,
                        "avg_temp_celsius": round(temp, 2),
                        "avg_rainfall_mm": round(rainfall, 2)
                    })
    df = pd.DataFrame(data)
    print("Weather data generated.")
    return df

def generate_soil_data():
    """Generates synthetic soil condition data for all districts."""
    data = []
    for state, districts in DISTRICTS.items():
        for district in districts:
            profile = SOIL_PROFILES[district]
            ph = profile["base_ph"] + random.uniform(-0.3, 0.3)
            nitrogen = profile["base_n"] + random.randint(-20, 20)
            phosphorus = nitrogen * random.uniform(0.1, 0.3)
            potassium = nitrogen * random.uniform(0.5, 0.8)
            data.append({
                "district": district,
                "state": state,
                "soil_type": profile["soil_type"],
                "ph_level": round(ph, 2),
                "nitrogen_ppm": int(nitrogen),
                "phosphorus_ppm": int(phosphorus),
                "potassium_ppm": int(potassium)
            })
    df = pd.DataFrame(data)
    print("Soil data generated.")
    return df

def generate_crop_yield_data(weather_df):
    """Generates synthetic crop yield data based on weather conditions."""
    data = []
    annual_weather = weather_df.groupby(['year', 'state', 'district']).agg(
        avg_temp=('avg_temp_celsius', 'mean'),
        total_rain=('avg_rainfall_mm', 'sum')
    ).reset_index()

    for _, row in annual_weather.iterrows():
        for crop in CROPS:
            # Skip crops not typically grown in a state
            if crop in ["Sugarcane"] and row["state"] == "Punjab":
                 if random.random() > 0.85: # Small chance
                    pass
                 else:
                    continue
            if crop in ["Wheat"] and row["state"] == "Maharashtra":
                 if random.random() > 0.9: # Small chance
                    pass
                 else:
                    continue

            profile = CROP_PROFILES[crop]
            base_yield = profile['base_yield']

            # Factor in weather impact
            temp_factor = 1 - (abs(row['avg_temp'] - profile['temp_opt']) / profile['temp_opt']) * 0.5
            rain_factor = 1 - (abs(row['total_rain'] - (profile['rain_opt'] * 12)) / (profile['rain_opt'] * 12)) * 0.5
            
            # Combine factors with some randomness
            final_yield = base_yield * temp_factor * rain_factor * random.uniform(0.85, 1.15)

            # Area cultivated
            area_hectares = random.randint(10000, 50000)
            
            data.append({
                "year": row['year'],
                "state": row['state'],
                "district": row['district'],
                "crop_name": crop,
                "yield_ton_per_hectare": round(final_yield, 2),
                "area_hectares": area_hectares,
                "production_tonnes": round(final_yield * area_hectares, 2)
            })
    df = pd.DataFrame(data)
    print("Crop yield data generated.")
    return df

def main():
    """Main function to generate and save all datasets."""
    # Create an 'output' directory if it doesn't exist
    output_dir = 'output_datasets'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    weather_df = generate_weather_data()
    soil_df = generate_soil_data()
    crop_yield_df = generate_crop_yield_data(weather_df)
    
    # Save to CSV
    weather_df.to_csv(os.path.join(output_dir, "weather_data.csv"), index=False)
    soil_df.to_csv(os.path.join(output_dir, "soil_data.csv"), index=False)
    crop_yield_df.to_csv(os.path.join(output_dir, "crop_yields.csv"), index=False)
    
    print(f"\nSuccessfully generated 3 datasets in the '{output_dir}' folder:")
    print(f"1. weather_data.csv ({len(weather_df)} rows)")
    print(f"2. soil_data.csv ({len(soil_df)} rows)")
    print(f"3. crop_yields.csv ({len(crop_yield_df)} rows)")
    print("\nIMPORTANT: Please move these 3 files into your 'data' directory.")

if __name__ == "__main__":
    main()

