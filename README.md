# Dependencies
python -m pip install esper
python -m pip install pyproj
python -m pip install shapely


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

# GeoJSON shape
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


