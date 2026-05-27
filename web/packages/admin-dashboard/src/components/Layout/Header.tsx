/** 顶部栏 Props */
interface HeaderProps {
  title: string;
}

export default function Header({ title }: HeaderProps) {
  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6">
      {/* 页面标题 */}
      <h1 className="text-lg font-semibold text-gray-900">{title}</h1>

      {/* 右侧用户信息 */}
      <div className="flex items-center gap-4">
        {/* 全局搜索入口 */}
        <div className="relative">
          <input
            type="text"
            placeholder="搜索指标、维度..."
            className="h-9 w-64 rounded-lg border border-gray-300 bg-gray-50 pl-9 pr-3 text-sm text-gray-700 placeholder:text-gray-400 focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-primary-400"
          />
          <svg
            className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
        </div>

        {/* 用户头像 */}
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-sm font-medium text-primary-700">
            A
          </div>
          <span className="text-sm font-medium text-gray-700">管理员</span>
        </div>
      </div>
    </header>
  );
}
