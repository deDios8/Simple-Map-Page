# TODO
can't create a new session - no geojson object is created

# Instructions for deployment

Project Console: 
https://console.firebase.google.com/project/geogm-simple-map/overview
Remote Hosting URL: 
firebase deploy
https://geogm-simple-map.web.app
Local Test:
cd "c:\Users\dedio\OneDrive\Documents\Programming\python\Simple Map Page\public"
python -m http.server 8080
http://localhost:8080/index.html

# Simple Map Page

This page is a mobile-friendly Leaflet map that:

- centers on the user's GPS location when permission is granted
- renders GeoJSON points and rectangular polygon zones
- hides any feature whose `properties.visible` value is `false`
- colors each visible feature using `properties.color`
- shows additional `properties.description` and `properties.extraData` values when the feature is tapped
- opens a bottom-right drawer with a list of all GeoJSON objects and an editor for basic properties
- listens to Firebase Realtime Database updates when configuration is supplied

## GeoJSON shape

Each entry is expected to look like this:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-122.4194, 37.7749]
  },
  "properties": {
    "id": "example-id",
    "name": "Example point",
    "visible": true,
    "color": "#0b8f87",
    "description": "Visible in the popup",
    "extraData": {
      "priority": "high"
    }
  }
}
```

Rectangular zones should use GeoJSON `Polygon` geometry with 5 coordinate pairs that close the rectangle.

## Firebase setup

1. Edit `app.js` and fill in the `firebaseConfig` object.
2. Make sure `firebaseCollectionPath` points to the collection/path that stores your feature entries.
3. Store your data under that path as either:
   - an object keyed by feature id
   - an array of GeoJSON features

If the Firebase config is left blank, the page runs with demo data instead.

## Running locally

For mobile GPS access, do not open the page directly as `file://...`.

Serve it over `http://localhost` for desktop testing or over HTTPS when opening it on a phone.

## Single-file embed

Use `embed.html` when you need this map app as a single embeddable file.

Example iframe:

```html
<iframe
  src="https://your-domain.example/map/embed.html"
  title="Simple Map"
  width="100%"
  height="700"
  style="border:0;"
  loading="lazy"
  allow="geolocation"
  referrerpolicy="no-referrer"
></iframe>
```

Notes:

- Keep `allow="geolocation"` on the iframe or browser location access will be blocked.
- Host over HTTPS for real GPS support on mobile browsers.
- Edit Firebase values inside `embed.html` if you want live sync from Realtime Database.




Prompt used to generate:
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
* Geometry
* ID
* Timestamp
* Requester
* Type
* Details

## GEOOBJ
* Geometry
* ID
* Name
* Appearance
  * Visible (tappable, etc)
  * Radius
  * Color-Border
  * Color-Fill
  * Transparency
* Stats
* Statuses


# Event Structure
## SUSPECT 
### check all geoObjects for suspects
* an ID
* of any TYPE
* having all or any STATUSES
* all STAT_THRESHOLDS

## TRIGGER
### has is_trigger component 
### check all suspects for triggers and mark as targets
* any WITHIN/ENTERED/EXITED, 
* any TYPES, 
* any IDs,
* all STATUSES,
* any/all STAT_THRESHOLDS

## TARGET
### apply result
* STAT name incrememt/decrement/setpoint
* add/remove/toggle STATUSES
* change radius, color, hidden



find all SUSPECTS and tag them SUSPECT (and suspect_checker)
check all SUSPECTS for TRIGGERS and tag them TARGETTED (and name of trigger)
check all TARGETS and apply RESULTS
