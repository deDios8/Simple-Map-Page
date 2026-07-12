import { initializeApp } from 'firebase/app';
import { getDatabase } from 'firebase/database';

let firebaseApp = null;
let database = null;

export async function initializeFirebase() {
  try {
    const response = await fetch('/online_config.json');
    const config = await response.json();
    
    firebaseApp = initializeApp(config.firebase);
    database = getDatabase(firebaseApp);
    
    return { database, config };
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
