#!/usr/bin/env python3
"""Export KMZ layers to a standalone Leaflet map using CDN assets only.

- Uses Leaflet from CDN
- References marker icons directly from the project root
- Sanitises KML descriptions for cleaner popups
- Optionally adds a non-toggleable hatched country mask from a shapefile
"""

from __future__ import annotations

import argparse
import html
import json
import re
import textwrap
import zipfile
from pathlib import Path
from typing import Any
import warnings
import xml.etree.ElementTree as ET

import geopandas as gpd

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
DEFAULT_CENTER = [48.7, 19.6]
DEFAULT_ZOOM = 7
DEFAULT_BORDER_SHP = Path(r"C:\Users\andre\Desktop\cat_map\europe_bounds\NUTS_RG_01M_2024_4326.shp")

LAYER_CONFIG: dict[str, dict[str, str]] = {
    "HAUNTED_PLACES": {
        "icon_source": "icon-haunted-place-48.svg",
        "color": "#ff8e6e",
    },
    "HUMANOIDS": {
        "icon_source": "icon-humanoid-48.svg",
        "color": "#7ad1ff",
    },
    "NO_DESCRIPTION": {
        "color": "#43b7ff",
    },
    "CREATURES": {
        "icon_source": "icon-creature-48.svg",
        "color": "#8fdc69",
    },
    "GHOSTS": {
        "icon_source": "icon-ghost-48.svg",
        "color": "#f4f6fb",
    },
}
LAYER_ORDER = {key: index for index, key in enumerate(LAYER_CONFIG)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export KMZ layers to a standalone Leaflet map")
    parser.add_argument("--kmz-dir", default="kmz_layers", type=Path, help="KMZ files directory")
    parser.add_argument("--output-dir", default="map", type=Path, help="Output directory")
    parser.add_argument("--title", default="Supernatural Slovakia", help="Map title")
    parser.add_argument(
        "--border-shapefile",
        default=DEFAULT_BORDER_SHP,
        type=Path,
        help="Optional shapefile used for the hatched country mask",
    )
    return parser.parse_args()


def normalize_layer_key(value: str) -> str:
    collapsed = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_")
    return collapsed.upper() or "LAYER"


def text_value(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    text = "".join(element.itertext()).strip()
    return text or None


def parse_point_coordinates(raw: str) -> list[float] | None:
    tokens = raw.strip().split()
    if not tokens:
        return None
    parts = tokens[0].split(",")
    if len(parts) < 2:
        return None
    return [float(parts[1]), float(parts[0])]  # [lat, lon]


BR_RE = re.compile(r"<\s*br\s*/?\s*>", flags=re.IGNORECASE)
P_RE = re.compile(r"<\s*/?\s*p\b[^>]*>", flags=re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


def sanitise_description(value: str) -> str:
    if not value:
        return ""

    text = html.unescape(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = BR_RE.sub("\n\n", text)
    text = P_RE.sub("\n\n", text)
    text = TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")

    cleaned_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if parts and len(parts[-1]) == 1 and len(" ".join(parts[:-1])) > 20:
        parts = parts[:-1]

    return "\n\n".join(parts)


def load_kmz_layer(kmz_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(kmz_path) as archive:
        kml_name = next((n for n in archive.namelist() if n.lower().endswith(".kml")), None)
        if not kml_name:
            raise ValueError(f"{kmz_path} contains no KML")
        root = ET.fromstring(archive.read(kml_name))

    doc_name = root.findtext(".//kml:Document/kml:name", namespaces=KML_NS) or kmz_path.stem
    layer_key = normalize_layer_key(doc_name)

    features = []
    for placemark in root.findall(".//kml:Placemark", KML_NS):
        coords = text_value(placemark.find(".//kml:Point/kml:coordinates", KML_NS))
        if not coords:
            continue
        point = parse_point_coordinates(coords)
        if not point:
            continue

        name = text_value(placemark.find("kml:name", KML_NS)) or "Untitled"
        desc = text_value(placemark.find("kml:description", KML_NS)) or ""
        features.append(
            {
                "name": name,
                "description": sanitise_description(desc),
                "coordinates": point,
            }
        )

    return {"key": layer_key, "label": doc_name, "features": features}


def svg_data_uri(color: str) -> str:
    svg = textwrap.dedent(
        f"""\
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
          <circle cx="24" cy="24" r="15" fill="{color}" fill-opacity="0.18" stroke="white" stroke-width="2"/>
          <circle cx="24" cy="24" r="7.5" fill="{color}" stroke="white" stroke-width="2"/>
        </svg>
        """
    ).strip()
    from urllib.parse import quote
    return "data:image/svg+xml;charset=UTF-8," + quote(svg)


def resolve_icon_url(project_root: Path, output_dir: Path, layer_key: str) -> str:
    config = LAYER_CONFIG.get(layer_key, {})
    icon_source = config.get("icon_source")
    if icon_source:
        source = project_root / icon_source
        if source.exists():
            return Path(__import__("os").path.relpath(source, output_dir)).as_posix()
    return svg_data_uri(config.get("color", "#43b7ff"))


def popup_html(name: str, description: str) -> str:
    if description:
        safe_desc = html.escape(description).replace("\n\n", "<br><br>").replace("\n", "<br>")
    else:
        safe_desc = '<em style="opacity:0.6">No description available.</em>'
    return (
        '<div class="popup-card">'
        f'<h3>{html.escape(name)}</h3>'
        f'<p>{safe_desc}</p>'
        '</div>'
    )


def load_border_geojson(border_shapefile: Path | None) -> dict[str, Any] | None:
    if not border_shapefile:
        return None
    if not border_shapefile.exists():
        warnings.warn(f"Border shapefile not found, skipping mask layer: {border_shapefile}")
        return None

    gdf = gpd.read_file(border_shapefile)
    if "CNTR_CODE" not in gdf.columns or "LEVL_CODE" not in gdf.columns:
        warnings.warn("Border shapefile missing CNTR_CODE and/or LEVL_CODE; skipping mask layer")
        return None

    gdf = gdf[(gdf["CNTR_CODE"] != "SK") & (gdf["LEVL_CODE"] == 0)].copy()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    if gdf.empty:
        warnings.warn("Border shapefile filter returned no rows; skipping mask layer")
        return None

    if gdf.crs is None:
        warnings.warn("Border shapefile has no CRS; assuming EPSG:4326")
        gdf = gdf.set_crs("EPSG:4326")
    elif str(gdf.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
        gdf = gdf.to_crs("EPSG:4326")

    return json.loads(gdf.to_json())


def build_html(
    map_title: str,
    layers: list[dict[str, Any]],
    center: list[float],
    zoom: int,
    border_geojson: dict[str, Any] | None,
) -> str:
    layers_json = json.dumps(layers, ensure_ascii=False)
    border_json = json.dumps(border_geojson, ensure_ascii=False) if border_geojson else "null"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(map_title)}</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  >
  <style>
    html, body {{ height: 100%; margin: 0; background: #0b1018; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    #map {{ width: 100%; height: 100vh; background: #0b1018; }}

    .map-title {{
      position: fixed;
      top: 14px;
      left: 58px;
      z-index: 1000;
      background: rgba(10, 14, 20, 0.92);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 14px;
      padding: 10px 16px;
      color: #f5f7fb;
      font-size: 1.05rem;
      font-weight: 600;
      box-shadow: 0 18px 48px rgba(0,0,0,0.35);
      backdrop-filter: blur(10px);
    }}

    .leaflet-popup-content-wrapper, .leaflet-popup-tip {{
      background: rgba(11, 16, 24, 0.96) !important;
      color: #f5f7fb !important;
      border-radius: 14px !important;
      box-shadow: 0 18px 48px rgba(0,0,0,0.35) !important;
    }}

    .leaflet-popup-content {{ margin: 14px 16px !important; }}
    .leaflet-container a.leaflet-popup-close-button {{ color: #f5f7fb !important; }}

    .popup-card h3 {{
      margin: 0 0 8px 0;
      font-size: 1rem;
      color: #f5f7fb;
    }}
    .popup-card p {{
      margin: 0;
      font-size: 0.9rem;
      line-height: 1.5;
      color: #d7deea;
      white-space: normal;
    }}

    .leaflet-control-layers {{
      background: rgba(10, 14, 20, 0.92) !important;
      border: 1px solid rgba(255,255,255,0.14) !important;
      border-radius: 16px !important;
      color: #f5f7fb !important;
      box-shadow: 0 18px 48px rgba(0,0,0,0.35) !important;
      backdrop-filter: blur(10px);
    }}
    .leaflet-control-layers-expanded {{ padding: 12px 14px !important; }}
    .leaflet-control-layers label {{ color: #f5f7fb !important; }}

    .leaflet-control-zoom {{
      border: 1px solid rgba(255,255,255,0.14) !important;
      border-radius: 16px !important;
      overflow: hidden;
      box-shadow: 0 18px 48px rgba(0,0,0,0.35) !important;
    }}
    .leaflet-control-zoom a {{
      background: rgba(10, 14, 20, 0.92) !important;
      color: #f5f7fb !important;
      width: 38px !important;
      height: 38px !important;
      line-height: 38px !important;
      font-size: 1.25rem !important;
      border: 0 !important;
    }}
    .leaflet-control-zoom a:hover {{
      background: rgba(20, 29, 41, 0.96) !important;
    }}

    .kmz-marker-icon {{
      filter: drop-shadow(0 0 14px rgba(67, 183, 255, 0.32));
    }}
  </style>
</head>
<body>
  <div class="map-title">{html.escape(map_title)}</div>
  <div id="map"></div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script src="https://cdn.jsdelivr.net/npm/leaflet.pattern@0.1.0/dist/leaflet.pattern.js"></script>
  <script>
    const map = L.map('map', {{
      center: {json.dumps(center)},
      zoom: {zoom},
      zoomControl: true,
      preferCanvas: false
    }});

    map.createPane('maskPane');
    map.getPane('maskPane').style.zIndex = 350;
    map.createPane('markerPaneCustom');
    map.getPane('markerPaneCustom').style.zIndex = 650;

    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      subdomains: 'abcd',
      maxZoom: 20,
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
    }}).addTo(map);

    const layerPayload = {layers_json};
    const borderGeoJson = {border_json};
    const overlayMaps = {{}};
    const bounds = [];

    function makeIcon(iconUrl) {{
      return L.icon({{
        iconUrl,
        iconSize: [40, 40],
        iconAnchor: [20, 20],
        popupAnchor: [0, -18],
        className: 'kmz-marker-icon'
      }});
    }}

    if (borderGeoJson) {{
      const hatch = new L.StripePattern({{
        weight: 1,
        spaceWeight: 8,
        color: '#292929',
        opacity: 0.95,
        spaceOpacity: 0,
        angle: 45
      }});
      hatch.addTo(map);

      L.geoJSON(borderGeoJson, {{
        pane: 'maskPane',
        interactive: false,
        style: function() {{
          return {{
            color: '#9b9b9b',
            weight: 1,
            opacity: 1,
            fillPattern: hatch,
            fillOpacity: 1
          }};
        }}
      }}).addTo(map);
    }}

    for (const layer of layerPayload) {{
      const group = L.layerGroup();
      for (const feature of layer.features) {{
        const marker = L.marker(feature.coordinates, {{ icon: makeIcon(layer.icon_url), pane: 'markerPaneCustom' }});
        marker.bindPopup(feature.popup_html, {{ maxWidth: 340 }});
        marker.bindTooltip(feature.name, {{ direction: 'top' }});
        marker.addTo(group);
        bounds.push(feature.coordinates);
      }}
      overlayMaps[`${{layer.label}} (${{layer.features.length}})`] = group;
      if (layer.features.length) {{
        group.addTo(map);
      }}
    }}

    L.control.layers(null, overlayMaps, {{ collapsed: false, position: 'topright' }}).addTo(map);

    if (bounds.length) {{
      map.fitBounds(bounds, {{ padding: [36, 36] }});
    }}
  </script>
</body>
</html>
"""


def create_map(
    layers: list[dict[str, Any]],
    title: str,
    project_root: Path,
    output_dir: Path,
    border_shapefile: Path | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    all_coords = [f["coordinates"] for layer in layers for f in layer["features"]]
    center = DEFAULT_CENTER
    if all_coords:
        center = [
            sum(c[0] for c in all_coords) / len(all_coords),
            sum(c[1] for c in all_coords) / len(all_coords),
        ]

    export_layers: list[dict[str, Any]] = []
    for layer in sorted(layers, key=lambda x: (LAYER_ORDER.get(x["key"], 999), x["label"])):
        if not layer["features"]:
            continue

        icon_url = resolve_icon_url(project_root, output_dir, layer["key"])
        export_layers.append(
            {
                "key": layer["key"],
                "label": layer["label"],
                "icon_url": icon_url,
                "features": [
                    {
                        "name": feature["name"],
                        "coordinates": feature["coordinates"],
                        "popup_html": popup_html(feature["name"], feature["description"]),
                    }
                    for feature in layer["features"]
                ],
            }
        )

    border_geojson = load_border_geojson(border_shapefile)
    html_content = build_html(title, export_layers, center, DEFAULT_ZOOM, border_geojson)
    output_path = output_dir / "index.html"
    output_path.write_text(html_content, encoding="utf-8")

    total = sum(len(layer["features"]) for layer in export_layers)
    print(f"Exported {len(export_layers)} layers with {total} points to {output_path}")
    return output_path


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    kmz_root = (project_root / args.kmz_dir).resolve()
    output_dir = (project_root / args.output_dir).resolve()

    if not kmz_root.exists():
        raise FileNotFoundError(f"KMZ directory not found: {kmz_root}")

    kmz_files = sorted(kmz_root.glob("*.kmz"))
    if not kmz_files:
        raise FileNotFoundError(f"No KMZ files found in: {kmz_root}")

    layers = [load_kmz_layer(f) for f in kmz_files]
    create_map(layers, args.title, project_root, output_dir, args.border_shapefile)


if __name__ == "__main__":
    main()
