import { useState, useCallback, useRef, useEffect } from 'react';

interface PythonEditorProps {
  /** 初始代码 */
  initialCode?: string;
  /** 执行代码回调 */
  onExecute: (code: string) => void;
  /** 编辑区域最大高度 */
  maxHeight?: string;
  /** 是否只读 */
  readOnly?: boolean;
  /** 占位提示文字 */
  placeholder?: string;
}

/** 默认预设代码 */
const DEFAULT_CODE = `# DataPilot Python 沙箱
import pandas as pd
import numpy as np

# 你的代码写在这里...
`;

const MONO_FONT =
  'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';

export default function PythonEditor({
  initialCode = DEFAULT_CODE,
  onExecute,
  maxHeight = '400px',
  readOnly = false,
  placeholder = '在此输入 Python 代码...',
}: PythonEditorProps) {
  const [code, setCode] = useState(initialCode);
  const lineCountRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const lineCount = code.split('\n').length;

  /** 同步行号区域与编辑区域的滚动位置 */
  const handleScroll = useCallback(() => {
    if (textareaRef.current && lineCountRef.current) {
      lineCountRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  }, []);

  /** 执行代码 */
  const handleExecute = useCallback(() => {
    const trimmed = code.trim();
    if (trimmed) {
      onExecute(trimmed);
    }
  }, [code, onExecute]);

  /** 清空代码 */
  const handleClear = useCallback(() => {
    setCode('');
  }, []);

  /** 键盘快捷键：Ctrl/Cmd + Enter 执行 */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleExecute();
      }
    },
    [handleExecute],
  );

  /** 同步滚动：textarea 滚动时，行号跟随滚动 */
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.addEventListener('scroll', handleScroll);
    return () => {
      textarea.removeEventListener('scroll', handleScroll);
    };
  }, [handleScroll]);

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 overflow-hidden">
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-300">
            Python 沙箱
          </span>
          <span className="text-[10px] text-gray-500">
            {readOnly ? '只读' : 'Ctrl+Enter 运行'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* 字符计数 */}
          <span className="text-[10px] text-gray-500">
            {code.length} 字符 / {lineCount} 行
          </span>
          {!readOnly && (
            <div className="flex items-center gap-2">
              {/* 清空按钮 */}
              <button
                onClick={handleClear}
                disabled={!code}
                className="rounded-md px-3 py-1.5 text-xs font-medium text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors disabled:text-gray-600 disabled:cursor-not-allowed"
              >
                清空
              </button>
              {/* 运行按钮 */}
              <button
                onClick={handleExecute}
                disabled={!code.trim()}
                className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-700 disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed"
              >
                运行
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 编辑区域（行号 + textarea） */}
      <div className="relative flex" style={{ maxHeight }}>
        {/* 行号 */}
        <div
          ref={lineCountRef}
          className="flex-shrink-0 overflow-hidden select-none border-r border-gray-700 bg-gray-800/50"
          style={{
            fontFamily: MONO_FONT,
            fontSize: '12px',
            lineHeight: '1.625rem',
          }}
        >
          <div className="px-3 py-3">
            {Array.from({ length: lineCount }, (_, i) => (
              <div key={i} className="text-right text-gray-500">
                {i + 1}
              </div>
            ))}
          </div>
        </div>

        {/* 代码输入 */}
        <textarea
          ref={textareaRef}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={handleKeyDown}
          readOnly={readOnly}
          placeholder={placeholder}
          spellCheck={false}
          className="flex-1 resize-none bg-transparent p-3 font-mono text-xs leading-relaxed text-green-400 placeholder-gray-600 focus:outline-none"
          style={{
            fontFamily: MONO_FONT,
            fontSize: '12px',
            lineHeight: '1.625rem',
          }}
        ></textarea>
      </div>
    </div>
  );
}
