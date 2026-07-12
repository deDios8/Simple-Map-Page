import { useState, useEffect } from 'react';
import { ref, onValue, off } from 'firebase/database';

export function useFirebaseData(database, path, enabled = true) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!database || !path || !enabled) {
      setLoading(false);
      return;
    }

    setLoading(true);
    const dataRef = ref(database, path);

    const unsubscribe = onValue(
      dataRef,
      (snapshot) => {
        setData(snapshot.val());
        setLoading(false);
        setError(null);
      },
      (err) => {
        console.error('Firebase data error:', err);
        setError(err);
        setLoading(false);
      }
    );

    return () => {
      off(dataRef);
      unsubscribe();
    };
  }, [database, path, enabled]);

  return { data, loading, error };
}
