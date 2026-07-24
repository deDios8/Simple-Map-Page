import { useEffect, useState } from "react";
import { onValue, ref } from "firebase/database";
import { database, dbPath } from "../firebase";

// Subscribes to `{sessionName}/{node}` and keeps normalized data in state.
// Re-subscribes whenever sessionName or node changes.
export function useFirebaseCollection(sessionName, node, normalize) {
  const [data, setData] = useState({});

  useEffect(() => {
    setData({});
    const collectionRef = ref(database, dbPath(sessionName, node));
    const unsubscribe = onValue(collectionRef, (snapshot) => {
      setData(normalize(snapshot.val()));
    });
    return () => unsubscribe();
  }, [sessionName, node, normalize]);

  return [data, setData];
}
