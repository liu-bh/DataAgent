import { useState, useMemo, useCallback } from 'react';
import type { ChatMessage } from '@/types/api';
import type { RCAReport } from '@/types/rca';
import SqlPanel from '@/components/SqlPanel';
import SqlExplanation from '@/components/SqlExplanation';
import ChartPanel from '@/components/ChartPanel';
import DAGProgress from '@/components/DAGProgress';
import PythonEditor from '@/components/PythonEditor';
import OutputPanel from '@/components/OutputPanel';
import RCAReportView from '@/components/RCAReport';
import { useDagStore } from '@/stores/dagStore';
import { useChatStore } from '@/stores/chatStore';

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

  // DAG 状态：从 dagStore 获取当前正在执行的 DAG
  const currentDag = useDagStore((s) => s.currentDag);
  const queryStatus = useChatStore((s) => s.queryStatus);

  // Python 沙箱状态
  const pythonResult = useDagStore((s) => s.pythonResult);
  const pythonExecuting = useDagStore((s) => s.pythonExecuting);
  const executePython = useDagStore((s) => s.executePython);
  const clearPythonResult = useDagStore((s) => s.clearPythonResult);

  // RCA 根因分析状态
  const rcaReport = useDagStore((s) => s.rcaReport);
  const rcaLoading = useDagStore((s) => s.rcaLoading);
  const rcaError = useDagStore((s) => s.rcaError);

  /** 是否应该显示 DAG 进度面板 */
  const showDAGProgress = useMemo(() => {
    if (isUser) return false;
    // 仅在意图分析或 SQL 生成阶段，且存在正在执行的 DAG 时显示
    const isAnalyzing =
      queryStatus === 'analyzing_intent' || queryStatus === 'generating_sql';
    return isAnalyzing && currentDag !== null;
  }, [isUser, queryStatus, currentDag]);

  /** 从消息数据中提取 RCA 报告（如果存在） */
  const messageRcaReport = useMemo((): RCAReport | null => {
    if (isUser) return null;
    // 检查消息是否携带了 RCA 分析结果
    const rawData = message.data as Record<string, unknown> | undefined;
    if (!rawData) return null;
    // 如果消息数据中包含 rca_report 字段，则视为 RCA 分析结果
    if ('rca_report' in rawData && rawData.rca_report) {
      return rawData.rca_report as RCAReport;
    }
    return null;
  }, [isUser, message.data]);

  /** 需要渲染的 RCA 报告（优先使用 store 中的，否则使用消息中的） */
  const displayRcaReport = rcaReport ?? messageRcaReport;

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

  /** 执行 Python 代码 */
  const handleExecutePython = useCallback(
    (code: string) => {
      executePython(code, currentDag?.dag_id);
    },
    [executePython, currentDag],
  );

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
            {/* DAG 执行进度面板 */}
            {showDAGProgress && currentDag && (
              <DAGProgress dag={currentDag} maxHeight="400px" />
            )}

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

            {/* Python 代码编辑器与输出面板 */}
            {(pythonExecuting || pythonResult) && (
              <div className="space-y-2">
                {/* Python 编辑器 */}
                <PythonEditor
                  onExecute={handleExecutePython}
                  maxHeight="250px"
                />

                {/* 执行状态提示 */}
                {pythonExecuting && (
                  <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-gray-400">
                    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
                    Python 代码执行中...
                  </div>
                )}

                {/* 执行结果 */}
                {pythonResult && (
                  <div className="flex items-center justify-between">
                    <OutputPanel
                      stdout={pythonResult.stdout}
                      stderr={pythonResult.stderr}
                      success={pythonResult.success}
                      executionTimeMs={pythonResult.execution_time_ms}
                      truncated={pythonResult.truncated}
                      status={pythonResult.status}
                      memoryUsedMb={pythonResult.memory_used_mb}
                      securityIssues={pythonResult.security_issues}
                      maxHeight="200px"
                    />
                  </div>
                )}

                {/* 清空 Python 结果按钮 */}
                {pythonResult && (
                  <div className="flex justify-end">
                    <button
                      onClick={clearPythonResult}
                      className="text-[10px] text-gray-400 hover:text-gray-200 transition-colors"
                    >
                      清空 Python 结果
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* RCA 根因分析结果展示 */}
            {rcaLoading && (
              <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-gray-400 border-t-transparent" />
                <span className="text-xs text-gray-500">正在执行根因分析...</span>
              </div>
            )}
            {rcaError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                <p className="text-xs text-red-600">根因分析失败：{rcaError}</p>
              </div>
            )}
            {displayRcaReport && (
              <RCAReportView report={displayRcaReport} />
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

            {/* 图表面板：当消息包含查询结果数据时自动渲染 */}
            {message.data && message.data.length > 0 && tableColumns.length > 0 && (
              <ChartPanel
                columns={tableColumns}
                rows={message.data}
              />
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
