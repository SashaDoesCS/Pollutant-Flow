import json
import pickle

def pickle_geojson(input_file, output_file):
    """
    Reads a UTF-8 encoded GeoJSON file, pickles it, and saves the pickled object to a file.

    :param input_file: Path to the GeoJSON file to be pickled.
    :param output_file: Path to save the pickled file.
    """
    try:
        # Load the GeoJSON data
        print("Loading GeoJSON data...")
        with open(input_file, 'r', encoding='utf-8') as geojson_file:
            geojson_data = json.load(geojson_file)

        # Pickle the data
        print("Pickling data...")
        with open(output_file, 'wb') as pickle_file:
            pickle.dump(geojson_data, pickle_file)

        print(f"GeoJSON data successfully pickled to {output_file}")
    except Exception as e:
        print(f"Error: {e}")

def retrieve_pickled_data(pickle_file):
    """
    Reads and returns data from a pickled file.

    :param pickle_file: Path to the pickled file.
    :return: Unpickled data.
    """
    try:
        print("Loading pickled data...")
        with open(pickle_file, 'rb') as file:
            data = pickle.load(file)
        print("Data successfully loaded from pickled file.")
        return data
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    # Paths for input GeoJSON and output pickle file
    geojson_file_path = "combined_rivers_pollutants.geojson"  # Ensure this file exists in your directory
    pickle_file_path = "combined_rivers_pollutants.pkl"

    # Pickle the GeoJSON file
    pickle_geojson(geojson_file_path, pickle_file_path)

    # Retrieve and inspect the pickled data
    data = retrieve_pickled_data(pickle_file_path)
    if data:
        # Print summary information about the data
        if isinstance(data, dict):
            print(f"Top-level keys: {list(data.keys())}")
            if 'features' in data:
                print(f"Number of features: {len(data['features'])}")
                print(f"Example feature: {data['features'][0]}")
        else:
            print("Unexpected data format.")
