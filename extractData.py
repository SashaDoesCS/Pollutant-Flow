import osmnx as ox
import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
import os
from datetime import datetime
import json
from tqdm import tqdm
import logging
import warnings

warnings.filterwarnings('ignore')


class WaterFeatureExtractor:
    def __init__(self, base_dir='water_features_data'):
        """
        Initialize the water feature extractor with organized directory structure
        """
        # Setup directory structure
        self.base_dir = base_dir
        self.state_dir = os.path.join(base_dir, 'states')
        self.combined_dir = os.path.join(base_dir, 'combined')
        self.logs_dir = os.path.join(base_dir, 'logs')

        # Create necessary directories
        for directory in [self.state_dir, self.combined_dir, self.logs_dir]:
            os.makedirs(directory, exist_ok=True)

        # Setup logging
        log_file = os.path.join(self.logs_dir, f'extraction_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

        # Water feature categories to extract
        self.water_tags = {
            'waterway': [
                'river', 'stream', 'canal', 'drain', 'ditch',
                'waterfall', 'rapids', 'lock'
            ],
            'natural': [
                'water', 'wetland', 'spring', 'hot_spring',
                'glacier', 'bay'
            ],
            'water': [
                'lake', 'reservoir', 'pond', 'basin', 'lagoon',
                'stream_pool', 'reflecting_pool', 'moat', 'wastewater'
            ],
            'leisure': ['marina'],
            'landuse': ['reservoir', 'basin']
        }

        # Initialize progress tracking
        self.progress = {
            'processed_states': set(),
            'failed_states': set()
        }

        # Configure OSMnx
        ox.config(use_cache=True, log_console=False)

    def load_progress(self):
        """Load progress from previous run if exists"""
        progress_file = os.path.join(self.base_dir, 'progress.json')
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                saved_progress = json.load(f)
                self.progress['processed_states'] = set(saved_progress.get('processed_states', []))
                self.progress['failed_states'] = set(saved_progress.get('failed_states', []))

    def save_progress(self):
        """Save current progress"""
        progress_file = os.path.join(self.base_dir, 'progress.json')
        with open(progress_file, 'w') as f:
            json.dump({
                'processed_states': list(self.progress['processed_states']),
                'failed_states': list(self.progress['failed_states'])
            }, f)

    def extract_state_features(self, state_name):
        """Extract water features for a single state"""
        if state_name in self.progress['processed_states']:
            logging.info(f"Skipping {state_name} - already processed")
            return None

        state_file = os.path.join(self.state_dir, f'{state_name.lower().replace(" ", "_")}_water_features.gpkg')

        try:
            # Get state boundary
            state_gdf = ox.geocode_to_gdf({'state': state_name, 'country': 'USA'})
            all_features = []

            # Process each water feature category
            for category, feature_types in self.water_tags.items():
                try:
                    features = ox.features_from_polygon(
                        state_gdf.unary_union,
                        tags={category: feature_types}
                    )

                    if len(features) > 0:
                        features['category'] = category
                        features['state'] = state_name
                        features['extraction_date'] = datetime.now().strftime("%Y-%m-%d")

                        # Keep relevant columns
                        cols_to_keep = ['name', 'category', 'state', 'extraction_date', 'geometry']
                        features = features[[col for col in cols_to_keep if col in features.columns]]

                        all_features.append(features)
                        logging.info(f"{state_name}: Found {len(features)} {category} features")

                except Exception as e:
                    logging.warning(f"Error extracting {category} features for {state_name}: {str(e)}")

            if all_features:
                # Combine all features for the state
                state_features = pd.concat(all_features, ignore_index=True)

                # Save state file
                state_features.to_file(state_file, driver='GPKG')
                logging.info(f"Saved {state_name} features to {state_file}")

                # Update progress
                self.progress['processed_states'].add(state_name)
                self.save_progress()

                return state_features

            return None

        except Exception as e:
            logging.error(f"Failed to process {state_name}: {str(e)}")
            self.progress['failed_states'].add(state_name)
            self.save_progress()
            return None

    def process_all_states(self):
        """Process all US states and generate combined file"""
        states = [
            'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California',
            'Colorado', 'Connecticut', 'Delaware', 'Florida', 'Georgia',
            'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa',
            'Kansas', 'Kentucky', 'Louisiana', 'Maine', 'Maryland',
            'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi', 'Missouri',
            'Montana', 'Nebraska', 'Nevada', 'New Hampshire', 'New Jersey',
            'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio',
            'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina',
            'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont',
            'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming'
        ]

        # Load any existing progress
        self.load_progress()

        # Process states with progress bar
        all_features = []
        for state in tqdm(states, desc="Processing states"):
            if state not in self.progress['processed_states']:
                features = self.extract_state_features(state)
                if features is not None:
                    all_features.append(features)

        # Combine existing state files with new ones
        for state in self.progress['processed_states']:
            state_file = os.path.join(self.state_dir, f'{state.lower().replace(" ", "_")}_water_features.gpkg')
            if os.path.exists(state_file):
                state_features = gpd.read_file(state_file)
                all_features.append(state_features)

        if all_features:
            # Create combined US file
            combined_file = os.path.join(self.combined_dir, 'usa_water_features.gpkg')
            combined_features = pd.concat(all_features, ignore_index=True)
            combined_features.to_file(combined_file, driver='GPKG')

            # Generate summary statistics
            self.generate_summary(combined_features)

            logging.info(f"Successfully created combined file: {combined_file}")
            return combined_features

        return None

    def generate_summary(self, features):
        """Generate and save summary statistics"""
        summary_file = os.path.join(self.combined_dir, 'summary_statistics.txt')

        with open(summary_file, 'w') as f:
            # Write basic statistics
            f.write("=== Water Features Summary ===\n\n")
            f.write(f"Total features: {len(features)}\n\n")

            # Features by state
            f.write("Features by State:\n")
            state_counts = features.groupby('state').size()
            for state, count in state_counts.items():
                f.write(f"{state}: {count}\n")

            # Features by category
            f.write("\nFeatures by Category:\n")
            category_counts = features.groupby('category').size()
            for category, count in category_counts.items():
                f.write(f"{category}: {count}\n")

            # Calculate areas and lengths
            linear_features = features[features.geometry.type.isin(['LineString', 'MultiLineString'])]
            polygon_features = features[features.geometry.type.isin(['Polygon', 'MultiPolygon'])]

            if len(linear_features) > 0:
                total_length = linear_features.geometry.length.sum()
                f.write(f"\nTotal length of linear features: {total_length / 1000:.2f} km\n")

            if len(polygon_features) > 0:
                total_area = polygon_features.geometry.area.sum()
                f.write(f"Total area of water bodies: {total_area / 1000000:.2f} km²\n")


def main():
    # Initialize extractor
    extractor = WaterFeatureExtractor()

    # Process all states and generate combined file
    logging.info("Starting water feature extraction for USA")
    features = extractor.process_all_states()

    if features is not None:
        logging.info("Process completed successfully!")
        logging.info(f"Results saved in '{extractor.base_dir}' directory")

        if extractor.progress['failed_states']:
            logging.warning(f"Failed states: {', '.join(extractor.progress['failed_states'])}")
    else:
        logging.error("No features were extracted")


if __name__ == "__main__":
    main()