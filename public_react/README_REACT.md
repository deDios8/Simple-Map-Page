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
