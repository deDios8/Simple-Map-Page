# TODO
Make the dropdowns for CRITERIA_COMPONENT_OPTIONS and RESULT_COMPONENT_OPTIONS and updateLocationInterval and 0.1.032 be contained on the server
Allow triggers to assign targets reflexively targeting the object the triggered
Entering and exiting zones doesn't seem to work consistently.

debug console should display DisplayName rather than ID's
wishlist: would like a way to move a user on laptop (overriding gps)
stat editor for drop-down stat addition.
anchor point for session
reformat event editor
popup generator

# Dependencies
## macos
brew install python@3.13
brew install node
npm install -g firebase-tools
firebase login

python -m pip install esper
python -m pip install pyproj
python -m pip install shapely
or
.venv/bin/pip install esper
.venv/bin/pip install pyproj
.venv/bin/pip install shapely
.venv/bin/pip install firebase


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
## Server Virtual Environment:
python server/main.py

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
  metaData = {
    displayName = "",
    displayDescription = "",
  },
  appearance = {
    visible = [],
    radius = 0,
    colorBorder = #000000,
    colorFill = #000000,
    transparency = .5
  },
  stats = {},
  traits = []
}
}


AI prompt:
It's time for a major addition to both the front-end and back-end. 
The backend already contains #file:ecs_event_components.py that gives some structure and context for two new types of entities that will be added. The criteria entities will have components added to them, based on user design, that will be processed to identify geo object entities (identifiable by having an appearance component added to them) that match the criteria. Those processors will be built later. For now, I need the user to be able to create criteria entities and attach and unattach criteria components them. Every criteria will have components #sym:ObjectsThatMetAllCriteria and  #sym:ObjectsThatMetAnyCriteria , that the processors will add entities id's to that properly meet the criteria components attached to that criteria entity. Just like the entities in #file:ecs_geo_components.py , these constructed entities need to be mirrored onto the database, this time in a node called "eventCriteria".
The front end needs an additional menu drawer that functions similar to the existing object editor. The entry button should be in the top right and have a "E" showing on the button. Upon opening the menu, it should have a similar layout to the existing geo object editor, listing the criteria entities in the "eventCriteria" node, and when clicked, an editor form opens below. Similar buttons for adding an criteria entity at the top of the editor form, and buttons for saving and deleting the criteria entity at the bottom of the editor form. The same collapsability and persistance of collapsed states is also requested. Adding a criterion within a criteria should be displayed and function just like adding stats to a geo object. The row for a criterion should have a name, and a field to list (comma separated) the tags.
For now, the names of each criterion can just be user entered and stored in the database as entered. The backend will add components that match the entered criterion names and ignore others. We'll add entry validation later.
The #file:demo_event.json file gives my approximation of an example Criteria json structure would be.