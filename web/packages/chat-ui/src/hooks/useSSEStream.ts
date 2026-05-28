import { useRef, useState, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface UseSSEStreamOptions {
  onStatus?: (data: Record<string, unknown>) => void;
  onMessage?: (data: Record<string, unknown>) => void;
  onSql?: (data: Record<string, unknown>) => void;
  onChart?: (data: Record<string, unknown>) => void;
  onDone?: (data: Record<string, unknown>) => void;
  onError?: (data: Record<string, unknown>) => void;
}

export function useSSEStream(options: UseSSEStreamOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (url: string, body: Record<string, unknown>) => {
      // 取消之前的流
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsStreaming(true);
      setError(null);

      try {
        const token = useAuthStore.getState().token;

        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('无法读取响应流');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // 按 SSE 协议的 "\n\n" 分隔事件
          const parts = buffer.split('\n\n');
          // 最后一段可能不完整，保留在 buffer 中
          buffer = parts.pop() ?? '';

          for (const part of parts) {
            if (!part.trim()) continue;

            let event = '';
            let dataStr = '';

            for (const line of part.split('\n')) {
              if (line.startsWith('event:')) {
                event = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                dataStr = line.slice(5).trim();
              }
            }

            if (!event || !dataStr) continue;

            let data: Record<string, unknown>;
            try {
              data = JSON.parse(dataStr);
            } catch {
              data = { raw: dataStr };
            }

            // 根据事件类型分发回调
            switch (event) {
              case 'status':
                options.onStatus?.(data);
                break;
              case 'message':
                options.onMessage?.(data);
                break;
              case 'sql':
                options.onSql?.(data);
                break;
              case 'chart':
                options.onChart?.(data);
                break;
              case 'done':
                options.onDone?.(data);
                break;
              case 'error':
                options.onError?.(data);
                break;
              default:
                // 未知事件类型，静默忽略
                break;
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          // 用户主动取消，不视为错误
        } else {
          const msg = err instanceof Error ? err.message : 'SSE 流连接失败';
          setError(msg);
          options.onError?.({ message: msg });
        }
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [options],
  );

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  return { startStream, stopStream, isStreaming, error };
}
