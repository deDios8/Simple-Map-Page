Move lat/long button down
Stop rezooming when an menu item is selected
Rename appearance row and coordinates row


# Instructions for deployment
## Project Console: 
https://console.firebase.google.com/project/geogm-simple-map/overview
## Remote Hosting URL: 
firebase deploy
https://geogm-simple-map.web.app
## Local Test:
cd "c:\Users\dedio\OneDrive\Documents\Programming\python\Simple Map Page\public"
python -m http.server 8080
http://localhost:8080/index.html


## GeoJSON shape



# Prompt used to generate:
Make a simple webpage that displays a leaflet map centered on the user's location. The map should display geojson objects as points and rectangular zones. A geojson object should only be made visible if a boolean visibility flag within the geojson entry is true. The color of a zone should be displayed based on an entry within the geojson object. Tapping a visible geojson object should bring up additional data stored in that geojson entry.
The page should have a hamburger style collapsible button in the bottom right corner that allows the user to see a list of all geojson objects and tap on them there to edit their properties. Their font color in the menu should be based on same color entry that determines their display color on the map.
The page should have listener for a firebase realtime database that will update the map when a change occurs.
The page should be well suited on mobile devices using their gps location.

THEN

I'd like to add a new functionality to this app.
I'd like to have the user enter an identifying string when they first access the site. Then add a geojson Point object  with the inputed id, at the users gps coordinates, and with a black color.
Then, while visiting the page, every 2 seconds, I'd like to update that geojson object's coordinates with the user's coordinates, and leave the rest of the geojson objects data unchanged. 



# Object Structure
## Client Request
{
type = "Feature", 
geometry = {
  coordinates = [0,0],
  type = "Point"
},
properties = {
  id = "same as key",
  clientRequestPayload = {
    timestamp = 0,
    requesterId = "",
    requestType = "",
    requestedAction "",
  }
}
}

## GEOOBJ
{
type = "Feature", 
geometry = {
  coordinates = [0,0],
  type = "Point"
  },
properties = {
  id = "same as key",
  isUser or isZone = True,
  metaData = {
    zoneType = "",
    displayName = "",
    displayDescription = "",
  },
  appearance = {
    visible = true,
    radius = 0,
    colorBorder = #000000,
    colorFill = #000000,
    transparency = .5
  },
  stats = {},
  statuses = {}
}
}


# Default Statuses
* seeing
* user
