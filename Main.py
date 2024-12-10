import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
import pickle
from collections import defaultdict
from datetime import datetime
import folium
import branca.colormap as cm
import webbrowser
import os
import json
from heapq import heappush, heappop


def log_error(message):
    """Log errors to a file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("river_simulation_error.log", "a", encoding='utf-8') as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def preprocess_river_data(data, river_name):
    """
    Preprocess river data to extract nodes and relevant information.

    Args:
        data (dict): Raw data containing river information
        river_name (str): Name of the river to process

    Returns:
        list: Processed river nodes with location, pollution, and flow rate information
    """
    print(f"Preprocessing data for river: {river_name}")

    if not isinstance(data, dict) or 'features' not in data:
        error_msg = "Error: Invalid dataset structure"
        log_error(error_msg)
        print(error_msg)
        return []

    features = data['features']
    river_nodes = []

    try:
        for feature in features:
            properties = feature.get('properties', {})
            geometry = feature.get('geometry', {})

            # Extract waterbody name
            waterbody_name = properties.get('Waterbody') or properties.get('name')

            if waterbody_name and river_name.lower() in waterbody_name.lower():
                # Get coordinates and convert to (latitude, longitude)
                coordinates = geometry.get('coordinates', [0, 0])
                location = (coordinates[1], coordinates[0])

                # Extract pollution data with default value
                pollution = float(properties.get('nResult', 1.0))

                # Extract and process flow rate with default value
                flow_stat = properties.get('FLOWSTAT', "1")
                try:
                    flow_rate = float(flow_stat)
                except ValueError:
                    # Convert text-based flow status to numerical values
                    flow_mapping = {
                        "flowing": 2.0,
                        "high": 3.0,
                        "moderate": 1.5,
                        "low": 0.5,
                        "stagnant": 0.1
                    }
                    flow_rate = flow_mapping.get(flow_stat.lower(), 1.0)

                # Create node data with default values for missing properties
                node_data = {
                    'location': location,
                    'pollution': pollution,
                    'flow_rate': flow_rate,
                    'properties': {
                        'depth': float(properties.get('depth', 1.0)),  # Default depth of 1.0
                        'temperature': float(properties.get('temperature', 20.0)),  # Default temp of 20°C
                        'ph': float(properties.get('ph', 7.0))  # Default pH of 7.0
                    }
                }

                river_nodes.append(node_data)

        # Sort nodes by latitude to ensure proper flow direction
        river_nodes.sort(key=lambda x: x['location'][0])

        print(f"Preprocessing complete. Found {len(river_nodes)} nodes for river '{river_name}'")

        # Log summary statistics if nodes were found
        if river_nodes:
            avg_pollution = np.mean([node['pollution'] for node in river_nodes])
            max_pollution = max([node['pollution'] for node in river_nodes])
            print(f"Average pollution level: {avg_pollution:.2f}")
            print(f"Maximum pollution level: {max_pollution:.2f}")
        else:
            print(f"Warning: No nodes found for river '{river_name}'")

        return river_nodes

    except Exception as e:
        error_msg = f"Error during preprocessing: {str(e)}"
        log_error(error_msg)
        print(error_msg)
        return []

class RiverParameters:
    """Class to store river-specific parameters and thresholds."""
    def __init__(self, name, params=None):
        self.name = name
        default_params = {
            'max_pollution': 3.0,
            'base_decay_rate': 0.15,
            'dilution_factor': 0.2,
            'pollution_thresholds': {
                'safe': 0.5,
                'warning': 0.8,
                'danger': 1.3
            },
            'flow_rate_multiplier': 1.0,
            'pollution_scale_factor': 1.5
        }
        self.params = params if params else default_params

    @classmethod
    def from_river_type(cls, name, river_type):
        """Create parameters based on river type (small, medium, large)."""
        type_params = {
            'small': {
                'max_pollution': 2.0,
                'base_decay_rate': 0.2,
                'dilution_factor': 0.15,
                'pollution_thresholds': {'safe': 0.3, 'warning': 0.7, 'danger': 1.2},
                'flow_rate_multiplier': 0.7,
                'pollution_scale_factor': 1.2
            },
            'medium': {
                'max_pollution': 3.0,
                'base_decay_rate': 0.15,
                'dilution_factor': 0.2,
                'pollution_thresholds': {'safe': 0.5, 'warning': 1.0, 'danger': 1.5},
                'flow_rate_multiplier': 1.0,
                'pollution_scale_factor': 1.5
            },
            'large': {
                'max_pollution': 4.0,
                'base_decay_rate': 0.1,
                'dilution_factor': 0.25,
                'pollution_thresholds': {'safe': 0.3, 'warning': 0.8, 'danger': 1.3},
                'flow_rate_multiplier': 1.3,
                'pollution_scale_factor': 1.8
            }
        }
        return cls(name, type_params.get(river_type.lower(), type_params['medium']))


class RiverNode:
    def __init__(self, location, initial_pollution, flow_rate):
        self.location = location
        self.pollution = max(0.1, initial_pollution)
        self.flow_rate = max(0.1, flow_rate)
        self.accumulation_factor = 0
        self.properties = {}
        self.base_pollution = initial_pollution
        self.depth = 1.0


class RiverNetwork:
    def __init__(self, river_data, river_params):
        self.params = river_params
        self.nodes = []
        if not river_data:
            raise ValueError("No river data provided")
        self._build_network(river_data)
        self._calculate_accumulation_factors()


class TreeNode:
    def __init__(self, river_node):
        self.river_node = river_node
        self.children = []
        self.parent = None
        self.depth = 0  # Distance from root

    def add_child(self, child_node):
        """Add a child node to this node"""
        child_node.parent = self
        child_node.depth = self.depth + 1
        self.children.append(child_node)

    def get_ancestors(self):
        """Get all ancestors of this node"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors


class RiverTree:
    def __init__(self):
        self.root = None
        self.nodes = {}  # Map river nodes to tree nodes

    def build_from_river_network(self, river_network):
        """Build a tree from the river network"""
        if not river_network.nodes:
            return

        # Create the root from the first river node
        self.root = TreeNode(river_network.nodes[0])
        self.nodes[river_network.nodes[0]] = self.root

        # Build the rest of the tree
        for i in range(1, len(river_network.nodes)):
            river_node = river_network.nodes[i]
            tree_node = TreeNode(river_node)
            self.nodes[river_node] = tree_node

            # Connect to parent (previous node in the sequence)
            parent_node = self.nodes[river_network.nodes[i - 1]]
            parent_node.add_child(tree_node)

    def print_tree(self, num_nodes=5):
        """Print a subset of the tree structure"""

        def _print_node(node, prefix="", nodes_printed=0):
            if nodes_printed >= num_nodes:
                return nodes_printed

            pollution = node.river_node.pollution
            location = node.river_node.location
            print(f"{prefix}Location: ({location[0]:.2f}, {location[1]:.2f}), "
                  f"Pollution: {pollution:.2f}, Depth: {node.depth}")

            nodes_printed += 1

            for child in node.children:
                if nodes_printed < num_nodes:
                    nodes_printed = _print_node(child, prefix + "  ", nodes_printed)
                else:
                    break

            return nodes_printed

        if self.root:
            print("\nRiver Network Tree Structure (First 5 nodes):")
            _print_node(self.root)
            total_nodes = sum(1 for _ in self.nodes)
            if total_nodes > num_nodes:
                print(f"... and {total_nodes - num_nodes} more nodes")
        else:
            print("Empty tree")


class RiverNetworkModified(RiverNetwork):
    def _build_network_with_cycle(self, river_data):
        """
        Override _build_network to introduce a cycle in the graph.
        """
        self._build_network(river_data)
        # Introduce a cycle: Connect the last node back to the first node
        if len(self.nodes) > 2:
            self.nodes[-1].properties['next_node'] = self.nodes[0]

    def simulate_pollutant_flow_with_priority(self, time_steps=150):
        """
        Simulate pollutant flow using a priority queue to process nodes based on pollution levels.
        """
        history = defaultdict(list)
        locations = np.array([node.location for node in self.nodes])

        for step in range(time_steps):
            # Use a priority queue to process nodes based on current pollution levels
            pq = []
            for i, node in enumerate(self.nodes):
                heappush(pq, (-node.pollution, i))  # Max-heap by negative pollution

            new_pollution = [0] * len(self.nodes)

            while pq:
                _, i = heappop(pq)
                node = self.nodes[i]

                # Decay, dilution, and upstream effects (as before)
                decay_rate = (self.params.params['base_decay_rate'] *
                              (1 + node.flow_rate / 10))
                upstream_pollution = 0
                if i > 0:
                    upstream_pollution = (
                            self.nodes[i - 1].pollution *
                            (1 - self.nodes[i - 1].accumulation_factor) *
                            (1 - decay_rate)
                    )

                local_contribution = node.base_pollution * 0.3
                dilution = 1 - (self.params.params['dilution_factor'] * (i / len(self.nodes)))
                total_pollution = (upstream_pollution + local_contribution) * dilution
                new_pollution[i] = min(
                    self.params.params['max_pollution'],
                    max(0.1, total_pollution)
                )

            for i, node in enumerate(self.nodes):
                node.pollution = new_pollution[i]

            history[step] = {
                'pollution_levels': [node.pollution for node in self.nodes],
                'locations': locations
            }

        return history

        def find_highest_pollution_path(self):
            """
            Use a stack to find the path with the highest pollution from the first node.
            """
            stack = [(0, 0, [])]  # (current node index, pollution, path)
            max_path = (0, [])  # (max pollution, path)

            while stack:
                current_index, pollution_sum, path = stack.pop()
                path = path + [current_index]
                current_node = self.nodes[current_index]

                # Update max path if necessary
                if pollution_sum > max_path[0]:
                    max_path = (pollution_sum, path)

                # Add neighbors to the stack (simulate next_node connectivity for the graph)
                for next_index in range(current_index + 1, len(self.nodes)):
                    next_node = self.nodes[next_index]
                    stack.append((next_index, pollution_sum + next_node.pollution, path))

            return max_path


    def _build_network(self, river_data):
        """Build river network with proper error handling and default values."""
        for node_data in river_data:
            try:
                location = node_data['location']
                raw_pollution = float(node_data.get('pollution', 1.0))
                scaled_pollution = min(
                    self.params.params['max_pollution'],
                    (raw_pollution / max(1, raw_pollution)) * self.params.params['pollution_scale_factor']
                )
                pollution = max(0.1, scaled_pollution)

                # Get flow rate and depth with default values
                base_flow = float(node_data.get('flow_rate', 1.0))
                properties = node_data.get('properties', {})
                depth = float(properties.get('depth', 1.0))

                # Calculate flow rate with safety checks
                flow_multiplier = float(self.params.params.get('flow_rate_multiplier', 1.0))
                flow_rate = max(0.1, base_flow * flow_multiplier * (1 + depth / 10))

                # Create node with validated data
                node = RiverNode(location, pollution, flow_rate)
                node.properties = properties
                node.depth = depth
                self.nodes.append(node)

            except (ValueError, TypeError, KeyError) as e:
                error_msg = f"Error processing node data: {str(e)}"
                log_error(error_msg)
                print(error_msg)
                continue

    def _build_network(self, river_data):
        for node_data in river_data:
            location = node_data['location']
            raw_pollution = node_data.get('pollution', 0)
            scaled_pollution = min(
                self.params.params['max_pollution'],
                (raw_pollution / max(1, raw_pollution)) * self.params.params['pollution_scale_factor']
            )
            pollution = max(0.1, scaled_pollution)

            base_flow = node_data.get('flow_rate', 1)
            depth = node_data['properties'].get('depth', 1)
            flow_rate = max(0.1, base_flow * self.params.params['flow_rate_multiplier'] * (1 + depth / 10))

            node = RiverNode(location, pollution, flow_rate)
            node.properties = node_data.get('properties', {})
            node.depth = depth
            self.nodes.append(node)

    def _calculate_accumulation_factors(self):
        """Calculate accumulation factors with error handling."""
        for i in range(len(self.nodes)):
            try:
                if i > 0:
                    prev_depth = max(0.1, self.nodes[i - 1].depth)
                    curr_depth = max(0.1, self.nodes[i].depth)
                    depth_ratio = curr_depth / prev_depth

                    prev_flow = max(0.1, self.nodes[i - 1].flow_rate)
                    curr_flow = max(0.1, self.nodes[i].flow_rate)
                    flow_ratio = curr_flow / prev_flow

                    self.nodes[i].accumulation_factor = min(0.3,
                        0.05 + 0.1 * (1 / depth_ratio) + 0.05 * (1 / flow_ratio))
            except Exception as e:
                error_msg = f"Error calculating accumulation factor for node {i}: {str(e)}"
                log_error(error_msg)
                print(error_msg)
                self.nodes[i].accumulation_factor = 0.1  # Default value


    def simulate_pollutant_flow(self, time_steps=150):
        history = defaultdict(list)
        locations = np.array([node.location for node in self.nodes])

        for step in range(time_steps):
            new_pollution = [0] * len(self.nodes)

            for i, node in enumerate(self.nodes):
                temperature = node.properties.get('temperature', 20)
                temp_factor = 1 + (temperature - 20) / 100

                decay_rate = (self.params.params['base_decay_rate'] * temp_factor *
                            (1 + node.flow_rate / 10))

                upstream_pollution = 0
                if i > 0:
                    upstream_pollution = (
                        self.nodes[i - 1].pollution *
                        (1 - self.nodes[i - 1].accumulation_factor) *
                        (1 - decay_rate)
                    )

                local_contribution = node.base_pollution * 0.3
                dilution = 1 - (self.params.params['dilution_factor'] * (i / len(self.nodes)))
                total_pollution = (upstream_pollution + local_contribution) * dilution
                new_pollution[i] = min(
                    self.params.params['max_pollution'],
                    max(0.1, total_pollution)
                )

            for i, node in enumerate(self.nodes):
                node.pollution = new_pollution[i]

            history[step] = {
                'pollution_levels': [node.pollution for node in self.nodes],
                'locations': locations
            }

        return history

def create_interactive_map(river_network, history, save_html=True):
    """Create an interactive map visualization with adjusted pollution thresholds."""
    if not os.path.exists('maps'):
        os.makedirs('maps')

    locations = [node.location for node in river_network.nodes]
    center_lat = np.mean([loc[0] for loc in locations])
    center_lon = np.mean([loc[1] for loc in locations])

    maps = []

    # Adjusted colormap for new thresholds
    colormap = cm.LinearColormap(
        colors=['#00ff00', '#ffff00', '#ff0000'],
        vmin=0.1,
        vmax=1.5,
        caption='Pollution Level of Nitrogen (mg/L)'
    )

    for timestep in range(len(history)):
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=8,
            tiles='CartoDB positron',
            prefer_canvas=True
        )

        current_state = history[timestep]

        # Draw river segments with enhanced styling
        for i in range(len(locations) - 1):
            start_loc = locations[i]
            end_loc = locations[i + 1]
            pollution_level = current_state['pollution_levels'][i]
            color = colormap.rgb_hex_str(pollution_level)

            # Enhanced river visualization
            folium.PolyLine(
                locations=[[start_loc[0], start_loc[1]], [end_loc[0], end_loc[1]]],
                color=color,
                weight=5,
                opacity=0.8,
                smooth_factor=1.5
            ).add_to(m)

            # Enhanced station markers
            popup_content = f"""
                                    <div style='font-family: Arial; min-width: 200px'>
                                        <h4 style='margin: 0; color: #333'>Monitoring Station {i + 1}</h4>
                                        <hr style='margin: 5px 0'>
                                        <table style='width: 100%; border-spacing: 5px'>
                                            <tr>
                                                <td><b>Pollution Level:</b></td>
                                                <td>{pollution_level:.2f} mg/L</td>
                                            </tr>
                                            <tr>
                                                <td><b>Flow Rate:</b></td>
                                                <td>{river_network.nodes[i].flow_rate:.2f} m³/s</td>
                                            </tr>
                                            <tr>
                                                <td><b>pH:</b></td>
                                                <td>{river_network.nodes[i].properties.get('ph', 'N/A')}</td>
                                            </tr>
                                            <tr>
                                                <td><b>Temperature:</b></td>
                                                <td>{river_network.nodes[i].properties.get('temperature', 'N/A')}°C</td>
                                            </tr>
                                        </table>
                                    </div>
                                """

            folium.CircleMarker(
                location=[start_loc[0], start_loc[1]],
                radius=8,
                color='black',
                weight=1,
                fill_color=color,
                fill_opacity=0.9,
                popup=folium.Popup(popup_content, max_width=300),
            ).add_to(m)

        # Enhanced timestamp display
        title_html = f'''
                                <div style="position: fixed; 
                                            top: 20px; 
                                            left: 60px; 
                                            z-index: 9999; 
                                            background-color: white; 
                                            padding: 15px; 
                                            border: 2px solid rgba(0,0,0,0.2); 
                                            border-radius: 8px;
                                            box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                                    <h3 style="margin: 0; font-family: Arial; color: #333;">
                                        River Pollution Simulation - Hour {timestep}
                                    </h3>
                                </div>
                            '''
        m.get_root().html.add_child(folium.Element(title_html))
        colormap.add_to(m)

        output_file = f'maps/river_pollution_timestep_{timestep}.html'
        m.save(output_file)
        maps.append(output_file)

    return maps

    return maps

def create_animation_html(map_files):
    """Create an enhanced animation interface with correct file paths."""
    animation_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>River Pollution Simulation</title>
        <style>
            body { margin: 0; padding: 0; font-family: Arial, sans-serif; }
            #map-container { width: 100%; height: 100vh; }
            #controls { 
                position: fixed; 
                bottom: 30px; 
                left: 50%; 
                transform: translateX(-50%);
                z-index: 1000;
                background: white;
                padding: 15px 25px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .button {
                background-color: #2196F3;
                border: none;
                color: white;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
                margin: 4px 2px;
                cursor: pointer;
                border-radius: 5px;
                transition: background-color 0.3s;
            }
            .button:hover {
                background-color: #1976D2;
            }
            #timestep {
                font-size: 16px;
                color: #333;
                min-width: 120px;
            }
            #speed-control {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            select.button {
                padding: 8px 15px;
                background-color: #1976D2;
            }
            select.button option {
                background-color: white;
                color: #333;
            }
        </style>
    </head>
    <body>
        <div id="map-container"></div>
        <div id="controls">
            <button class="button" onclick="startStop()" id="playButton">Play</button>
            <button class="button" onclick="previousFrame()">←</button>
            <button class="button" onclick="nextFrame()">→</button>
            <span id="timestep">Hour: 0</span>
            <div id="speed-control">
                <span>Speed:</span>
                <select onchange="updateSpeed(this.value)" class="button">
                    <option value="2000">0.5x</option>
                    <option value="1000" selected>1x</option>
                    <option value="500">2x</option>
                    <option value="250">4x</option>
                </select>
            </div>
        </div>
        <script>
            const frames = FRAME_LIST;
            let currentFrame = 0;
            let isPlaying = false;
            let intervalId = null;
            let speed = 1000;

            function loadFrame(index) {
                document.getElementById('map-container').innerHTML = 
                    `<iframe src="maps/${frames[index]}" width="100%" height="100%" frameborder="0"></iframe>`;
                document.getElementById('timestep').textContent = `Hour: ${index}`;
            }

            function nextFrame() {
                currentFrame = (currentFrame + 1) % frames.length;
                loadFrame(currentFrame);
            }

            function previousFrame() {
                currentFrame = (currentFrame - 1 + frames.length) % frames.length;
                loadFrame(currentFrame);
            }

            function updateSpeed(newSpeed) {
                speed = parseInt(newSpeed);
                if (isPlaying) {
                    clearInterval(intervalId);
                    intervalId = setInterval(nextFrame, speed);
                }
            }

            function startStop() {
                const playButton = document.getElementById('playButton');
                if (isPlaying) {
                    clearInterval(intervalId);
                    isPlaying = false;
                    playButton.textContent = 'Play';
                } else {
                    intervalId = setInterval(nextFrame, speed);
                    isPlaying = true;
                    playButton.textContent = 'Pause';
                }
            }

            // Add keyboard controls
            document.addEventListener('keydown', function(event) {
                switch(event.key) {
                    case ' ':  // Spacebar
                        startStop();
                        break;
                    case 'ArrowLeft':
                        previousFrame();
                        break;
                    case 'ArrowRight':
                        nextFrame();
                        break;
                }
            });

            loadFrame(0);
        </script>
    </body>
    </html>
    """

    # Convert map_files to just filenames without the 'maps/' directory
    map_files = [os.path.basename(f) for f in map_files]
    animation_html = animation_html.replace('FRAME_LIST', json.dumps(map_files))

    output_file = 'river_pollution_animation.html'
    with open(output_file, 'w', encoding="utf-8") as f:
        f.write(animation_html)

    return output_file


def create_manual_river_data(river_name, num_nodes):
    """
    Create synthetic river data when no real data is available.

    Args:
        river_name (str): Name of the river
        num_nodes (int): Number of nodes to create

    Returns:
        dict: Synthetic river data in the expected format
    """
    try:
        print(f"Creating synthetic data for {river_name} with {num_nodes} nodes...")

        # Get base coordinates from user
        print("\nEnter approximate start point coordinates:")
        start_lat = float(input("Start latitude (e.g., 41.5): ").strip())
        start_lon = float(input("Start longitude (e.g., -72.5): ").strip())

        print("\nEnter approximate end point coordinates:")
        end_lat = float(input("End latitude (e.g., 41.8): ").strip())
        end_lon = float(input("End longitude (e.g., -72.8): ").strip())

        # Create evenly spaced coordinates
        lats = np.linspace(start_lat, end_lat, num_nodes)
        lons = np.linspace(start_lon, end_lon, num_nodes)

        # Generate synthetic river data
        features = []
        for i in range(num_nodes):
            # Create more realistic varying values
            depth = round(np.random.uniform(1.0, 5.0), 2)  # Depth between 1-5 meters
            temperature = round(np.random.uniform(15.0, 25.0), 1)  # Temperature between 15-25°C
            ph = round(np.random.uniform(6.5, 8.5), 1)  # pH between 6.5-8.5
            pollution = round(np.random.uniform(0.5, 2.0), 2)  # Initial pollution levels
            flow_rate = round(np.random.uniform(1.0, 3.0), 2)  # Flow rate variation

            feature = {
                'type': 'Feature',
                'properties': {
                    'Waterbody': river_name,
                    'nResult': pollution,
                    'FLOWSTAT': str(flow_rate),
                    'depth': depth,
                    'temperature': temperature,
                    'ph': ph
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(lons[i]), float(lats[i])]
                }
            }
            features.append(feature)

        return {
            'type': 'FeatureCollection',
            'features': features
        }

    except ValueError as e:
        print(f"Error: Invalid input - {str(e)}")
        return None
    except Exception as e:
        print(f"Error creating synthetic data: {str(e)}")
        return None


def main():
    try:
        # Create necessary directories
        for directory in ['logs', 'maps', 'output']:
            if not os.path.exists(directory):
                os.makedirs(directory)

        file_path = "combined_rivers_pollutants.pkl"
        river_name = input("Enter the river name: ").strip()
        river_type = input("Enter river type (small/medium/large): ").strip().lower()

        # Validate river type
        if river_type not in ['small', 'medium', 'large']:
            print(f"Invalid river type '{river_type}'. Defaulting to 'medium'")
            river_type = 'medium'

        # Try to load real data first
        river_data = None
        try:
            print(f"Loading data from {file_path}...")
            with open(file_path, 'rb') as file:
                data = pickle.load(file)
            river_data = preprocess_river_data(data, river_name)
        except (FileNotFoundError, pickle.PickleError) as e:
            print(f"Could not load data from file: {str(e)}")

        # If no data is found or loading failed, offer manual creation
        if not river_data:
            print("\nNo data found for this river. Would you like to create synthetic data?")
            create_synthetic = input("Enter 'y' for yes, any other key to exit: ").strip().lower()

            if create_synthetic == 'y':
                while True:
                    try:
                        num_nodes = int(input("Enter the number of nodes to create (5-50): "))
                        if 5 <= num_nodes <= 50:
                            break
                        print("Please enter a number between 5 and 50.")
                    except ValueError:
                        print("Please enter a valid number.")

                synthetic_data = create_manual_river_data(river_name, num_nodes)
                if synthetic_data:
                    river_data = preprocess_river_data(synthetic_data, river_name)
                else:
                    print("Failed to create synthetic data.")
                    return
            else:
                print("Exiting program.")
                return

        print("Initializing river network...")
        river_params = RiverParameters.from_river_type(river_name, river_type)

        try:
            river = RiverNetworkModified(river_data, river_params)

            # Create and initialize the tree
            river_tree = RiverTree()
            river_tree.build_from_river_network(river)

            # Print the tree structure before simulation
            print("\nInitial River Network Tree Structure:")
            river_tree.print_tree()

        except ValueError as e:
            print(f"Error creating river network: {str(e)}")
            return

        print("\nSimulating pollutant flow...")
        history = river.simulate_pollutant_flow(time_steps=24)

        # Print the tree structure after simulation to show changes
        print("\nRiver Network Tree Structure After Simulation:")
        river_tree.print_tree()

        print("\nCreating visualization...")
        map_files = create_interactive_map(river, history)
        animation_file = create_animation_html(map_files)
        absolute_path = os.path.abspath(animation_file)

        print(f"\nOpening animation in web browser...")
        webbrowser.open('file://' + absolute_path)

        print("\nSimulation complete!")
        print(f"Simulation parameters for {river_name} ({river_type}):")
        print(f"Max pollution: {river_params.params['max_pollution']} mg/L")
        print(f"Base decay rate: {river_params.params['base_decay_rate']}")
        print(f"Dilution factor: {river_params.params['dilution_factor']}")
        print("\nThresholds:")
        for level, value in river_params.params['pollution_thresholds'].items():
            print(f"- {level.capitalize()}: {value} mg/L")

    except Exception as e:
        error_msg = f"An error occurred in main: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()