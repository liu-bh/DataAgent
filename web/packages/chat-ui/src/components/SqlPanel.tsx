import { useState, useCallback } from 'react';

interface SqlPanelProps {
  /** SQL 语句 */
  sql: string;
  /** SQL 方言 */
  dialect?: string;
  /** SQL 解析错误 */
  sqlError?: string;
  /** 编辑 SQL 回调（Phase1 stub） */
  onEditSql?: (editedSql: string) => void;
  /** 重新执行回调（Phase1 stub） */
  onReExecute?: () => void;
}

/** SQL 关键词正则，用于语法高亮 */
const SQL_KEYWORDS =
  /\b(SELECT|FROM|WHERE|AND|OR|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|ON|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|AS|DISTINCT|UNION|ALL|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|VIEW|INTO|SET|VALUES|IN|NOT|IS|NULL|BETWEEN|LIKE|EXISTS|CASE|WHEN|THEN|ELSE|END|SUM|COUNT|AVG|MAX|MIN|ASC|DESC|WITH|IF|INTERVAL|CURRENT_DATE|CURRENT_TIME|DATE|COUNT\(\*\)|TRUE|FALSE)\b/gi;

/** SQL 方言标签颜色映射 */
const DIALECT_STYLES: Record<string, string> = {
  mysql: 'bg-blue-100 text-blue-700',
  postgresql: 'bg-indigo-100 text-indigo-700',
  doris: 'bg-orange-100 text-orange-700',
  starrocks: 'bg-orange-100 text-orange-700',
  clickhouse: 'bg-yellow-100 text-yellow-700',
};

/** 对 SQL 文本进行简易语法高亮 */
function highlightSql(sql: string): string {
  // 转义 HTML 特殊字符
  const escaped = sql
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // 高亮 SQL 关键词
  const highlighted = escaped.replace(
    SQL_KEYWORDS,
    (match) => `<span class="font-semibold text-primary-700">${match}</span>`,
  );

  // 高亮字符串字面量
  return highlighted.replace(
    /'[^']*'/g,
    (match) => `<span class="text-green-600">${match}</span>`,
  );
}

export default function SqlPanel({
  sql,
  dialect,
  sqlError,
  onEditSql,
  onReExecute,
}: SqlPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editedSql, setEditedSql] = useState(sql);
  const [copied, setCopied] = useState(false);

  /** 复制 SQL 到剪贴板 */
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 降级方案
      const textarea = document.createElement('textarea');
      textarea.value = sql;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [sql]);

  /** 进入编辑模式 */
  const handleStartEdit = () => {
    setEditedSql(sql);
    setIsEditing(true);
    setIsCollapsed(false);
  };

  /** 取消编辑 */
  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedSql(sql);
  };

  /** 确认编辑 */
  const handleConfirmEdit = () => {
    if (editedSql.trim() && editedSql.trim() !== sql) {
      onEditSql?.(editedSql.trim());
    }
    setIsEditing(false);
  };

  const dialectStyle =
    dialect && DIALECT_STYLES[dialect.toLowerCase()]
      ? DIALECT_STYLES[dialect.toLowerCase()]
      : 'bg-gray-100 text-gray-600';

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-900 overflow-hidden">
      {/* 头部：折叠/展开 + 方言标签 + 操作按钮 */}
      <div className="flex items-center justify-between px-3 py-2">
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="flex items-center gap-1.5 text-xs font-medium text-gray-300 hover:text-white transition-colors"
        >
          <svg
            className={`h-3.5 w-3.5 transition-transform ${isCollapsed ? '' : 'rotate-90'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
          {isCollapsed ? '查看 SQL' : '收起 SQL'}
        </button>

        <div className="flex items-center gap-1.5">
          {/* SQL 方言标签 */}
          {dialect && (
            <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${dialectStyle}`}>
              {dialect.toUpperCase()}
            </span>
          )}

          {/* 复制按钮 */}
          <button
            onClick={handleCopy}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
            title="复制 SQL"
          >
            {copied ? (
              <svg className="h-3.5 w-3.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </button>

          {/* 编辑按钮 */}
          {!isEditing && onEditSql && (
            <button
              onClick={handleStartEdit}
              className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
              title="编辑 SQL"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
          )}

          {/* 重新执行按钮 */}
          {onReExecute && (
            <button
              onClick={onReExecute}
              className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
              title="重新执行"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* SQL 内容区域（可折叠） */}
      {!isCollapsed && (
        <div className="border-t border-gray-700">
          {/* SQL 解析错误提示 */}
          {sqlError && (
            <div className="flex items-center gap-2 bg-red-900/30 px-3 py-2 text-xs text-red-400">
              <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <span>SQL 解析错误：{sqlError}</span>
            </div>
          )}

          {/* 编辑模式：textarea */}
          {isEditing ? (
            <div className="p-3">
              <textarea
                value={editedSql}
                onChange={(e) => setEditedSql(e.target.value)}
                className="w-full resize-none rounded bg-gray-800 p-2 font-mono text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                rows={6}
                spellCheck={false}
              />
              <div className="mt-2 flex justify-end gap-2">
                <button
                  onClick={handleCancelEdit}
                  className="rounded-md px-3 py-1 text-xs font-medium text-gray-400 hover:bg-gray-700 hover:text-gray-200 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleConfirmEdit}
                  disabled={!editedSql.trim() || editedSql.trim() === sql}
                  className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-primary-700 disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed"
                >
                  确认修改
                </button>
              </div>
            </div>
          ) : (
            /* 展示模式：高亮 SQL */
            <pre className="overflow-x-auto p-3">
              <code
                className="block font-mono text-xs leading-relaxed text-gray-200"
                dangerouslySetInnerHTML={{ __html: highlightSql(sql) }}
              />
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
