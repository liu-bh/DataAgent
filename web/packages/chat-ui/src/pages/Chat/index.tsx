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
import EmptyState from '@/components/EmptyState';
import OnboardingGuide from '@/components/OnboardingGuide';
import ErrorFriendly from '@/components/ErrorFriendly';

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

  const onboardingCompleted = useAuthStore((s) => s.onboardingCompleted);
  const setOnboardingCompleted = useAuthStore((s) => s.setOnboardingCompleted);

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

  /** 新手引导完成回调 */
  const handleOnboardingComplete = () => {
    setOnboardingCompleted(true);
  };

  /** 新手引导发送示例查询 */
  const handleOnboardingSendExample = (question: string) => {
    setOnboardingCompleted(true);
    handleSend(question);
  };

  /** 根据消息内容判断错误类型 */
  const getErrorType = (msg: typeof messages[0]):
    | 'no_match'
    | 'timeout'
    | 'out_of_scope'
    | 'quota_exceeded'
    | 'unknown'
    | null => {
    if (msg.role !== 'assistant' || msg.content !== '抱歉，处理您的请求时出现了错误，请稍后重试。') {
      return null;
    }
    const error = msg.sql_error?.toLowerCase() ?? '';
    if (error.includes('no_match') || error.includes('未找到') || error.includes('not found')) {
      return 'no_match';
    }
    if (error.includes('timeout') || error.includes('超时')) {
      return 'timeout';
    }
    if (error.includes('out_of_scope') || error.includes('超出范围')) {
      return 'out_of_scope';
    }
    if (error.includes('quota') || error.includes('配额') || error.includes('上限')) {
      return 'quota_exceeded';
    }
    return 'unknown';
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
        <div className="relative flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl">
            {messages.length === 0 && !isLoading ? (
              /* 空状态 */
              <>
                <EmptyState onSendExample={handleSend} />
                {/* 首次登录时显示新手引导（覆盖在空状态上方） */}
                {!onboardingCompleted && (
                  <OnboardingGuide
                    onComplete={handleOnboardingComplete}
                    onSendExample={handleOnboardingSendExample}
                  />
                )}
              </>
            ) : (
              messages.map((msg) => {
                const errorType = getErrorType(msg);
                return (
                  <div key={msg.id}>
                    {errorType ? (
                      <ErrorFriendly
                        errorType={errorType}
                        errorMessage={msg.sql_error}
                        onRetry={handleRetry}
                        onSuggest={handleSend}
                      />
                    ) : (
                      <MessageBubble
                        message={msg}
                        onEditSql={handleEditSql}
                      />
                    )}
                  </div>
                );
              })
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
