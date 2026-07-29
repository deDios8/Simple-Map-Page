# TODO
- Make the dropdown options for CRITERIA_COMPONENT_OPTIONS and RESULT_COMPONENT_OPTIONS and updateLocationIntervalHz and 0.1.032 be contained on the server
- Bulk move option for anchor point for session to relocate entire games
- Stat editor for drop-down stat addition.
* Allow triggers to assign targets reflexively targeting the zone the triggered

* App auto-select a newly added zone, criteria, event for editing.
- Add an event clock/timer
  - Tuning the timing of events to have a predictable tick rate for DOT-like effects names
- hasTags isn't noticing a Stat name
- First entered seemed to be per-zone rather than per-tag
- No event triggers for stats
- 

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

npm expo (can't remember exact commands to add)


# Old instructions for deployment
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

## New Expo Local Test:
npx expo start --web
## Expo GitHub Pages Deploy:
cd public_expo && npm run deploy
# Note for bad cached on gh-pages:
If you ever see the same fatal: a branch named 'gh-pages' already exists error again, the fix is identical: delete public_expo/node_modules/.cache/gh-pages and rerun npm run deploy.

Save should become primary whenever something changes on the editor, but should otherwise start out looking like cancel.