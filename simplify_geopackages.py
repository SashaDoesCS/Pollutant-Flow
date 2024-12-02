import os
import geopandas as gpd
import logging
from shapely.geometry import shape

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Simplification function
def simplify_geopackage_files(cache_dir, output_dir, simplification_tolerance=0.01):
    """
    Simplifies GeoPackage files and combines them into a single file.

    Args:
        cache_dir (str): Directory containing GeoPackage files to simplify.
        output_dir (str): Directory where the simplified output will be saved.
        simplification_tolerance (float): Tolerance for geometry simplification.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # List all files in cache directory
    files = [f for f in os.listdir(cache_dir) if f.endswith(".gpkg")]
    if not files:
        logging.error("No GeoPackage files found in the specified cache directory.")
        return

    combined_data = []
    for file in files:
        file_path = os.path.join(cache_dir, file)
        try:
            # Load the GeoPackage file
            logging.info(f"Processing file: {file}")
            gdf = gpd.read_file(file_path)

            # Simplify geometries
            logging.info(f"Simplifying geometries with tolerance {simplification_tolerance}")
            gdf['geometry'] = gdf['geometry'].simplify(tolerance=simplification_tolerance, preserve_topology=True)

            # Keep relevant columns (adjust as needed)
            cols_to_keep = ['name', 'category', 'state', 'geometry']
            gdf = gdf[[col for col in cols_to_keep if col in gdf.columns]]

            # Append to combined list
            combined_data.append(gdf)

        except Exception as e:
            logging.warning(f"Failed to process file {file}: {e}")
            continue

    if combined_data:
        # Combine all data into a single GeoDataFrame
        combined_gdf = gpd.GeoDataFrame(pd.concat(combined_data, ignore_index=True), crs=gdf.crs)

        # Save to output directory
        output_file = os.path.join(output_dir, "simplified_water_features.gpkg")
        combined_gdf.to_file(output_file, driver="GPKG", layer_creation_options=["SPATIALITE=TRUE"])
        logging.info(f"Simplified features saved to {output_file}")
    else:
        logging.warning("No data to combine after processing.")

# Main execution
if __name__ == "__main__":
    # Specify directories
    cache_dir = "cache"  # Replace with the actual cache directory path
    output_dir = "water_features_data/states/California"  # Replace with the desired output directory

    # Simplify the files
    simplify_geopackage_files(cache_dir, output_dir, simplification_tolerance=0.01)
