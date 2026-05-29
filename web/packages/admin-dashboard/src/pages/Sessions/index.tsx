import { useEffect, useState, useCallback } from 'react';
import type { Session } from '@/api/sessions';
import { sessionApi } from '@/api/sessions';
import { formatDate } from '@/utils/format';

/** 归档状态标签 */
function ArchiveBadge({ archived }: { archived: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        archived
          ? 'bg-yellow-100 text-yellow-700'
          : 'bg-green-100 text-green-700'
      }`}
    >
      {archived ? '已归档' : '进行中'}
    </span>
  );
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  /** 加载会话列表 */
  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sessionApi.list(200);
      setSessions(data);
    } catch (err) {
      console.error('加载会话列表失败:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  /** 按标题搜索过滤 */
  const filteredSessions = search
    ? sessions.filter((s) => s.title.toLowerCase().includes(search.toLowerCase()))
    : sessions;

  /** 删除会话 */
  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`确定要删除会话 "${title}" 吗？此操作不可撤销。`)) return;
    setBusyId(id);
    try {
      await sessionApi.delete(id);
      await fetchSessions();
    } catch (err) {
      console.error('删除会话失败:', err);
      alert('删除失败，请稍后重试');
    } finally {
      setBusyId(null);
    }
  };

  /** 切换归档状态 */
  const handleToggleArchive = async (session: Session) => {
    setBusyId(session.id);
    try {
      await sessionApi.update(session.id, { is_archived: !session.is_archived });
      await fetchSessions();
    } catch (err) {
      console.error('更新会话失败:', err);
      alert('更新失败，请稍后重试');
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="text-gray-400">加载中...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <p className="text-sm text-gray-500">共 {sessions.length} 个会话</p>
          {/* 搜索框 */}
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
              />
            </svg>
            <input
              type="text"
              placeholder="按标题搜索..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded-lg border border-gray-300 py-1.5 pl-9 pr-3 text-sm text-gray-700 placeholder-gray-400 transition-colors focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
        </div>
      </div>

      {/* 会话表格 */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">标题</th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">消息数</th>
              <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">状态</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">创建时间</th>
              <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {filteredSessions.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-sm text-gray-400">
                  {search ? '未找到匹配的会话' : '暂无会话'}
                </td>
              </tr>
            ) : (
              filteredSessions.map((session) => (
                <tr key={session.id} className="transition-colors hover:bg-gray-50">
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {session.id.slice(0, 8)}...
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                    {session.title || '-'}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-center text-sm text-gray-600">
                    {session.message_count}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-center">
                    <ArchiveBadge archived={session.is_archived} />
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                    {formatDate(session.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleToggleArchive(session)}
                        disabled={busyId === session.id}
                        className="inline-flex items-center rounded-md border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50"
                      >
                        {session.is_archived ? '取消归档' : '归档'}
                      </button>
                      <button
                        onClick={() => handleDelete(session.id, session.title || session.id)}
                        disabled={busyId === session.id}
                        className="inline-flex items-center rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
                      >
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
