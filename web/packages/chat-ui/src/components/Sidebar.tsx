import { useState, useEffect, useCallback } from 'react';
import { useSessionStore } from '@/stores/sessionStore';
import { useChatStore } from '@/stores/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { useNavigate } from 'react-router-dom';
import QueryHistory from '@/components/QueryHistory';
import StarredQueries from '@/components/StarredQueries';

export default function Sidebar() {
  const {
    sessions,
    activeSessionId,
    isLoading,
    fetchSessions,
    createSession,
    setActiveSession,
  } = useSessionStore();
  const {
    queryHistory,
    starredQueries,
    fetchHistory,
    fetchStarred,
    toggleStar,
  } = useChatStore();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  /** 当前激活的侧边栏 Tab */
  const [activeTab, setActiveTab] = useState<'sessions' | 'history' | 'starred'>('sessions');

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  /** Tab 切换时加载数据 */
  useEffect(() => {
    if (activeTab === 'history') {
      fetchHistory();
    } else if (activeTab === 'starred') {
      fetchStarred();
    }
  }, [activeTab, fetchHistory, fetchStarred]);

  const handleNewChat = async () => {
    const session = await createSession();
    navigate(`/chat/${session.id}`);
  };

  const handleSelectSession = (id: string) => {
    setActiveSession(id);
    navigate(`/chat/${id}`);
  };

  /** 一键复用查询：导航到当前会话并填入问题 */
  const handleReuseQuery = useCallback(
    (question: string) => {
      // 如果有活跃会话则跳转，否则不处理
      if (activeSessionId) {
        navigate(`/chat/${activeSessionId}`);
      }
      // 通过自定义事件通知 Chat 页面填充输入框
      window.dispatchEvent(
        new CustomEvent('datapilot:reuse-query', { detail: { question } }),
      );
    },
    [activeSessionId, navigate],
  );

  /** 清空查询历史 */
  const handleClearHistory = useCallback(async () => {
    const { clearHistory: apiClearHistory } = await import('@/api/history');
    try {
      await apiClearHistory();
      fetchHistory();
    } catch {
      // 清空失败静默处理
    }
  }, [fetchHistory]);

  // 按更新时间倒序，非归档在前
  const sortedSessions = [...sessions]
    .filter((s) => !s.is_archived)
    .sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );

  const archivedSessions = [...sessions]
    .filter((s) => s.is_archived)
    .sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );

  return (
    <aside className="flex h-full w-64 flex-col border-r border-gray-200 bg-gray-50">
      {/* 顶部：品牌 + 新建对话 */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h1 className="text-lg font-semibold text-gray-900">DataPilot</h1>
        <button
          onClick={handleNewChat}
          className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-200 hover:text-gray-700 transition-colors"
          title="新建对话"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4v16m8-8H4"
            />
          </svg>
        </button>
      </div>

      {/* Tab 切换栏 */}
      <div className="flex border-b border-gray-200 px-2">
        {([
          { key: 'sessions' as const, label: '会话' },
          { key: 'history' as const, label: '历史' },
          { key: 'starred' as const, label: '收藏' },
        ]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 py-2 text-center text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? 'border-b-2 border-primary-600 text-primary-600'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 内容区域：根据 Tab 渲染不同内容 */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {activeTab === 'sessions' && (
          <>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-primary-600" />
              </div>
            ) : (
              <>
                {sortedSessions.length === 0 && (
                  <p className="px-2 py-8 text-center text-sm text-gray-400">
                    暂无对话
                  </p>
                )}

                {sortedSessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => handleSelectSession(session.id)}
                    className={`mb-0.5 w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                      activeSessionId === session.id
                        ? 'bg-white text-gray-900 shadow-sm font-medium'
                        : 'text-gray-600 hover:bg-white hover:text-gray-900'
                    }`}
                  >
                    <div className="truncate">{session.title}</div>
                    <div className="mt-0.5 text-xs text-gray-400">
                      {session.message_count} 条消息
                    </div>
                  </button>
                ))}

                {/* 归档会话 */}
                {archivedSessions.length > 0 && (
                  <>
                    <div className="mt-4 px-3 text-xs font-medium uppercase text-gray-400">
                      已归档
                    </div>
                    {archivedSessions.map((session) => (
                      <button
                        key={session.id}
                        onClick={() => handleSelectSession(session.id)}
                        className="mb-0.5 w-full rounded-lg px-3 py-2.5 text-left text-sm text-gray-400 transition-colors hover:bg-white hover:text-gray-600"
                      >
                        <div className="truncate">{session.title}</div>
                      </button>
                    ))}
                  </>
                )}
              </>
            )}
          </>
        )}

        {activeTab === 'history' && (
          <QueryHistory
            history={queryHistory}
            onReuse={handleReuseQuery}
            onToggleStar={toggleStar}
            onClear={handleClearHistory}
          />
        )}

        {activeTab === 'starred' && (
          <StarredQueries
            queries={starredQueries}
            onReuse={handleReuseQuery}
            onUnstar={toggleStar}
          />
        )}
      </div>

      {/* 底部：用户信息 */}
      <div className="border-t border-gray-200 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-sm font-medium text-primary-700">
            {user?.display_name?.[0] ?? 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-gray-900">
              {user?.display_name ?? '用户'}
            </p>
            <p className="truncate text-xs text-gray-400">{user?.role ?? ''}</p>
          </div>
          <button
            onClick={() => {
              logout();
              navigate('/login');
            }}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
            title="退出登录"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}
