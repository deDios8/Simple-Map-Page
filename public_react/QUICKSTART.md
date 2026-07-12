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
