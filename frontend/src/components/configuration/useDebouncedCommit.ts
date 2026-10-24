import { useCallback, useEffect, useRef } from 'react';

/** Run `fn` after `delay` ms of quiet; `flush` runs a pending call now, `cancel` drops it. */
export function useDebouncedCommit<A extends unknown[]>(fn: (...args: A) => void, delay = 400) {
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<A | null>(null);

  const cancel = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    pending.current = null;
  }, []);
  const flush = useCallback(() => {
    const args = pending.current;
    cancel();
    if (args) fnRef.current(...args);
  }, [cancel]);
  const schedule = useCallback((...args: A) => {
    pending.current = args;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(flush, delay);
  }, [delay, flush]);

  // A change typed just before leaving the screen still saves
  useEffect(() => flush, [flush]);
  return { schedule, flush, cancel };
}
