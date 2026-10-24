import { useEffect, useState } from "react";
import { apiGet, type DataStatus } from "./api";

/** status=null while loading; offline=true if the backend is unreachable. */
export function useDataStatus() {
  const [state, setState] = useState<{ status: DataStatus | null; offline: boolean }>({ status: null, offline: false });
  useEffect(() => {
    const ac = new AbortController();
    apiGet<DataStatus>("/data-status", ac.signal)
      .then((status) => setState({ status, offline: false }))
      .catch(() => !ac.signal.aborted && setState({ status: null, offline: true }));
    return () => ac.abort();
  }, []);
  return state;
}
