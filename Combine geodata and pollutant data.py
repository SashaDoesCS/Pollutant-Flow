import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def integrate_pollutants_with_rivers(pollutant_file, river_geojson, output_file):
    """
    Combines pollutant data with river GeoDataFrame based on spatial proximity.

    Args:
        pollutant_file (str): Path to the CSV file containing pollutant data.
        river_geojson (str): Path to the GeoJSON file containing river data.
        output_file (str): Path to save the combined dataset.
    """
    try:
        # Load pollutant data
        print("Loading pollutant data...")
        pollutants_df = pd.read_csv(pollutant_file)

        # Ensure required columns exist
        required_columns = ['Latitude', 'Longitude', 'DWM_Name', 'DWM_Units', 'ResVal']
        if not all(col in pollutants_df.columns for col in required_columns):
            raise ValueError(f"The pollutant data must contain these columns: {', '.join(required_columns)}")

        # Convert pollutant data to GeoDataFrame
        pollutants_df['geometry'] = pollutants_df.apply(
            lambda row: Point(row['Longitude'], row['Latitude']), axis=1)
        pollutants_gdf = gpd.GeoDataFrame(pollutants_df, geometry='geometry', crs="EPSG:4326")

        # Check if the river GeoJSON file exists
        if not os.path.exists(river_geojson):
            raise FileNotFoundError(f"The river GeoJSON file does not exist: {river_geojson}")

        # Load river GeoDataFrame
        print("Loading river data...")
        rivers_gdf = gpd.read_file(river_geojson)

        # Perform a spatial join (pollutants with rivers)
        print("Combining datasets...")
        combined_gdf = gpd.sjoin(pollutants_gdf, rivers_gdf, how="inner", predicate="intersects")

        # Save the combined GeoDataFrame
        combined_gdf.to_file(output_file, driver="GeoJSON")
        print(f"Combined dataset saved to {output_file}")

    except FileNotFoundError as fnf_error:
        print(f"File not found: {fnf_error}")
    except Exception as e:
        print(f"An error occurred: {e}")

# File paths
pollutant_csv = "labdatamain-8-23-2022.csv"  # Path to the pollutant data CSV
river_geojson = "water_features_pipeline/cache/massachusetts_raw.geojson"  # Path to the GeoJSON file for rivers
output_file = "combined_rivers_pollutants.geojson"  # Path to save the combined data

# Run the integration function
integrate_pollutants_with_rivers(pollutant_csv, river_geojson, output_file)
