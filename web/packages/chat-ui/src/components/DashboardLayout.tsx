import type { DashboardLayout as DashboardLayoutType } from '@/types/dashboard';
import DashboardPanel from './DashboardPanel';

interface DashboardLayoutProps {
  dashboard: DashboardLayoutType;
}

/**
 * Dashboard 网格布局组件
 * 使用 CSS Grid 实现 12 列网格系统
 * 面板按 position.row 和 position.col 定位
 */
export default function DashboardLayoutView({
  dashboard,
}: DashboardLayoutProps) {
  const { panels, columns } = dashboard;

  // 如果没有面板，显示空状态
  if (panels.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-gray-700 bg-gray-800 py-20">
        <svg
          className="mb-3 h-12 w-12 text-gray-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
          />
        </svg>
        <p className="text-sm text-gray-500">暂无面板，请添加可视化面板</p>
      </div>
    );
  }

  return (
    <div
      className="grid gap-4"
      style={{
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
      }}
    >
      {panels.map((panel) => (
        <DashboardPanel key={panel.panel_id} panel={panel} />
      ))}
    </div>
  );
}
