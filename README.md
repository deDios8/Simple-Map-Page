# TODO
- Make the dropdowns for CRITERIA_COMPONENT_OPTIONS and RESULT_COMPONENT_OPTIONS and updateLocationInterval and 0.1.032 be contained on the server
- Allow triggers to assign targets reflexively targeting the zone the triggered

- Wishlist: would like a way to move a user using keybindings on pc (overriding gps)
- App auto-select a newly added zone, criteria, event for editing.
- Add an event clock/timer
  - Tuning the timing of events to have a predictable tick rate for DOT-like effects
- Bulk move option for anchor point for session to relocate entire games
- Slow down tick rate for server event processing and separate that from db_updates
- Stat editor for drop-down stat addition.
- Test stat value checker triggers


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

