# TODO
- Make the dropdown options for CRITERIA_COMPONENT_OPTIONS and RESULT_COMPONENT_OPTIONS and updateLocationIntervalHz and 0.1.032 be contained on the server
* Bulk move option for anchor point for session to relocate entire games
  - Each game needs an invisible reference point
  - That referecent point can contain settings like:
    - Update interval (in seconds with a minimum of 0.2?)
    - Moving reference point moves all zones the same amount (haversine?)
      - Could lead to relative distance based coords rather than lat/long
    - Cannot be modified: Name=reference, opacity=0, clickable=false
    - Not be clickable on the map
    - stacked at the lowest level of visibility (z-dir)
- Stat editor for drop-down stat addition.
* Allow triggers to assign targets reflexively targeting the zone the triggered
- setBorder needs to change to setBorderColor
- add setBorderDash

* App auto-select a newly added zone, criteria, event for editing.
- Add an event clock/timer
  - Tuning the timing of events to have a predictable tick rate for DOT-like effects names
- hasTags isn't noticing a Stat name
- First entered seemed to be per-zone rather than per-tag
- No event triggers for stats


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