# Pollutant-Flow

Tested on Windows 11 only

This project is creates a simulation for rivers using river flow, available pollutant data from USGS NWIS, geodata provided by Open Street Map, animated with html. 
The system uses dynamic and greedy algorithms to cycle through multiple graphs in order to  mimic how river pollutants would flow in a river or stream. Tested on Massachusetts
Only due to the file sizes, be warned if downloading a larger state or multiple states, it might take awhile to read.

The following features are implemented in the main program:

Simulates and animates results of pollutant flow
Find pollutant hot spots
Capable of mapping smaller rivers and streams not normally available
Custom simulations
Statewide coverage transferable to any state with mapped rivers
User input rough coordinates and nodes for rivers with no major gauges 


Required libraries:
```
pip install matplotlib numpy folium branca pandas geopandas shapely

from tqdm import tqdm


```
There are several programs to assist with downloading. To use the program to download information, you will need to find the pollutant map for your state.
Here is the order in which the programs are meant to be used:


1. ExtractData

2. overpass json processing

3. simplify geometries 

4. simplify_geopackages

5. repair geojson file

6. Combine geodata and pollutant data
7. pickle file

With this you should have a file called combined_river_pollutants.pkl 
If this combined successfully then it should be able to load using main and run the simulation 

