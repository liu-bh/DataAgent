import { useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { LineChart, BarChart, PieChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import type { DashboardPanel as DashboardPanelType } from '@/types/dashboard';

// 注册 ECharts 组件（按需加载）
echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);

interface DashboardPanelProps {
  panel: DashboardPanelType;
}

/**
 * Dashboard 面板组件
 * 根据 panel_type 渲染不同的内容：chart / table / metric / text
 */
export default function DashboardPanel({ panel }: DashboardPanelProps) {
  const { panel_type, title, chart_spec, metric_config, content, width, height } =
    panel;

  /** ECharts 配置项 */
  const chartOption: EChartsOption = useMemo(() => {
    if (panel_type !== 'chart' || !chart_spec) return {};
    return chart_spec as EChartsOption;
  }, [panel_type, chart_spec]);

  /** ECharts 渲染属性 */
  const chartProps = useMemo(
    () => ({
      option: chartOption,
      style: { height: '100%', width: '100%' },
      notMerge: true,
      lazyUpdate: true,
      opts: { renderer: 'canvas' as const },
    }),
    [chartOption],
  );

  /** 指标卡片趋势箭头颜色 */
  const trendColor = metric_config?.trend === 'up'
    ? 'text-green-500'
    : metric_config?.trend === 'down'
      ? 'text-red-500'
      : 'text-gray-400';

  /** 指标卡片趋势箭头 SVG */
  const trendIcon = metric_config?.trend === 'up'
    ? 'M5 10l7-7m0 0l7 7m-7-7v18'
    : metric_config?.trend === 'down'
      ? 'M19 14l-7 7m0 0l-7-7m7 7V3'
      : 'M5 12h14';

  /** 表格数据解析 */
  const tableData = useMemo(() => {
    if (panel_type !== 'table' || !chart_spec) return null;
    const spec = chart_spec as {
      columns?: string[];
      rows?: Record<string, unknown>[];
    };
    return spec;
  }, [panel_type, chart_spec]);

  return (
    <div
      className="flex flex-col rounded-lg border border-gray-700 bg-gray-800 shadow-sm overflow-hidden"
      style={{ gridColumn: `span ${width}`, minHeight: `${height}px` }}
    >
      {/* 面板标题栏 */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2.5">
        <h3 className="text-sm font-medium text-gray-200 truncate">{title}</h3>
        <div className="flex items-center gap-1">
          <span className="text-xs text-gray-500 uppercase">{panel_type}</span>
        </div>
      </div>

      {/* 面板内容区域 */}
      <div className="flex-1 p-4">
        {panel_type === 'chart' && chart_spec && (
          <div className="h-full min-h-[200px]">
            <ReactEChartsCore echarts={echarts} {...chartProps} />
          </div>
        )}

        {panel_type === 'table' && tableData && (
          <div className="overflow-auto max-h-[300px]">
            {tableData.columns && tableData.rows ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-700">
                    {tableData.columns.map((col) => (
                      <th
                        key={col}
                        className="px-3 py-2 text-left font-medium text-gray-400 whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.rows.map((row, idx) => (
                    <tr
                      key={idx}
                      className="border-b border-gray-700/50 last:border-b-0 hover:bg-gray-700/30"
                    >
                      {tableData.columns!.map((col) => (
                        <td
                          key={col}
                          className="px-3 py-2 text-gray-300 whitespace-nowrap max-w-[200px] truncate"
                          title={String(row[col] ?? '')}
                        >
                          {row[col] === null ? (
                            <span className="text-gray-600">NULL</span>
                          ) : (
                            String(row[col])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-gray-500 text-center py-4">
                暂无表格数据
              </p>
            )}
          </div>
        )}

        {panel_type === 'metric' && metric_config && (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            {/* 指标值 */}
            <div className="text-3xl font-bold text-white">
              {metric_config.value !== undefined
                ? metric_config.value.toLocaleString()
                : '--'}
              <span className="ml-1 text-base font-normal text-gray-400">
                {metric_config.unit}
              </span>
            </div>
            {/* 指标标签 */}
            <p className="text-sm text-gray-400">{metric_config.label}</p>
            {/* 趋势信息 */}
            {metric_config.change_percent !== undefined && (
              <div className={`flex items-center gap-1 ${trendColor} text-sm`}>
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d={trendIcon}
                  />
                </svg>
                <span>
                  {metric_config.change_percent > 0 ? '+' : ''}
                  {metric_config.change_percent}%
                </span>
              </div>
            )}
          </div>
        )}

        {panel_type === 'text' && (
          <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {content ?? '暂无文本内容'}
          </div>
        )}
      </div>
    </div>
  );
}
