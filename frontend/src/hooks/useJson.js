import { useEffect, useState } from 'react';

export default function useJson(path) {
  const [state, setState] = useState({ data: null, loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    fetch(path)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status} при загрузке ${path}`);
        }
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ data: null, loading: false, error: err.message });
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  return state;
}