/** 指标卡片 Props */
interface MetricCardProps {
  /** 卡片标题 */
  title: string;
  /** 核心数值 */
  value: string | number;
  /** 单位（如 "人"、"%"、"次"） */
  unit?: string;
  /** 同比趋势百分比（正数=上升，负数=下降，0 或 undefined=持平） */
  trend?: number;
  /** SVG 路径图标 */
  icon?: string;
}

/** 格式化数值：超过 10000 显示 "万" */
function formatValue(value: number): string {
  if (value >= 10000) {
    return (value / 10000).toFixed(1) + '万';
  }
  return value.toLocaleString('zh-CN');
}

export default function MetricCard({ title, value, unit, trend, icon }: MetricCardProps) {
  /** 趋势样式与图标 */
  const trendConfig = (() => {
    if (trend === undefined || trend === 0) {
      return {
        className: 'text-gray-400',
        arrow: 'M5 12h14M12 5l7 7-7 7',
        label: '持平',
      };
    }
    if (trend > 0) {
      return {
        className: 'text-green-500',
        arrow: 'M5 19l7-7 7 7',
        label: `+${trend.toFixed(1)}%`,
      };
    }
    return {
      className: 'text-red-500',
      arrow: 'M19 5l-7 7-7-7',
      label: `${trend.toFixed(1)}%`,
    };
  })();

  const displayValue = typeof value === 'number' ? formatValue(value) : value;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          {/* 标题 */}
          <p className="text-sm font-medium text-gray-500">{title}</p>

          {/* 数值 + 单位 */}
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-gray-900">{displayValue}</span>
            {unit && <span className="text-sm text-gray-400">{unit}</span>}
          </div>

          {/* 趋势 */}
          {trend !== undefined && (
            <div className={`flex items-center gap-1 text-xs font-medium ${trendConfig.className}`}>
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d={trendConfig.arrow} />
              </svg>
              <span>{trendConfig.label}</span>
              <span className="text-gray-400 ml-1">同比</span>
            </div>
          )}
        </div>

        {/* 图标 */}
        {icon && (
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary-50">
            <svg className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}
