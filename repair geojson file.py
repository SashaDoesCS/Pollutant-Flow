import geopandas as gpd
from shapely.geometry import shape, mapping
from shapely.validation import make_valid
import json
import logging
import os
import pandas as pd
from shapely.geometry import Point


def repair_geojson(input_file, output_file):
    """
    Repairs a GeoJSON file by fixing common geometry issues and validates the output.
    Handles different file encodings.

    Args:
        input_file (str): Path to the input GeoJSON file
        output_file (str): Path to save the repaired GeoJSON file
    """
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Try different encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1']
        geojson_data = None

        for encoding in encodings:
            try:
                logger.info(f"Attempting to read file with {encoding} encoding...")
                with open(input_file, 'r', encoding=encoding) as f:
                    geojson_data = json.load(f)
                logger.info(f"Successfully read file with {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
            except json.JSONDecodeError:
                continue

        if geojson_data is None:
            raise ValueError("Could not read the GeoJSON file with any of the attempted encodings")

        # Initialize counters for reporting
        total_features = len(geojson_data['features'])
        fixed_features = 0
        invalid_features = 0

        # Process each feature
        repaired_features = []
        for feature in geojson_data['features']:
            try:
                if feature['geometry'] is None:
                    logger.warning("Skipping feature with null geometry")
                    invalid_features += 1
                    continue

                # Convert to shapely geometry
                geom = shape(feature['geometry'])

                # Check if geometry is valid
                if not geom.is_valid:
                    # Attempt to repair the geometry
                    fixed_geom = make_valid(geom)
                    if fixed_geom.is_valid:
                        feature['geometry'] = mapping(fixed_geom)
                        fixed_features += 1
                    else:
                        invalid_features += 1
                        continue

                repaired_features.append(feature)

            except Exception as e:
                logger.error(f"Error processing feature: {str(e)}")
                invalid_features += 1
                continue

        # Create new GeoJSON with repaired features
        repaired_geojson = {
            'type': 'FeatureCollection',
            'features': repaired_features
        }

        # Save repaired GeoJSON using UTF-8 encoding
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(repaired_geojson, f, ensure_ascii=False)

        # Validate the output using geopandas
        try:
            gdf = gpd.read_file(output_file)
            logger.info("Output file successfully validated with GeoPandas")
        except Exception as e:
            logger.error(f"Output validation failed: {str(e)}")
            raise

        # Report results
        logger.info(f"Total features processed: {total_features}")
        logger.info(f"Features fixed: {fixed_features}")
        logger.info(f"Invalid features removed: {invalid_features}")
        logger.info(f"Features in output: {len(repaired_features)}")

        return True

    except Exception as e:
        logger.error(f"Failed to repair GeoJSON: {str(e)}")
        return False


def integrate_pollutants_with_rivers(pollutant_file, river_geojson, output_file):
    """
    Combines pollutant data with river GeoDataFrame based on spatial proximity.
    """
    try:
        # Load pollutant data
        print("Loading pollutant data...")
        pollutants_df = pd.read_csv(pollutant_file, low_memory=False)

        # Print some diagnostic information
        print("\nDiagnostic Information:")
        print(f"Number of pollutant records: {len(pollutants_df)}")
        print("\nSample of coordinates:")
        print(pollutants_df[['Latitude', 'Longitude']].head())

        # Convert pollutant data to GeoDataFrame
        pollutants_df['geometry'] = pollutants_df.apply(
            lambda row: Point(row['Longitude'], row['Latitude']), axis=1)
        pollutants_gdf = gpd.GeoDataFrame(pollutants_df, geometry='geometry', crs="EPSG:4326")

        # Load river GeoDataFrame
        print("\nLoading river data...")
        rivers_gdf = gpd.read_file(river_geojson)

        print(f"\nRiver CRS: {rivers_gdf.crs}")
        print(f"Pollutants CRS: {pollutants_gdf.crs}")

        # Ensure both datasets are in the same CRS
        if rivers_gdf.crs != pollutants_gdf.crs:
            print("Converting river data to EPSG:4326...")
            rivers_gdf = rivers_gdf.to_crs("EPSG:4326")

        # Create a buffer around rivers (0.001 degrees ≈ 100 meters)
        print("\nCreating buffer around rivers...")
        rivers_gdf['geometry'] = rivers_gdf.geometry.buffer(0.001)

        # Perform a spatial join using nearest neighbor approach
        print("\nCombining datasets...")
        combined_gdf = gpd.sjoin_nearest(
            pollutants_gdf,
            rivers_gdf,
            how="left",  # Keep all pollutant points
            max_distance=0.001  # Maximum distance in degrees (about 100m)
        )

        print(f"\nNumber of matched features: {len(combined_gdf)}")

        # Save the combined GeoDataFrame
        if len(combined_gdf) > 0:
            combined_gdf.to_file(output_file, driver="GeoJSON")
            print(f"\nCombined dataset saved to {output_file}")
        else:
            print("\nWARNING: No matches found between pollutants and rivers!")

        return combined_gdf

    except Exception as e:
        print(f"An error occurred: {e}")
        raise


def repair_and_combine_data(river_file, pollutant_file, output_file):
    """
    Repairs river GeoJSON and combines it with pollutant data.
    """
    repaired_river_file = "repaired_rivers.geojson"
    if repair_geojson(river_file, repaired_river_file):
        integrate_pollutants_with_rivers(pollutant_file, repaired_river_file, output_file)
    else:
        logging.error("Failed to repair river GeoJSON file")


# Add at the bottom of your script
if __name__ == "__main__":
    # File paths
    river_geojson = "water_features_pipeline/cache/massachusetts_raw.geojson"
    pollutant_csv = "labdatamain-8-23-2022.csv"
    output_file = "combined_rivers_pollutants.geojson"

    print("Starting repair and combination process...")

    # First repair the GeoJSON
    repaired_river_file = "repaired_rivers.geojson"
    if repair_geojson(river_geojson, repaired_river_file):
        # Try to combine the data
        result = integrate_pollutants_with_rivers(pollutant_csv, repaired_river_file, output_file)

        # Print some information about the result
        if result is not None:
            print("\nFinal Results:")
            print(f"Total pollutant points matched: {len(result)}")
            if len(result) > 0:
                print("\nSample of combined data:")
                print(result[['Latitude', 'Longitude', 'DWM_Name', 'ResVal']].head())
    else:
        logging.error("Failed to repair river GeoJSON file")
        