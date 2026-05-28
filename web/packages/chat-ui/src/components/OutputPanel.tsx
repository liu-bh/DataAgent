import { useState, useCallback } from 'react';
import type { SecurityIssue, SandboxStatus } from '@/types/sandbox';

interface OutputPanelProps {
  /** 标准输出 */
  stdout: string;
  /** 标准错误输出 */
  stderr: string;
  /** 是否执行成功 */
  success: boolean;
  /** 执行耗时（毫秒） */
  executionTimeMs?: number;
  /** 输出是否被截断 */
  truncated?: boolean;
  /** 最大高度 */
  maxHeight?: string;
  /** 沙箱执行状态 */
  status?: SandboxStatus;
  /** 内存使用量（MB） */
  memoryUsedMb?: number;
  /** 安全问题列表 */
  securityIssues?: SecurityIssue[];
}

/** 状态文本映射 */
const STATUS_LABEL: Record<SandboxStatus, string> = {
  success: '执行成功',
  timeout: '执行超时',
  memory_exceeded: '内存超限',
  security_error: '安全检查失败',
  runtime_error: '运行时错误',
  output_exceeded: '输出超限',
  system_error: '系统错误',
};

export default function OutputPanel({
  stdout,
  stderr,
  success,
  executionTimeMs,
  truncated,
  maxHeight = '300px',
  status,
  memoryUsedMb,
  securityIssues,
}: OutputPanelProps) {
  const [copied, setCopied] = useState(false);

  /** 复制全部输出到剪贴板 */
  const handleCopy = useCallback(async () => {
    const output = [stdout, stderr].filter(Boolean).join('\n');
    if (!output) return;

    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板写入失败，静默处理
    }
  }, [stdout, stderr]);

  const hasOutput = Boolean(stdout) || Boolean(stderr);
  const hasSecurityIssues = securityIssues && securityIssues.length > 0;

  /** 根据状态确定指示点颜色 */
  const statusDotColor = success
    ? 'bg-green-400'
    : status === 'security_error'
      ? 'bg-orange-400'
      : 'bg-red-400';

  /** 状态文本：优先使用 status 字段 */
  const statusText = status ? STATUS_LABEL[status] : (success ? '执行成功' : '执行失败');

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 overflow-hidden">
      {/* 顶部状态栏 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          {/* 状态指示点 */}
          <span
            className={`inline-block h-2 w-2 rounded-full ${statusDotColor}`}
          />
          <span className="text-xs font-medium text-gray-300">
            {statusText}
          </span>
          {executionTimeMs !== undefined && (
            <span className="text-[10px] text-gray-500">
              耗时: {executionTimeMs}ms
            </span>
          )}
          {memoryUsedMb !== undefined && memoryUsedMb > 0 && (
            <span className="text-[10px] text-gray-500">
              内存: {memoryUsedMb}MB
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* 截断标记 */}
          {truncated && (
            <span className="text-[10px] text-yellow-500">输出已截断</span>
          )}
          {/* 复制按钮 */}
          {hasOutput && (
            <button
              onClick={handleCopy}
              className="rounded px-2 py-0.5 text-[10px] text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
            >
              {copied ? '已复制' : '复制输出'}
            </button>
          )}
        </div>
      </div>

      {/* 输出内容区域 */}
      <div
        className="overflow-auto p-3"
        style={{ maxHeight }}
      >
        {/* 安全问题提示 */}
        {hasSecurityIssues && (
          <div className="mb-2 rounded-md border border-orange-700/50 bg-orange-900/20 p-2">
            <p className="text-xs font-medium text-orange-400 mb-1">
              检测到安全风险：
            </p>
            <ul className="space-y-1">
              {securityIssues!.map((issue, idx) => (
                <li key={idx} className="text-xs text-orange-300">
                  {issue.line !== undefined && (
                    <span className="text-orange-500">L{issue.line}: </span>
                  )}
                  {issue.message}
                  {issue.snippet && (
                    <code className="ml-1 rounded bg-orange-900/50 px-1 py-0.5 text-[10px] text-orange-200">
                      {issue.snippet}
                    </code>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {!hasOutput && !hasSecurityIssues ? (
          <p className="text-xs text-gray-500 italic">无输出</p>
        ) : (
          <div className="space-y-2">
            {/* 标准输出 */}
            {stdout && (
              <pre
                className={`whitespace-pre-wrap break-words text-xs leading-relaxed ${
                  success ? 'text-gray-100' : 'text-gray-300'
                }`}
                style={{
                  fontFamily:
                    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                }}
              >
                {stdout}
              </pre>
            )}

            {/* 标准错误 */}
            {stderr && (
              <pre
                className="whitespace-pre-wrap break-words text-xs leading-relaxed text-red-400"
                style={{
                  fontFamily:
                    'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                }}
              >
                {stderr}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
