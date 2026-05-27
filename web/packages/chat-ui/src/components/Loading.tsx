interface LoadingProps {
  /** 自定义提示文字 */
  text?: string;
  /** 全屏加载 */
  fullScreen?: boolean;
}

export default function Loading({ text = '加载中...', fullScreen = false }: LoadingProps) {
  const content = (
    <div className="flex flex-col items-center justify-center gap-3">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-primary-600" />
      {text && <p className="text-sm text-gray-500">{text}</p>}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80">
        {content}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[200px] items-center justify-center">
      {content}
    </div>
  );
}
