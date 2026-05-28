import { useState, useMemo } from 'react';
import type { ChatMessage } from '@/types/api';
import SqlPanel from '@/components/SqlPanel';
import SqlExplanation from '@/components/SqlExplanation';

interface MessageBubbleProps {
  message: ChatMessage;
  /** 编辑 SQL 回调 */
  onEditSql?: (messageId: string, editedSql: string) => void;
}

export default function MessageBubble({
  message,
  onEditSql,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const [showData, setShowData] = useState(false);

  /** 查询结果表格列（从 data 数组推导） */
  const tableColumns = useMemo(() => {
    if (!message.data || message.data.length === 0) return [];
    return Object.keys(message.data[0]);
  }, [message.data]);

  /** 展示的行数（Phase1 限制 5 行） */
  const displayRows = useMemo(() => {
    if (!message.data) return [];
    return message.data.slice(0, 5);
  }, [message.data]);

  /** 编辑 SQL 回调 */
  const handleEditSql = (editedSql: string) => {
    onEditSql?.(message.id, editedSql);
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-white text-gray-900 shadow-sm border border-gray-100'
        }`}
      >
        {/* 消息内容 */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
        </div>

        {/* ========== 助手消息增强内容 ========== */}
        {!isUser && (
          <div className="mt-3 space-y-3">
            {/* SQL 解释面板 */}
            {message.sql_explanation && (
              <SqlExplanation
                explanation={message.sql_explanation}
                freshnessNote={message.freshness_note}
                totalRows={message.total_rows}
              />
            )}

            {/* SQL 预览面板 */}
            {message.sql && (
              <SqlPanel
                sql={message.edited_sql ?? message.sql}
                dialect={message.sql_dialect}
                sqlError={message.sql_error}
                onEditSql={handleEditSql}
                onReExecute={() => {
                  // Phase1 stub：重新执行功能
                  console.log('重新执行 SQL:', message.sql);
                }}
              />
            )}

            {/* 查询结果表格（Phase1 简化版：最多 5 行） */}
            {tableColumns.length > 0 && (
              <div className="space-y-2">
                <button
                  onClick={() => setShowData(!showData)}
                  className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
                >
                  <svg
                    className={`h-3.5 w-3.5 transition-transform ${showData ? 'rotate-90' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  {showData ? '收起数据' : `查看数据 (${message.total_rows ?? displayRows.length} 行)`}
                </button>

                {showData && (
                  <div className="overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          {tableColumns.map((col) => (
                            <th
                              key={col}
                              className="px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap"
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {displayRows.map((row, idx) => (
                          <tr
                            key={idx}
                            className="border-b border-gray-100 last:border-b-0"
                          >
                            {tableColumns.map((col) => (
                              <td
                                key={col}
                                className="px-3 py-2 text-gray-700 whitespace-nowrap max-w-[200px] truncate"
                                title={String(row[col] ?? '')}
                              >
                                {row[col] === null
                                  ? <span className="text-gray-300">NULL</span>
                                  : String(row[col])}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {/* 仅展示部分数据的提示 */}
                    {message.has_more && (
                      <div className="border-t border-gray-200 px-3 py-1.5 text-center text-xs text-gray-400">
                        仅展示前 5 行，共 {message.total_rows?.toLocaleString() ?? '...'} 行
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 图表占位（Phase5 完善） */}
            {message.chart_spec && (
              <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-center">
                <svg
                  className="mx-auto mb-2 h-8 w-8 text-gray-300"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
                <p className="text-xs text-gray-400">
                  {message.chart_spec.chartType === 'table'
                    ? '表格视图'
                    : '图表将在后续版本中展示'}
                </p>
              </div>
            )}
          </div>
        )}

        {/* ========== 用户消息增强：编辑 SQL diff ========== */}
        {isUser && message.edited_sql && (
          <div className="mt-2 space-y-1.5">
            <p className="text-xs text-white/60">已编辑 SQL：</p>
            <pre className="overflow-x-auto rounded bg-white/10 p-2 text-xs">
              <code className="text-white/90">{message.edited_sql}</code>
            </pre>
          </div>
        )}

        {/* 底部元信息（仅助手消息） */}
        {!isUser && !message.sql_explanation && (
          <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
            {message.total_rows !== undefined && (
              <span>共 {message.total_rows.toLocaleString()} 行</span>
            )}
            {message.has_more && <span>仅展示部分数据</span>}
          </div>
        )}

        {/* 时间戳 */}
        <div
          className={`mt-2 text-xs ${
            isUser ? 'text-white/50' : 'text-gray-300'
          }`}
        >
          {new Date(message.created_at).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
}
