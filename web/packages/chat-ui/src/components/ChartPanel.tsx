import { useMemo, useCallback } from 'react';
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
import { useChartType } from '@/hooks/useChartType';
import {
  type ChartType,
  generateChartOption,
} from '@/utils/chartConfig';

// 注册 ECharts 组件（按需加载，减小打包体积）
echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);

interface ChartPanelProps {
  /** 列名数组 */
  columns: string[];
  /** 查询结果行 */
  rows: Record<string, unknown>[];
  /** 最大高度 */
  maxHeight?: string;
}

/** 图表类型按钮配置 */
const CHART_TYPE_BUTTONS: { type: ChartType; label: string }[] = [
  { type: 'line', label: '折线' },
  { type: 'bar', label: '柱状' },
  { type: 'pie', label: '饼图' },
  { type: 'table', label: '表格' },
];

/** 各图表类型对应的 SVG 图标路径 */
const CHART_TYPE_ICONS: Record<ChartType, string> = {
  line: 'M3 3v18h18M7 16l4-8 4 4 5-6',
  bar: 'M3 21h18M5 21V7h4v14M13 21V11h4v10',
  pie: 'M12 2a10 10 0 100 20 10 10 0 000-20z M12 2v10l7-5',
  table: 'M3 5h18M3 9h18M3 13h18M3 17h18',
};

export default function ChartPanel({
  columns,
  rows,
  maxHeight = '320px',
}: ChartPanelProps) {
  const { chartType, chartColumns, setChartType } = useChartType(columns, rows);

  /** 是否有有效数据 */
  const hasData = columns.length > 0 && rows.length > 0;

  /** ECharts 配置 */
  const chartOption: EChartsOption = useMemo(() => {
    if (!hasData || chartType === 'table') return {};
    return generateChartOption(chartType, chartColumns);
  }, [hasData, chartType, chartColumns]);

  /** ECharts 通用配置（响应式等） */
  const chartProps = useMemo(() => ({
    option: chartOption,
    style: { height: maxHeight, width: '100%' },
    notMerge: true,
    lazyUpdate: true,
    opts: { renderer: 'canvas' as const },
  }), [chartOption, maxHeight]);

  /** 表格数据（columns + rows 格式） */
  const tableColumns = columns;
  const tableRows = rows;

  /** 切换图表类型 */
  const handleTypeChange = useCallback(
    (type: ChartType) => {
      setChartType(type);
    },
    [setChartType],
  );

  // 无数据时显示空状态
  if (!hasData) {
    return (
      <div
        className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-6 text-center"
        style={{ maxHeight }}
      >
        <svg
          className="mx-auto mb-2 h-8 w-8 text-gray-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
        <p className="text-xs text-gray-400">暂无数据</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      {/* 工具栏：图表类型切换 */}
      <div className="flex items-center gap-1 border-b border-gray-200 bg-gray-50 px-2 py-1.5">
        {CHART_TYPE_BUTTONS.map(({ type, label }) => (
          <button
            key={type}
            onClick={() => handleTypeChange(type)}
            className={`flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
              chartType === type
                ? 'bg-primary-100 text-primary-700'
                : 'text-gray-500 hover:bg-gray-200 hover:text-gray-700'
            }`}
            title={label}
          >
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d={CHART_TYPE_ICONS[type]}
              />
            </svg>
            {label}
          </button>
        ))}
      </div>

      {/* 图表 / 表格内容区域 */}
      <div className="p-3">
        {chartType === 'table' ? (
          /* 表格视图 */
          <div
            className="overflow-auto rounded border border-gray-200"
            style={{ maxHeight }}
          >
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  {tableColumns.map((col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-gray-100 last:border-b-0 hover:bg-gray-50"
                  >
                    {tableColumns.map((col) => (
                      <td
                        key={col}
                        className="px-3 py-2 text-gray-700 whitespace-nowrap max-w-[200px] truncate"
                        title={String(row[col] ?? '')}
                      >
                        {row[col] === null ? (
                          <span className="text-gray-300">NULL</span>
                        ) : (
                          String(row[col])
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* ECharts 图表 */
          <ReactEChartsCore
            echarts={echarts}
            {...chartProps}
          />
        )}
      </div>
    </div>
  );
}
