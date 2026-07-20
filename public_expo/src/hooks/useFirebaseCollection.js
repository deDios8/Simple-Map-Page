import { useEffect, useRef, useState } from "react";
import { onValue, ref } from "firebase/database";
import { database, dbPath } from "../firebase";

// Subscribes to `{sessionName}/{node}` and keeps normalized data in state.
// Re-subscribes whenever sessionName or node changes. When `listenerActive`
// is false the subscription stays open (matching the prototype's "pause db"
// behavior) but incoming snapshots are ignored instead of updating state.
export function useFirebaseCollection(sessionName, node, normalize, listenerActive) {
  const [data, setData] = useState({});
  const listenerActiveRef = useRef(listenerActive);

  useEffect(() => {
    listenerActiveRef.current = listenerActive;
  }, [listenerActive]);

  useEffect(() => {
    setData({});
    const collectionRef = ref(database, dbPath(sessionName, node));
    const unsubscribe = onValue(collectionRef, (snapshot) => {
      if (!listenerActiveRef.current) return;
      setData(normalize(snapshot.val()));
    });
    return () => unsubscribe();
  }, [sessionName, node, normalize]);

  return [data, setData];
}
