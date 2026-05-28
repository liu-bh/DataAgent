import { useState, useCallback, useRef } from 'react';

/**
 * 异步操作状态
 */
interface AsyncActionState<T> {
  /** 返回数据 */
  data: T | null;
  /** 是否正在加载 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
}

/**
 * useAsyncAction 返回值
 */
interface UseAsyncActionReturn<T, A extends unknown[]> {
  /** 当前异步操作状态 */
  state: AsyncActionState<T>;
  /** 执行异步操作 */
  execute: (...args: A) => Promise<T | null>;
  /** 重置所有状态 */
  reset: () => void;
  /** 使用上次参数重试 */
  retry: () => void;
}

/**
 * 通用异步操作 Hook，统一管理 loading/error/retry 状态
 *
 * @param action - 异步操作函数
 * @param options - 可选的成功/失败回调
 * @returns 状态对象和操作方法
 */
export function useAsyncAction<T, A extends unknown[]>(
  action: (...args: A) => Promise<T>,
  options?: {
    onSuccess?: (data: T) => void;
    onError?: (error: string) => void;
  },
): UseAsyncActionReturn<T, A> {
  const [state, setState] = useState<AsyncActionState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  // 保存上次调用的参数，用于 retry
  const lastArgsRef = useRef<A | null>(null);

  const execute = useCallback(
    async (...args: A): Promise<T | null> => {
      setState({ data: null, loading: true, error: null });
      lastArgsRef.current = args;

      try {
        const result = await action(...args);
        setState({ data: result, loading: false, error: null });
        options?.onSuccess?.(result);
        return result;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : '操作失败，请稍后重试';
        setState({ data: null, loading: false, error: errorMessage });
        options?.onError?.(errorMessage);
        return null;
      }
    },
    [action, options],
  );

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
    lastArgsRef.current = null;
  }, []);

  const retry = useCallback(() => {
    if (lastArgsRef.current) {
      return execute(...lastArgsRef.current);
    }
    return Promise.resolve(null);
  }, [execute]);

  return { state, execute, reset, retry };
}
