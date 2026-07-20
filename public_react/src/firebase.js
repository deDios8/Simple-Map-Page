import { initializeApp } from 'firebase/app';
import { getDatabase } from 'firebase/database';

let firebaseApp = null;
let database = null;

export async function initializeFirebase() {
  try {
    const response = await fetch('/online_config.json');
    const config = await response.json();
    
    // Firebase config is at root level in online_config.json
    const firebaseConfig = {
      apiKey: config.apiKey,
      authDomain: config.authDomain,
      databaseURL: config.databaseURL,
      projectId: config.projectId,
      storageBucket: config.storageBucket,
      messagingSenderId: config.messagingSenderId,
      appId: config.appId,
    };
    
    firebaseApp = initializeApp(firebaseConfig);
    database = getDatabase(firebaseApp);
    
    // Return database and processed config
    return { 
      database, 
      config: {
        ...config,
        firebaseZoneNode: config.nodes?.zones || 'zones',
        firebaseClientRequestNode: config.nodes?.clientRequests || 'zzz_clientRequests',
        firebaseEventsNode: config.nodes?.events || 'events',
        mapLayer: config.mapLayer?.default?.url || '',
        mapLayerAttribution: config.mapLayer?.default?.attribution || '',
        updateLocationInterval: config.updateLocationInterval || 0,
      }
    };
  } catch (error) {
    console.error('Failed to initialize Firebase:', error);
    throw error;
  }
}

export function getFirebaseDatabase() {
  return database;
}

export function getFirebasePath(node, config) {
  const { userId, sessionName } = config;
  return `${node}/${userId}/${sessionName}`;
}
