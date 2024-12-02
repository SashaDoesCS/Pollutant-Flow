import os
import geopandas as gpd
import json
import logging
import pandas as pd
from shapely.geometry import shape, mapping

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Simplification function
def simplify_json_files(cache_dir, output_dir, simplification_tolerance=0.01):
    """
    Simplifies GeoJSON-like files and combines them into a single file.

    Args:
        cache_dir (str): Directory containing JSON files to simplify.
        output_dir (str): Directory where the simplified output will be saved.
        simplification_tolerance (float): Tolerance for geometry simplification.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # List all JSON files in cache directory
    files = [f for f in os.listdir(cache_dir) if f.endswith(".json")]
    if not files:
        logging.error("No JSON files found in the specified cache directory.")
        return

    combined_data = []
    for file in files:
        file_path = os.path.join(cache_dir, file)
        try:
            # Load the JSON file
            logging.info(f"Processing file: {file}")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check for valid GeoJSON structure
            if "features" not in data or not isinstance(data["features"], list):
                logging.warning(f"File {file} does not contain a valid 'features' key.")
                continue

            # Convert to GeoDataFrame
            features = data["features"]
            geometries = [shape(feature["geometry"]) for feature in features if "geometry" in feature]
            properties = [feature.get("properties", {}) for feature in features]
            gdf = gpd.GeoDataFrame(properties, geometry=geometries, crs="EPSG:4326")

            # Simplify geometries
            logging.info(f"Simplifying geometries with tolerance {simplification_tolerance}")
            gdf["geometry"] = gdf["geometry"].simplify(tolerance=simplification_tolerance, preserve_topology=True)

            # Keep relevant columns (adjust as needed)
            cols_to_keep = ['name', 'category', 'state', 'geometry']
            gdf = gdf[[col for col in cols_to_keep if col in gdf.columns]]

            # Append to combined list
            combined_data.append(gdf)

        except json.JSONDecodeError as e:
            logging.warning(f"File {file} is not a valid JSON: {e}")
        except Exception as e:
            logging.warning(f"Failed to process file {file}: {e}")
            continue

    if combined_data:
        # Combine all data into a single GeoDataFrame
        combined_gdf = gpd.GeoDataFrame(pd.concat(combined_data, ignore_index=True), crs="EPSG:4326")

        # Save to output directory
        output_file = os.path.join(output_dir, "simplified_water_features.geojson")
        combined_gdf.to_file(output_file, driver="GeoJSON")
        logging.info(f"Simplified features saved to {output_file}")
    else:
        logging.warning("No data to combine after processing.")

# Main execution
if __name__ == "__main__":
    # Specify directories
    cache_dir = "cache"  # Replace with the actual cache directory path
    output_dir = "water_features_data/states/California"  # Replace with the desired output directory

    # Simplify the files
    simplify_json_files(cache_dir, output_dir, simplification_tolerance=0.01)
