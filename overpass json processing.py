import os
import json
import logging
import geopandas as gpd
from shapely.geometry import Point, LineString

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def process_overpass_json(file_path, output_dir, simplification_tolerance=0.1):
    """
    Processes Overpass JSON data and simplifies geometries.

    Args:
        file_path (str): Path to the Overpass JSON file.
        output_dir (str): Directory to save the simplified output.
        simplification_tolerance (float): Tolerance for geometry simplification.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        # Load the JSON data
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check for the 'elements' key
        if "elements" not in data:
            logging.error(f"'elements' key not found in {file_path}")
            return

        # Separate nodes and ways
        nodes = {el["id"]: Point(el["lon"], el["lat"]) for el in data["elements"] if el["type"] == "node"}
        ways = [el for el in data["elements"] if el["type"] == "way"]

        # Convert ways to LineString geometries
        features = []
        for way in ways:
            try:
                geometry = LineString([nodes[node_id] for node_id in way["nodes"] if node_id in nodes])
                properties = way.get("tags", {})
                features.append({"geometry": geometry, "properties": properties})
            except Exception as e:
                logging.warning(f"Failed to process way {way['id']}: {e}")

        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

        # Simplify geometries
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=simplification_tolerance, preserve_topology=True)

        # Save to GeoJSON
        output_file = os.path.join(output_dir, "simplified_water_features.geojson")
        gdf.to_file(output_file, driver="GeoJSON")
        logging.info(f"Simplified features saved to {output_file}")

    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")


# Main execution
if __name__ == "__main__":
    # Specify input file and output directory
    input_file = "cache/1bdbe0695ef81d377b6ead3f508c7f27a25bee4c.json"  # Replace with the uploaded file path
    output_dir = "water_features_data/states/California"  # Replace with the desired output directory

    # Process the file
    process_overpass_json(input_file, output_dir, simplification_tolerance=0.01)
