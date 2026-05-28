import { useCallback, useRef } from 'react';

/**
 * 节流 Hook
 * 限制函数在指定时间间隔内只执行一次
 */
export function useThrottle<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number = 300,
): T {
  const lastCallRef = useRef<number>(0);
  const lastArgsRef = useRef<unknown[] | null>(null);

  return useCallback(
    ((...args: unknown[]) => {
      const now = Date.now();
      const elapsed = now - lastCallRef.current;

      if (elapsed >= delay) {
        lastCallRef.current = now;
        callback(...args);
      } else {
        // 保存最后一次调用的参数，在节流结束后执行
        lastArgsRef.current = args;
        if (!lastCallRef.current) {
          lastCallRef.current = now;
          setTimeout(() => {
            lastCallRef.current = 0;
            if (lastArgsRef.current) {
              callback(...lastArgsRef.current);
              lastArgsRef.current = null;
            }
          }, delay - elapsed);
        }
      }
    }) as T,
    [callback, delay],
  );
}
