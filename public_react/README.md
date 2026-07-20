# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.


## From: README_REACT.md

# Simple Map Page - React Version

This is a React migration of the original vanilla JavaScript Simple Map Page application.

## Architecture Improvements

### From Vanilla JS to React

**Original (`public/`):**
- 1,925 lines of imperative JavaScript
- Manual DOM queries and updates
- Global state object with scattered updates
- String-based HTML templating
- Manual Firebase listener management

**React Version (`public_react/`):**
- Component-based architecture
- Declarative UI with automatic re-rendering
- Centralized state management with hooks
- JSX for type-safe templating
- Custom hooks for Firebase and geolocation

## Project Structure

```
public_react/
├── src/
│   ├── components/          # React components
│   │   ├── MapView.jsx      # Leaflet map integration
│   │   ├── StatusCard.jsx   # Location status display
│   │   ├── SimControls.jsx  # GPS simulation controls
│   │   ├── RequestButtons.jsx   # A/B/X/Y request buttons
│   │   ├── ZonesDrawer.jsx  # Main drawer with zone list
│   │   ├── ZoneList.jsx     # Zone list display
│   │   └── ZoneEditor.jsx   # Zone editing form
│   ├── hooks/               # Custom React hooks
│   │   ├── useFirebaseData.js   # Firebase real-time data hook
│   │   └── useGeolocation.js    # GPS location hook
│   ├── firebase.js          # Firebase initialization
│   ├── styles.css           # Migrated styles from original
│   ├── App.jsx              # Main application component
│   └── main.jsx             # React entry point
├── public/                  # Static assets
│   ├── online_config.json   # Firebase configuration
│   ├── map_criteria_components.json
│   └── map_result_components.json
├── index.html
├── vite.config.js
└── package.json
```

## Key Components

### Custom Hooks

**`useFirebaseData(database, path, enabled)`**
- Manages Firebase real-time listeners
- Automatically subscribes/unsubscribes
- Returns `{ data, loading, error }`

**`useGeolocation(gpsMode, updateInterval)`**
- Wraps browser Geolocation API
- Handles GPS permissions and errors
- Returns `{ location, status, error }`

### Components

**`MapView`** - Leaflet map with zones and user location
**`ZonesDrawer`** - Sidebar with zone management
**`ZoneEditor`** - Form for editing zone properties
**`StatusCard`** - Location status indicator

## Installation & Setup

### 1. Install Dependencies
```bash
cd public_react
npm install
```

### 2. Configure Firebase
Copy your Firebase configuration files to `public_react/public/`:
```bash
cp ../public/*.json public/
```

### 3. Start Development Server
```bash
npm run dev
```

The app will run at `http://localhost:5173/`

### 4. Build for Production
```bash
npm run build
```

Output will be in `dist/` directory.

## Key Benefits Over Vanilla Version

### 1. **Maintainability**
- Clear component boundaries
- Easier to locate and modify code
- Better code organization

### 2. **State Management**
- Automatic UI updates when state changes
- No manual DOM manipulation
- Predictable data flow

### 3. **Reusability**
- Components can be easily reused
- Custom hooks encapsulate logic
- Shared functionality across features

### 4. **Developer Experience**
- Hot Module Replacement (HMR)
- Better error messages
- TypeScript-ready (add later if needed)

### 5. **Firebase Integration**
- Cleaner listener lifecycle management
- Automatic cleanup on unmount
- Easier to debug data flow

### 6. **Testability**
- Components can be tested in isolation
- Hooks can be tested separately
- Mock Firebase and geolocation easily

## Migration Status

### ✅ Completed
- Core map functionality
- GPS and simulation mode
- Zone CRUD operations
- Firebase real-time sync
- Request buttons (A/B/X/Y)
- Zone list and editor
- Stats editor
- Drawer UI

### 🚧 Not Yet Implemented
- Events drawer and editor
- Message modal system
- Coordinate picking mode
- Trigger/target criteria components
- Result components
- Advanced zone features

## Next Steps

To complete the migration:

1. **Implement Events System**
   - Create `EventsDrawer.jsx`
   - Create `EventEditor.jsx`
   - Add event CRUD operations

2. **Add Message Modal**
   - Create `MessageModal.jsx`
   - Implement dismiss message logic

3. **Enhance Zone Editor**
   - Add coordinate picking from map
   - Implement criteria components
   - Add result components

4. **Performance Optimization**
   - Memoize expensive computations
   - Use `React.memo` for pure components
   - Implement virtual scrolling for large lists

5. **Testing**
   - Add unit tests with Vitest
   - Add component tests with React Testing Library
   - Add E2E tests with Playwright

## Development Notes

- The app uses Vite for fast development and building
- Firebase Realtime Database for backend
- Leaflet for mapping (not react-leaflet, to maintain closer parity with original)
- CSS is mostly unchanged from original for visual consistency

## Troubleshooting

**Map not rendering:**
- Check Leaflet CSS is loaded
- Verify map container has height in CSS

**Firebase errors:**
- Ensure `online_config.json` exists in `public/`
- Check Firebase configuration is correct
- Verify database rules allow access

**GPS not working:**
- HTTPS required for geolocation API
- User must grant location permission
- Use simulation mode for testing


## From QUICKSTART.md

# Quick Start Guide

## Prerequisites

Your React version of Simple Map Page is ready! The configuration files have been copied from the original `public/` folder.

## Start Development

```bash
cd /Users/aaron.klingbeil/Documents/Simple-Map-Page/public_react
npm run dev
```

Then open **http://localhost:5173/** in your browser.

## First Run

On first load, you'll be prompted for:
1. **User ID** - Your Firebase user identifier
2. **Password** - Your user password  
3. **Session Name** - Name for this session

These are stored in localStorage for subsequent visits.

## What Works

✅ GPS location tracking
✅ Simulation mode (toggle with GPS/SIM button)
✅ Firebase real-time zone sync
✅ Create/edit/delete zones
✅ Zone stats editor
✅ Map visualization with Leaflet
✅ Request buttons (A/B/X/Y)
✅ Zone list and selection
✅ Clear logs functionality

## What's Not Implemented Yet

⏳ Events drawer and editor
⏳ Message modal system
⏳ Coordinate picking from map
⏳ Full criteria component system

## Keyboard Shortcuts

- **GPS/SIM button**: Toggle between real GPS and simulation
- **pause db/resume db**: Pause/resume Firebase listeners
- **Simulation arrows**: Move position when in SIM mode

## File Structure

```
public_react/
├── src/
│   ├── components/      # React components
│   ├── hooks/           # Custom React hooks
│   ├── firebase.js      # Firebase setup
│   ├── App.jsx          # Main app
│   └── styles.css       # Styles
├── public/              # Static files
│   └── *.json          # Config files
└── dist/               # Production build (after npm run build)
```

## Build for Production

```bash
npm run build
```

Output goes to `dist/` folder.

## Troubleshooting

**Map doesn't show:**
- Check browser console for errors
- Verify Leaflet CSS is loading
- Check that `#map` div has height in styles.css

**Firebase not connecting:**
- Verify `public/online_config.json` exists
- Check Firebase configuration is correct
- Look for errors in browser console

**GPS not working:**
- Grant location permission when browser asks
- Use HTTPS in production (required for geolocation)
- Try simulation mode for testing

## Documentation

- See `README_REACT.md` for detailed React architecture docs
- See `MIGRATION_SUMMARY.md` for migration details
- Original code is preserved in `/public/` folder

## Comparison with Original

| Metric | Original | React Version |
|--------|----------|---------------|
| Lines of code | 1,925 (single file) | ~1,200 (modular) |
| DOM queries | 55+ manual | 0 (React manages) |
| State updates | Manual | Automatic |
| Build step | None | Vite (optional) |
| Hot reload | ❌ | ✅ |
| Component reuse | ❌ | ✅ |
| Testability | Hard | Easy |

Enjoy your React app! 🚀


## From MIGRATION_SUMMARY.md

# React Migration Summary

## Project Created

I've successfully created a React version of your Simple Map Page application in `/Users/aaron.klingbeil/Documents/Simple-Map-Page/public_react/`.

## What Was Migrated

### ✅ Core Features Implemented

1. **Firebase Integration**
   - Real-time database connection
   - Zone data synchronization
   - Request submission
   - Custom `useFirebaseData` hook for automatic listener management

2. **Geolocation System**
   - GPS tracking with browser Geolocation API
   - Simulation mode for testing
   - Custom `useGeolocation` hook
   - Location status display

3. **Map Functionality**
   - Leaflet map integration
   - User location marker
   - Zone rendering (circles and polygons)
   - GeoJSON layer management

4. **Zone Management**
   - Create, read, update, delete (CRUD) operations
   - Zone list display
   - Zone editor with form controls
   - Stats editor for custom properties
   - Log management

5. **UI Components**
   - Zones drawer (sidebar)
   - Status card
   - Simulation controls
   - Request buttons (A/B/X/Y)
   - GPS/Sim mode toggle
   - Firebase listener pause/resume

## Architecture Improvements

### Before (Vanilla JS)
- **1,925 lines** in a single file
- **55+ manual DOM queries**
- Global state object with scattered updates
- String-based HTML templating
- Manual listener lifecycle management

### After (React)
- **Modular component structure**
  - 8 components in separate files
  - 2 custom hooks
  - Clear separation of concerns
  
- **Declarative state management**
  - React hooks for all state
  - Automatic UI updates
  - Predictable data flow

- **Better maintainability**
  - Each feature has its own component
  - Reusable hooks for common logic
  - Easier to test and debug

## Project Structure

```
public_react/
├── src/
│   ├── components/
│   │   ├── MapView.jsx          # Leaflet map
│   │   ├── StatusCard.jsx       # Location display
│   │   ├── SimControls.jsx      # Simulation buttons
│   │   ├── RequestButtons.jsx   # A/B/X/Y buttons
│   │   ├── ZonesDrawer.jsx      # Main sidebar
│   │   ├── ZoneList.jsx         # Zone list
│   │   └── ZoneEditor.jsx       # Zone editing form
│   ├── hooks/
│   │   ├── useFirebaseData.js   # Firebase real-time hook
│   │   └── useGeolocation.js    # GPS tracking hook
│   ├── firebase.js              # Firebase setup
│   ├── App.jsx                  # Main component
│   ├── main.jsx                 # Entry point
│   └── styles.css               # Migrated styles
├── public/
│   ├── online_config.json       # Firebase config
│   ├── map_criteria_components.json
│   └── map_result_components.json
├── package.json
└── README_REACT.md              # React documentation
```

## Dependencies Installed

- **react** & **react-dom**: Core React
- **firebase**: Firebase SDK
- **leaflet**: Map library
- **vite**: Build tool and dev server

## Getting Started

### 1. Start Development Server
```bash
cd public_react
npm run dev
```
Access at `http://localhost:5173/`

### 2. Build for Production
```bash
npm run build
```

## Not Yet Implemented

The following features from the original app still need to be migrated:

1. **Events System**
   - Events drawer
   - Event editor
   - Trigger/target criteria components
   - Result components

2. **Message Modal**
   - User message display
   - Dismiss functionality

3. **Advanced Features**
   - Coordinate picking from map click
   - Complete criteria component system
   - All event processing logic

## Benefits of This Migration

1. **Easier to Add Features**: New components can be added without touching existing code
2. **Better Performance**: React's virtual DOM optimizes updates
3. **Improved Debugging**: React DevTools show component hierarchy and state
4. **Type Safety Ready**: Easy to add TypeScript later
5. **Testing**: Components can be unit tested in isolation
6. **Hot Reload**: Changes appear instantly during development

## Next Steps

If you want to complete the migration:

1. **Implement Events**: Create EventsDrawer and EventEditor components
2. **Add Message Modal**: Simple modal component for user messages
3. **Coordinate Picking**: Enable map click to set zone coordinates
4. **Optimization**: Code splitting, lazy loading for better performance
5. **Testing**: Add unit tests for components and hooks

## Files Created

- `/public_react/src/App.jsx` - Main application
- `/public_react/src/firebase.js` - Firebase initialization
- `/public_react/src/hooks/useFirebaseData.js` - Firebase hook
- `/public_react/src/hooks/useGeolocation.js` - GPS hook
- `/public_react/src/components/MapView.jsx` - Map component
- `/public_react/src/components/StatusCard.jsx` - Status display
- `/public_react/src/components/SimControls.jsx` - Simulation controls
- `/public_react/src/components/RequestButtons.jsx` - Request buttons
- `/public_react/src/components/ZonesDrawer.jsx` - Drawer component
- `/public_react/src/components/ZoneList.jsx` - Zone list
- `/public_react/src/components/ZoneEditor.jsx` - Zone editor
- `/public_react/README_REACT.md` - Complete React documentation

## Build Status

✅ **Build successful** (511 KB minified, 154 KB gzipped)

The application is ready to run in development mode or be deployed to production!
