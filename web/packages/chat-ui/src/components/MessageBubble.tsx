import { useState } from 'react';
import type { ChatMessage } from '@/types/api';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const [showSql, setShowSql] = useState(false);

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

        {/* SQL 相关信息 */}
        {message.sql && !isUser && (
          <div className="mt-3 space-y-2">
            {/* SQL 展示按钮 */}
            <button
              onClick={() => setShowSql(!showSql)}
              className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 transition-colors"
            >
              <svg
                className={`h-3.5 w-3.5 transition-transform ${showSql ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {showSql ? '收起 SQL' : '查看 SQL'}
            </button>

            {showSql && (
              <div className="space-y-2">
                <div className="sql-display">
                  <code className="text-xs">{message.sql}</code>
                </div>

                {/* SQL 解释 */}
                {message.sql_explanation && (
                  <p className="text-xs text-gray-500">
                    {message.sql_explanation}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* 数据新鲜度提示 */}
        {message.freshness_note && !isUser && (
          <div className="mt-2 flex items-center gap-1.5">
            <svg
              className="h-3.5 w-3.5 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-xs text-gray-400">{message.freshness_note}</span>
          </div>
        )}

        {/* 底部元信息 */}
        {!isUser && (
          <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
            {message.total_rows !== undefined && (
              <span>共 {message.total_rows.toLocaleString()} 行</span>
            )}
            {message.has_more && <span>仅展示部分数据</span>}
          </div>
        )}
      </div>
    </div>
  );
}
