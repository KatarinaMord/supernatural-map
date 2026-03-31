# KMZ Leaflet Map Exporter

This project turns your `.kmz` map layers into a simple web map you can open in a browser.
The final map uses Leaflet, the CartoDB Dark Matter retina basemap, and clickable popups that show each point's name and description.

## What This Is In Plain English

Think of the script as a converter.
It takes map files from `kmz_layers/`, reads the places stored inside them, chooses the right icons, and builds a finished map page in `map/index.html`.

You do not need to install web frameworks or Python packages.
The script uses only built-in Python tools.

## Words You Will See

- `KMZ`: a zipped map file. Your source data lives here.
- `KML`: the map data inside the KMZ. The script reads this part.
- `Leaflet`: the JavaScript library that draws the map in the browser.
- `Popup`: the small info box that appears when you click a marker.
- `Layer`: one group of points, such as `GHOSTS` or `HUMANOIDS`.

## What You Need Before Running It

- Python 3.10 or newer
- Your `.kmz` files inside `kmz_layers/`
- The icon SVG files in the project root
- Existing local Leaflet files somewhere in this repo, so the script can copy them into the final map

## The Main Idea

When you run:

```bash
python export_leaflet_map.py
```

the script does not edit your KMZ files.
It reads them, then creates a new ready-to-open website inside the `map/` folder.

## Notebook Walkthrough

If you want a slower, more beginner-friendly version of the same flow, open:

- `export_leaflet_map_walkthrough.ipynb`

That notebook is standalone. It rebuilds the exporter inside Jupyter and explains the file structure, Python libraries, KMZ/KML parsing, coordinate order, Leaflet assets, icon handling, and final HTML export step by step.

## Step-By-Step Flow

This is the full flow of the script, in the same order it runs:

1. `main()` starts the whole process.
2. `parse_args()` reads any options you gave on the command line, such as a custom title or a different output folder.
3. The script finds the project folder, then checks that `kmz_layers/` exists.
4. It looks for all `.kmz` files in that folder.
5. For each KMZ file, `load_kmz_layer()` opens it and reads the `doc.kml` file inside.
6. Inside the KML, the script looks for placemarks with point coordinates.
7. For each point, it keeps three things: the place name, the description, and the coordinates.
8. The layers are sorted into a consistent order, so they appear in a predictable way on the map.
9. `copy_leaflet_assets()` copies the local Leaflet files the web page needs to run.
10. `copy_layer_icons()` assigns the correct SVG icon to each layer. If a layer does not have a custom SVG, `write_generated_icon()` creates a simple fallback icon.
11. `build_html()` creates the actual web page code for the map.
12. `write_map()` saves that web page as `map/index.html`.
13. The script prints a short summary telling you how many layers and points were exported.

## What Each Function Does

This section is for understanding the script without needing to be a programmer.

| Function | Plain-language job | Why it matters |
| --- | --- | --- |
| `parse_args()` | Reads command line options. | Lets you change the title or folder paths without editing the code. |
| `normalize_layer_key()` | Cleans a layer name into a standard key like `HAUNTED_PLACES`. | Makes layer matching reliable. |
| `slugify()` | Turns text into a safe filename. | Used when creating icon file names. |
| `is_relative_to()` | Checks whether one path is inside another. | Helps the script avoid copying files from the output folder back into itself. |
| `javascript_json()` | Converts Python data into safe JavaScript text. | Lets the map page use the exported layer data correctly. |
| `text_value()` | Pulls text out of an XML element. | Used while reading names, descriptions, and coordinates from KML. |
| `parse_point_coordinates()` | Converts raw KML coordinates into map coordinates. | Leaflet needs coordinates in a different order than KML stores them. |
| `load_kmz_layer()` | Opens one KMZ and extracts its point data. | This is the main reader for your source map files. |
| `find_leaflet_assets()` | Searches the project for local Leaflet files. | The output map needs these files to display properly. |
| `copy_leaflet_assets()` | Copies Leaflet files into the export folder. | Makes the final map self-contained. |
| `write_generated_icon()` | Draws a simple SVG icon if no custom one exists. | Prevents a layer from being left without an icon. |
| `copy_layer_icons()` | Chooses and copies the icons for each layer. | Makes `GHOSTS`, `CREATURES`, and other layers visually distinct. |
| `build_html()` | Writes the web page content for the final map. | This is where the map layout, styling, popups, and base map are defined. |
| `write_map()` | Saves the generated HTML to disk. | Creates the `map/index.html` file you open later. |
| `main()` | Runs everything in the correct order. | It is the control center of the script. |

## What Goes In

Input files:

- `kmz_layers/*.kmz`
- `icon-creature-48.svg`
- `icon-ghost-48.svg`
- `icon-haunted-place-48.svg`
- `icon-humanoid-48.svg`
- Local Leaflet files already present somewhere in the repo

## What Comes Out

Output files:

- `map/index.html`: the web page
- `map/icons/`: the icons used by the web page
- `map/vendor/leaflet/`: the Leaflet files copied into the export

If you want to view the result, open `map/index.html` in a browser.

## What The Final Map Does

- Shows the Dark Matter retina basemap from CartoDB
- Adds one overlay layer per KMZ file
- Places a marker for each point found in the KMZ
- Opens a popup when you click a marker
- Shows the point name as the popup heading
- Shows the description under the heading
- Displays `No description available.` if the point has no description
- Shows a layer control in the top right so layers can be turned on and off

## Where To Edit Things

If you want to change how the result looks or behaves, these are the main places:

- `LAYER_CONFIG`: change which icon belongs to which layer
- `LAYER_ORDER`: change the order layers appear
- `DEFAULT_CENTER`: change the fallback center of the map
- `DEFAULT_ZOOM`: change the fallback zoom level
- `build_html()`: change the HTML, popup design, or basemap setup

## Limits To Be Aware Of

- The script currently reads only point placemarks
- Each KMZ needs to contain a KML file, usually named `doc.kml`
- The final map still needs internet access for the CartoDB basemap tiles
- If local Leaflet files cannot be found in the repo, export will fail

## Typical Use

If you are not changing the code, the normal workflow is:

1. Put your KMZ files into `kmz_layers/`
2. Run `python export_leaflet_map.py`
3. Wait for the summary message
4. Open `map/index.html`
5. Click markers to read the names and descriptions

## Optional Commands

Custom title:

```bash
python export_leaflet_map.py --title "Supernatural Slovakia"
```

Custom input and output folders:

```bash
python export_leaflet_map.py --kmz-dir kmz_layers --output-dir map
```

## Quick Safety Check

If you only want to check that the script is valid Python:

```bash
python -m py_compile export_leaflet_map.py
```
