# TypeScript 前端开发规范

## 1. 基础约定

- **TypeScript**：>= 5.3，开启 `strict` 模式
- **构建工具**：Vite
- **包管理**：pnpm（monorepo workspace）
- **格式化**：Prettier
- **Lint**：ESLint（flat config）
- **React**：>= 18（函数组件 + Hooks）
- **状态管理**：zustand
- **请求**：ky（内置重试/超时）
- **CSS**：Tailwind CSS

## 2. 命名规范

| 类型 | 风格 | 示例 |
|------|------|------|
| 组件文件 | `PascalCase.tsx` | `ChatPanel.tsx`, `MetricEditor.tsx` |
| Hook 文件 | `camelCase 且 use 前缀` | `useSession.ts`, `useStreaming.ts` |
| 工具/函数文件 | `camelCase.ts` | `formatDate.ts`, `parseSql.ts` |
| 类型文件 | `camelCase.types.ts` | `metric.types.ts`, `session.types.ts` |
| 常量文件 | `camelCase.constants.ts` | `api.constants.ts` |
| 组件 | `PascalCase` | `function ChatPanel() {}` |
| Hook | `camelCase` + `use` 前缀 | `function useSession()` |
| 普通函数 | `camelCase` | `function formatDate()` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| CSS 类名 | Tailwind 原子类优先 | `className="flex items-center gap-2"` |
| 类型/接口 | `PascalCase` | `interface ChatMessage {}` |
| 枚举 | `PascalCase` 成员 `UPPER_SNAKE` | `enum Role { ADMIN, USER }` |

## 3. 组件规范

### 3.1 函数组件

```typescript
// 正确：函数声明 + 类型 Props 接口
interface MetricCardProps {
  name: string;
  value: number;
  trend?: "up" | "down" | "flat";
}

export function MetricCard({ name, value, trend }: MetricCardProps) {
  return (
    <div className="rounded-lg border p-4">
      <span className="text-sm text-gray-500">{name}</span>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}
```

### 3.2 组件拆分原则

- 单个文件不超过 **300 行**
- 组件职责单一，超过 3 个 `useState` 考虑拆分
- 复杂逻辑抽为自定义 Hook
- UI 展示组件与业务逻辑组件分离

### 3.3 组件目录结构

```
web/packages/chat-ui/src/
├── components/
│   ├── ChatPanel/
│   │   ├── ChatPanel.tsx        # 主组件
│   │   ├── ChatPanel.types.ts   # 类型定义
│   │   ├── ChatMessage.tsx      # 子组件
│   │   ├── ChatInput.tsx        # 子组件
│   │   └── index.ts             # 导出
│   ├── ChartRenderer/
│   └── common/                  # 通用组件（Button、Modal、Table...）
├── hooks/
│   ├── useSession.ts
│   ├── useStreaming.ts
│   └── useAuth.ts
├── stores/
│   ├── chatStore.ts
│   └── userStore.ts
├── services/
│   ├── api.ts                   # 请求封装
│   └── sse.ts                   # SSE 连接
├── utils/
│   ├── format.ts
│   └── parseSql.ts
├── types/
│   └── index.ts                 # 全局类型
└── App.tsx
```

## 4. Hooks 规范

```typescript
// 正确：以 use 开头，返回值明确
function useSession(sessionId: string) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    fetchSession(sessionId)
      .then(setSession)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [sessionId]);

  return { session, loading, error };
}
```

**规则：**
- 只在顶层调用 Hooks，不在循环/条件中使用
- 自定义 Hook 内部可以调用其他自定义 Hook
- 返回对象而非数组（除非只有 2 个值）

## 5. 状态管理 (zustand)

```typescript
// stores/chatStore.ts
import { create } from "zustand";

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  addMessage: (msg: ChatMessage) => void;
  setStreaming: (v: boolean) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setStreaming: (v) => set({ isStreaming: v }),
  clearMessages: () => set({ messages: [] }),
}));
```

**规则：**
- 全局共享状态用 zustand（用户信息、会话列表等）
- 组件局部状态用 `useState`/`useReducer`
- 服务端状态优先用 React Query（数据源列表、指标列表等）
- 禁止通过 props 层层传递超过 3 层（用 Context 或 zustand）

## 6. API 请求

```typescript
// services/api.ts
import ky from "ky";

export const api = ky.create({
  prefixUrl: "/api/v1",
  timeout: 30000,
  hooks: {
    beforeError: [
      async (error) => {
        if (error.response.status === 401) {
          window.location.href = "/login";
        }
        return error;
      },
    ],
  },
});

// 业务调用
export const chatApi = {
  sendMessage: (sessionId: string, content: string) =>
    api.post("chat/message", { json: { session_id: sessionId, content } }).json<ChatResponse>(),

  getSessions: () =>
    api.get("sessions").json<SessionListResponse>(),
};
```

## 7. SSE 流式接收

```typescript
// services/sse.ts
export function streamChat(
  sessionId: string,
  content: string,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): AbortController {
  const controller = new AbortController();

  fetch("/api/v1/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, content }),
    signal: controller.signal,
  })
    .then(async (res) => {
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        // 解析 SSE data: 行
        for (const line of text.split("\n")) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") { onDone(); return; }
            onChunk(data);
          }
        }
      }
    })
    .catch(onError);

  return controller;
}
```

## 8. 类型定义

```typescript
// types/index.ts

// 用 interface 定义对象形状
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sql?: string;
  sqlExplanation?: string;   // SQL 自然语言解释
  chartSpec?: ChartSpec;
  freshnessNote?: string;    // 数据新鲜度提示
  dataCutoff?: string;        // 数据截止时间 ISO 8601
  totalRows?: number;         // 总行数
  hasMore?: boolean;          // 是否有更多数据
  cursor?: string;            // 游标分页 token
  createdAt: string;
}

// 游标分页响应（替代 offset 分页，适用于大数据量）
export interface CursorPageResult<T> {
  data: T[];
  totalRows: number;
  hasMore: boolean;
  cursor: string | null;
}

// 会话状态
export interface SessionState {
  id: string;
  messageCount: number;       // 当前消息数，上限 50
  expiresAt: string;          // 30 分钟无操作过期
  isExpired: boolean;
}

// 用 type 定义联合类型/工具类型
export type Role = "admin" | "analyst" | "viewer";
export type DataSourceType = "mysql" | "postgresql" | "doris" | "starrocks" | "clickhouse";

// 枚举场景用 as const + typeof
export const TaskStatus = {
  PENDING: "pending",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
} as const;

export type TaskStatus = (typeof TaskStatus)[keyof typeof TaskStatus];
```

**规则：**
- 公共 API 类型统一放 `types/` 目录
- 组件内部类型放同目录 `.types.ts`
- 禁止用 `any`，必要时用 `unknown`
- 后端响应类型与 Pydantic 模型保持一致

## 9. 样式规范 (Tailwind CSS)

**规则：**
- 优先使用 Tailwind 原子类
- 复杂动画/特殊效果提取为组件（如 `AnimatedCounter.tsx`）
- 主题色通过 `tailwind.config.ts` 统一定义，禁止硬编码颜色值
- 响应式使用 `sm:/md:/lg:` 前缀

```typescript
// 正确
<div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
  <span className="text-sm font-medium text-gray-700">指标名称</span>
  <span className="text-lg font-bold text-blue-600">1,234</span>
</div>

// 错误：硬编码颜色、内联样式
<div style={{ color: "#1a73e8", fontSize: 18, fontWeight: "bold" }}>
```

## 10. 性能约定

- 列表使用虚拟滚动（`@tanstack/react-virtual`），超过 100 条时启用
- 图片/图表懒加载
- 路由懒加载：`React.lazy()` + `Suspense`
- 避免不必要的 re-render：`useMemo`/`useCallback` 用于传递给子组件的引用
- 大列表 key 使用稳定 ID，禁止用数组索引
