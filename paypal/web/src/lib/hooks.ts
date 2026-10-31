import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api";

/** Load something from the API, with loading and error states, and a reload. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[], pollMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const reload = useCallback(async () => {
    const mine = ++seq.current;
    try {
      const value = await load();
      if (mine === seq.current) {
        setData(value);
        setError("");
      }
    } catch (e) {
      if (mine === seq.current) setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      if (mine === seq.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    setLoading(true);
    reload();
    if (!pollMs) return;
    const t = window.setInterval(reload, pollMs);
    return () => window.clearInterval(t);
  }, [reload, pollMs]);
  return { data, error, loading, reload, setData };
}

/** The current Unix time, ticking every second. */
export function useNow(): number {
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => {
    const t = window.setInterval(() => setNow(Math.floor(Date.now() / 1000)), 1000);
    return () => window.clearInterval(t);
  }, []);
  return now;
}

/** The demo vendor this browser made last, so a visitor can come back to it. */
export const lastDemo = {
  get: (): string | null => {
    try {
      return localStorage.getItem("redline-demo-vendor");
    } catch {
      return null;
    }
  },
  set: (token: string) => {
    try {
      localStorage.setItem("redline-demo-vendor", token);
    } catch {
      /* fine */
    }
  },
};
