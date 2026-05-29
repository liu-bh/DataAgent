import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

/** 路径到页面标题的映射 */
const PAGE_TITLES: Record<string, string> = {
  '/admin': '管理后台',
  '/admin/dashboard': '大盘概览',
  '/admin/analytics': '查询分析',
  '/admin/data-sources': '数据源管理',
  '/admin/semantic-models': '语义模型管理',
  '/admin/semantic-models/create': '创建语义模型',
  '/admin/metrics': '指标管理',
  '/admin/dimensions': '维度管理',
};

/** 根据 pathname 匹配标题 */
function getPageTitle(pathname: string): string {
  // 精确匹配优先
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  // 前缀匹配（如 /admin/semantic-models/xxx -> 语义模型管理）
  const match = Object.keys(PAGE_TITLES)
    .sort((a, b) => b.length - a.length)
    .find((key) => key !== '/admin' && pathname.startsWith(key));
  return match ? PAGE_TITLES[match]! : '管理后台';
}

export default function AdminLayout() {
  const location = useLocation();
  const title = getPageTitle(location.pathname);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* 左侧导航 */}
      <Sidebar />

      {/* 右侧主区域 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 顶部栏 */}
        <Header title={title} />

        {/* 内容区域 */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
