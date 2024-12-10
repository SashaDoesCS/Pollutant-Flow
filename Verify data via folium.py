import folium
import geopandas as gpd
import os
import logging
from branca.colormap import LinearColormap
import json
from shapely.geometry import box
from tqdm import tqdm


class WaterFeaturesMapValidator:
    def __init__(self, data_dir='water_features_data'):
        """
        Initialize the map validator
        """
        self.data_dir = data_dir
        self.counties_dir = os.path.join(data_dir, 'counties')
        self.states_dir = os.path.join(data_dir, 'states')
        self.combined_dir = os.path.join(data_dir, 'combined')
        self.validation_dir = os.path.join(data_dir, 'validation')

        # Create validation directory if it doesn't exist
        os.makedirs(self.validation_dir, exist_ok=True)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

        # Define color schemes for different feature types
        self.color_schemes = {
            'river': '#0066cc',
            'stream': '#3399ff',
            'canal': '#0099cc',
            'lake': '#006699',
            'reservoir': '#004d99',
            'wetland': '#66ccff',
            'spring': '#00ffcc',
            'default': '#0033cc'
        }

    def validate_gpkg(self, file_path):
        """
        Validate that a GPKG file contains valid geospatial data
        """
        try:
            # Try to read the file
            gdf = gpd.read_file(file_path)

            # Basic validation checks
            if len(gdf) == 0:
                return False, "File contains no features"

            if not all(gdf.geometry.is_valid):
                return False, "File contains invalid geometries"

            # Check if geometries are within reasonable bounds
            bounds = gdf.total_bounds
            if not (-180 <= bounds[0] <= 180 and -90 <= bounds[1] <= 90):
                return False, "Features contain coordinates outside valid range"

            # Verify CRS is geographic or projected
            if gdf.crs is None:
                return False, "Missing coordinate reference system"

            return True, f"Valid file with {len(gdf)} features"

        except Exception as e:
            return False, f"Error reading file: {str(e)}"

    def create_map(self, gdf, title, output_file):
        # Ensure the GeoDataFrame has a projected CRS
        if gdf.crs and gdf.crs.is_geographic:
            gdf = gdf.to_crs(epsg=3857)

        # Get the centroid of all geometries for initial map center
        center_lat = gdf.geometry.centroid.y.mean()
        center_lon = gdf.geometry.centroid.x.mean()

        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='cartodbpositron'
        )

        # Add title
        title_html = f'''
            <div style="position: fixed; 
                        top: 10px; 
                        left: 50px; 
                        width: 800px; 
                        height: 40px; 
                        z-index:9999; 
                        font-size:20px;
                        font-weight: bold;
                        background-color: rgba(255, 255, 255, 0.8);
                        padding: 10px;
                        border-radius: 5px;">
                {title}
            </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))

        # Add features to map
        for _, row in gdf.iterrows():
            # Determine color based on feature type
            feature_color = self.color_schemes.get(
                row.get('category', '').lower(),
                self.color_schemes['default']
            )

            # Create popup content
            popup_content = '<br>'.join([
                f"<strong>{k}:</strong> {v}"
                for k, v in row.items()
                if k != 'geometry' and str(v) != 'nan'
            ])

            # Define a style function for the feature
            def style_function(feature):
                return {
                    'color': feature_color,
                    'weight': 2,
                    'fillOpacity': 0.5
                }

            # Add feature to map
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=style_function,
                popup=folium.Popup(popup_content, max_width=300)
            ).add_to(m)

        # Add layer control
        folium.LayerControl().add_to(m)

        # Save map
        m.save(output_file)
        return m

    def validate_and_map_file(self, file_path, output_name=None):
        """
        Validate a GPKG file and create a map if valid
        """
        logging.info(f"Validating {file_path}")

        # Validate file
        is_valid, message = self.validate_gpkg(file_path)

        if is_valid:
            logging.info(f"Validation successful: {message}")

            # Read data
            gdf = gpd.read_file(file_path)

            # Create output filename if not provided
            if output_name is None:
                output_name = os.path.splitext(os.path.basename(file_path))[0]

            output_file = os.path.join(self.validation_dir, f"{output_name}_validation.html")

            # Create map
            self.create_map(
                gdf,
                f"Water Features Validation Map - {output_name}",
                output_file
            )

            logging.info(f"Created validation map: {output_file}")
            return True, output_file
        else:
            logging.error(f"Validation failed: {message}")
            return False, message

    def validate_all_files(self):
        """
        Validate all GPKG files in the data directory
        """
        validation_results = {
            'counties': [],
            'states': [],
            'combined': []
        }

        # Validate county files
        for file in tqdm(os.listdir(self.counties_dir), desc="Validating counties"):
            if file.endswith('.gpkg'):
                file_path = os.path.join(self.counties_dir, file)
                success, result = self.validate_and_map_file(
                    file_path,
                    f"county_{os.path.splitext(file)[0]}"
                )
                validation_results['counties'].append({
                    'file': file,
                    'success': success,
                    'result': result
                })

        # Validate state files
        for file in tqdm(os.listdir(self.states_dir), desc="Validating states"):
            if file.endswith('.gpkg'):
                file_path = os.path.join(self.states_dir, file)
                success, result = self.validate_and_map_file(
                    file_path,
                    f"state_{os.path.splitext(file)[0]}"
                )
                validation_results['states'].append({
                    'file': file,
                    'success': success,
                    'result': result
                })

        # Validate combined file
        combined_file = os.path.join(self.combined_dir, 'usa_water_features.gpkg')
        if os.path.exists(combined_file):
            success, result = self.validate_and_map_file(combined_file, 'usa_combined')
            validation_results['combined'].append({
                'file': 'usa_water_features.gpkg',
                'success': success,
                'result': result
            })

        # Save validation results
        results_file = os.path.join(self.validation_dir, 'validation_results.json')
        with open(results_file, 'w') as f:
            json.dump(validation_results, f, indent=2)

        return validation_results


def main():
    validator = WaterFeaturesMapValidator()
    results = validator.validate_all_files()

    # Print summary
    print("\nValidation Summary:")
    for category, items in results.items():
        successful = sum(1 for item in items if item['success'])
        print(f"\n{category.title()}:")
        print(f"- Total files: {len(items)}")
        print(f"- Successfully validated: {successful}")
        print(f"- Failed validation: {len(items) - successful}")


if __name__ == "__main__":
    main()