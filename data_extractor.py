import pandas as pd
import mysql.connector
import os

# --- CONFIGURATION ---
INPUT_CSV_PATH = (
    "./India Agriculture Crop Production.csv"  # Ensure this matches your file name
)
OUTPUT_CSV_PATH = "filtered_db2_update.csv"

# Try to import config.py (for Reehan). If missing, use local config (for Kunal).
try:
    from config import DB2_CONFIG

    print("✅ Loaded configuration from config.py")
except ImportError:
    print("⚠️ config.py not found. Using local configuration.")
    DB2_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "YOUR_LOCAL_ROOT_PASSWORD",  # <--- KUNAL UPDATE THIS
        "database": "groez_db2",
    }


def connect_db():
    """Connects to DB2 to fetch existing constraints."""
    try:
        return mysql.connector.connect(**DB2_CONFIG)
    except mysql.connector.Error as e:
        print(f"❌ Error connecting to DB2: {e}")
        return None


def get_db_constraints(cursor):
    """
    Fetches the set of (State, District) tuples and Crop names
    that ALREADY EXIST in your database.
    """
    constraints = {
        "locations": set(),  # Stores (state_lower, district_lower)
        "crops": set(),  # Stores crop_lower
    }

    print("🔍 Scanning DB2 for existing states, districts, and crops...")

    # 1. Fetch existing Districts
    cursor.execute("SELECT state, district FROM districts")
    for state, district in cursor.fetchall():
        # Store as lower case for case-insensitive matching
        constraints["locations"].add((state.strip().lower(), district.strip().lower()))

    # 2. Fetch existing Crops
    cursor.execute("SELECT crop_name FROM crops")
    for (crop,) in cursor.fetchall():
        constraints["crops"].add(crop.strip().lower())

    print(f"   -> Found {len(constraints['locations'])} valid districts.")
    print(f"   -> Found {len(constraints['crops'])} valid crops.")

    return constraints


def extract_and_filter():
    # 1. Check Input
    if not os.path.exists(INPUT_CSV_PATH):
        print(f"❌ Error: Input file '{INPUT_CSV_PATH}' not found.")
        print("   Please verify the file name matches the script configuration.")
        return

    # 2. Get Constraints from DB
    conn = connect_db()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        db_constraints = get_db_constraints(cursor)
    finally:
        conn.close()

    if not db_constraints["locations"]:
        print("⚠️ Warning: DB2 seems empty. No districts found to filter by.")
        return

    # 3. Process CSV
    print(f"📂 Reading '{INPUT_CSV_PATH}'...")
    try:
        # Read CSV - handling potential encoding issues
        try:
            df = pd.read_csv(INPUT_CSV_PATH, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(INPUT_CSV_PATH, encoding="latin1")

        # Clean column names (strip whitespace)
        df.columns = df.columns.str.strip()

        # Check if 'Yield' exists, if not, we might need to calculate it
        if "Yield" not in df.columns:
            print(
                "ℹ️ 'Yield' column not found in CSV. Will calculate as Production/Area."
            )
            df["Yield"] = df["Production"] / df["Area"]

        # Fill NaNs for text columns to avoid matching errors
        df["State"] = df["State"].fillna("")
        df["District"] = df["District"].fillna("")
        df["Crop"] = df["Crop"].fillna("")

        print(f"   -> Raw CSV contains {len(df)} rows.")

        # 4. Apply Filters (Case-Insensitive)

        # Helper columns for matching
        df["match_state"] = df["State"].str.strip().str.lower()
        df["match_district"] = df["District"].str.strip().str.lower()
        df["match_crop"] = df["Crop"].str.strip().str.lower()

        # Filter A: Keep only rows where (State, District) matches DB2
        # We use a lambda to check against the set of tuples
        location_mask = df.apply(
            lambda x: (x["match_state"], x["match_district"])
            in db_constraints["locations"],
            axis=1,
        )

        # Filter B: Keep only rows where Crop matches DB2
        crop_mask = df["match_crop"].isin(db_constraints["crops"])

        # Combine Filters
        df_filtered = df[location_mask & crop_mask].copy()

        # 5. Clean up and Save
        # Select only the columns needed for DB2 Schema
        # DB2 Schema needs: Year, Yield, Area, Production (mapped from CSV)
        final_columns = [
            "State",
            "District",
            "Crop",
            "Year",
            "Area",
            "Production",
            "Yield",
        ]

        # Ensure specific columns exist before selecting
        available_cols = [c for c in final_columns if c in df_filtered.columns]
        df_final = df_filtered[available_cols]

        # Drop rows with NaN in critical values
        df_final = df_final.dropna(subset=["Area", "Production"])

        print(f"   -> Extracted {len(df_final)} relevant rows.")

        if not df_final.empty:
            df_final.to_csv(OUTPUT_CSV_PATH, index=False)
            print(f"🎉 Success! Filtered data saved to '{OUTPUT_CSV_PATH}'")
            print("   You can now use this file to update your database.")
        else:
            print(
                "⚠️ No matching data found. The CSV did not contain any rows matching your DB2 districts/crops."
            )

    except Exception as e:
        print(f"❌ Error processing CSV: {e}")


if __name__ == "__main__":
    extract_and_filter()
