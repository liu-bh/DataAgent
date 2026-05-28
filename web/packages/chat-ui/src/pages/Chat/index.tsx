import { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { useSessionStore } from '@/stores/sessionStore';
import { useChatStore } from '@/stores/chatStore';
import Sidebar from '@/components/Sidebar';
import MessageBubble from '@/components/MessageBubble';
import QueryStatus from '@/components/QueryStatus';
import ChatInput from '@/components/ChatInput';
import Loading from '@/components/Loading';

export default function Chat() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const user = useAuthStore((s) => s.user);

  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);

  const messages = useChatStore((s) => s.messages);
  const isLoading = useChatStore((s) => s.isLoading);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const clearMessages = useChatStore((s) => s.clearMessages);
  const loadMessages = useChatStore((s) => s.loadMessages);
  const queryStatus = useChatStore((s) => s.queryStatus);
  const queryError = useChatStore((s) => s.queryError);
  const updateAssistantSql = useChatStore((s) => s.updateAssistantSql);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 未登录则跳转登录页
  useEffect(() => {
    if (!token) {
      navigate('/login', { replace: true });
    }
  }, [token, navigate]);

  // 获取用户信息
  useEffect(() => {
    if (token && !user) {
      fetchMe();
    }
  }, [token, user, fetchMe]);

  // 切换会话时加载消息
  const currentSessionId = sessionId ?? activeSessionId;

  useEffect(() => {
    if (currentSessionId) {
      setActiveSession(currentSessionId);
      loadMessages(currentSessionId);
    } else {
      clearMessages();
    }
  }, [currentSessionId, setActiveSession, loadMessages, clearMessages]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, queryStatus]);

  const handleSend = async (content: string) => {
    let sid = currentSessionId;

    // 如果没有当前会话，先创建一个
    if (!sid) {
      const { createSession } = useSessionStore.getState();
      const session = await createSession({
        title: content.slice(0, 30) + (content.length > 30 ? '...' : ''),
      });
      sid = session.id;
      navigate(`/chat/${sid}`, { replace: true });
    }

    await sendMessage({ session_id: sid, content });
  };

  /** 编辑 SQL 回调 */
  const handleEditSql = (messageId: string, editedSql: string) => {
    updateAssistantSql(messageId, editedSql);
  };

  /** 重试查询 */
  const handleRetry = () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMsg && currentSessionId) {
      // 移除错误消息
      const lastUserIdx = messages.lastIndexOf(lastUserMsg);
      const { setQueryStatus } = useChatStore.getState();
      setQueryStatus('idle');
      useChatStore.setState((state) => ({
        messages: state.messages.slice(0, lastUserIdx),
      }));
      // 重新发送
      sendMessage({ session_id: currentSessionId, content: lastUserMsg.content });
    }
  };

  // 未认证时不渲染主内容
  if (!token) {
    return <Loading fullScreen />;
  }

  return (
    <div className="flex h-screen bg-white">
      {/* 侧边栏 */}
      <Sidebar />

      {/* 主内容区 */}
      <main className="flex flex-1 flex-col">
        {/* 顶部栏 */}
        <header className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
          <h2 className="text-sm font-medium text-gray-700">
            {currentSessionId ? '对话详情' : '新的对话'}
          </h2>
          <button
            onClick={() => navigate('/settings')}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            title="设置"
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
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </header>

        {/* 消息列表区域 */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl">
            {messages.length === 0 && !isLoading ? (
              /* 空状态 */
              <div className="flex h-full flex-col items-center justify-center py-20">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-50">
                  <svg
                    className="h-8 w-8 text-primary-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                    />
                  </svg>
                </div>
                <h3 className="mb-1 text-lg font-medium text-gray-900">
                  开始新的对话
                </h3>
                <p className="text-sm text-gray-500">
                  输入您的问题，DataPilot 将为您查询数据并生成可视化图表
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onEditSql={handleEditSql}
                />
              ))
            )}

            {/* 查询状态指示器 */}
            <QueryStatus
              status={queryStatus}
              errorMessage={queryError}
              onRetry={handleRetry}
            />

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 输入区域 */}
        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </main>
    </div>
  );
}
