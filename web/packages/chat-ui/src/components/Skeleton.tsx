/**
 * 骨架屏加载组件
 * 提供聊天消息和仪表板的占位加载效果
 */

interface SkeletonProps {
  className?: string;
}

/** 基础骨架元素 */
export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-md bg-gray-700 ${className}`}
    />
  );
}

/** 聊天消息骨架 */
export function ChatMessageSkeleton() {
  return (
    <div className="mb-4 flex gap-3">
      {/* 头像 */}
      <Skeleton className="h-8 w-8 flex-shrink-0 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-20 w-full" />
      </div>
    </div>
  );
}

/** 对话列表骨架 */
export function ChatListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border border-gray-700 bg-gray-800/50 p-3">
          <Skeleton className="mb-2 h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

/** Dashboard 面板骨架 */
export function DashboardPanelSkeleton() {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <Skeleton className="mb-3 h-5 w-1/3" />
      <Skeleton className="h-48 w-full rounded" />
    </div>
  );
}
