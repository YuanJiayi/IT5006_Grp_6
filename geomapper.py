import json

import folium
from map_layers.order_density import add_order_density_layer #Add new layers to map like this
from map_layers.seller_density import add_seller_density_layer
from map_layers.seller_buyer_routes import add_seller_buyer_routes_layer
from map_layers.state_order_density import add_state_order_density_layer

with open("data/brazil_boundary.geojson", encoding="utf-8") as boundary_file:
    brazil_boundary = json.load(boundary_file)
with open("data/brazil_states.geojson", encoding="utf-8") as states_file:
    brazil_states = json.load(states_file)

# Keep the initial view and panning focused on Brazil.
brazil_bounds = [[-33.75, -73.99], [5.27, -34.79]]
brazil_map = folium.Map(
    location=[-14.2, -51.9],
    zoom_start=4.5,
    min_zoom=4,
    max_bounds=True,
    tiles="OpenStreetMap",
    control_scale=True
)

folium.GeoJson(
    brazil_boundary,
    control=False,
    style_function=lambda feature: {
        "color": "#4a4a4a",
        "weight": 1.5,
        "fillColor": "#f5f5f5",
        "fillOpacity": 0.08
    }
).add_to(brazil_map)

folium.GeoJson(
    brazil_states,
    control=False,
    style_function=lambda feature: {
        "color": "#374151",
        "weight": 1.1,
        "fillOpacity": 0
    },
    tooltip=folium.GeoJsonTooltip(fields=["name", "sigla"], aliases=["State", "Code"])
).add_to(brazil_map)

# Calculated metrics are an independent overlay layer.
add_order_density_layer(brazil_map)
add_seller_density_layer(brazil_map)
add_seller_buyer_routes_layer(brazil_map)
add_state_order_density_layer(brazil_map)

folium.LayerControl(collapsed=False).add_to(brazil_map)

# Fit the map to Brazil rather than only the order locations.
brazil_map.fit_bounds(brazil_bounds)

brazil_map.save("brazil_order_density_map.html")
print("Saved map to brazil_order_density_map.html")


# The Streamlit can probably use the Folium object directly rather than rely on the html.
# We can keep adding layers to this same map so thats nice lol