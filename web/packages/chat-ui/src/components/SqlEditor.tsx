import { useState, useCallback } from 'react';

interface SqlEditorProps {
  /** 原始 SQL 语句 */
  originalSql: string;
  /** 执行 SQL 回调 */
  onExecute: (sql: string) => void;
  /** 重置 SQL 回调 */
  onReset: () => void;
}

/** SQL 关键词正则，用于语法高亮 */
const SQL_KEYWORDS =
  /\b(SELECT|FROM|WHERE|AND|OR|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|ON|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|AS|DISTINCT|UNION|ALL|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|VIEW|INTO|SET|VALUES|IN|NOT|IS|NULL|BETWEEN|LIKE|EXISTS|CASE|WHEN|THEN|ELSE|END|SUM|COUNT|AVG|MAX|MIN|ASC|DESC|WITH|IF|INTERVAL|CURRENT_DATE|CURRENT_TIME|DATE|TRUE|FALSE)\b/gi;

/** 对 SQL 文本进行简易语法高亮（关键词蓝色，字符串绿色） */
function highlightSql(sql: string): string {
  const escaped = sql
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  const highlighted = escaped.replace(
    SQL_KEYWORDS,
    (match) => `<span class="font-semibold text-blue-400">${match}</span>`,
  );

  return highlighted.replace(
    /'[^']*'/g,
    (match) => `<span class="text-green-400">${match}</span>`,
  );
}

export default function SqlEditor({
  originalSql,
  onExecute,
  onReset,
}: SqlEditorProps) {
  const [editedSql, setEditedSql] = useState(originalSql);

  /** 根据光标位置判断当前行是否应该高亮，返回完整高亮 HTML */
  const highlightedHtml = highlightSql(editedSql);

  /** 执行 SQL */
  const handleExecute = useCallback(() => {
    const trimmed = editedSql.trim();
    if (trimmed) {
      onExecute(trimmed);
    }
  }, [editedSql, onExecute]);

  /** 重置为原始 SQL */
  const handleReset = useCallback(() => {
    setEditedSql(originalSql);
    onReset();
  }, [originalSql, onReset]);

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

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-900 overflow-hidden">
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <span className="text-xs font-medium text-gray-300">SQL 编辑器</span>
        <div className="flex items-center gap-2">
          {/* 快捷键提示 */}
          <span className="text-[10px] text-gray-500">
            Ctrl+Enter 执行
          </span>
        </div>
      </div>

      {/* 编辑区域 */}
      <div className="relative">
        <textarea
          value={editedSql}
          onChange={(e) => setEditedSql(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full resize-none bg-transparent p-3 font-mono text-xs leading-relaxed text-transparent caret-white focus:outline-none"
          rows={6}
          spellCheck={false}
          style={{
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          }}
        />
        {/* 高亮层（与 textarea 重叠，仅用于显示） */}
        <pre
          className="pointer-events-none absolute inset-0 overflow-x-auto p-3 font-mono text-xs leading-relaxed"
          style={{
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          }}
          aria-hidden="true"
        >
          <code
            className="block text-gray-200 whitespace-pre-wrap break-words"
            dangerouslySetInnerHTML={{ __html: highlightedHtml }}
          />
        </pre>
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center justify-end gap-2 border-t border-gray-700 px-3 py-2">
        <button
          onClick={handleReset}
          className="rounded-md px-3 py-1.5 text-xs font-medium text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
        >
          重置
        </button>
        <button
          onClick={handleExecute}
          disabled={!editedSql.trim()}
          className="rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-primary-700 disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed"
        >
          执行
        </button>
      </div>
    </div>
  );
}
