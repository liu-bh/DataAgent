import { useState, useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import type { DrillDownResult, DimensionValue } from '@/types/rca';

// 注册 ECharts 组件
echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface DrillDownChartProps {
  drillDown: DrillDownResult;
}

/** 格式化百分比 */
function formatPercent(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

/** 单个维度值行 */
function DimensionValueRow({ item }: { item: DimensionValue }) {
  const isPositive = item.change_percent >= 0;
  const changeColor = isPositive ? 'text-emerald-400' : 'text-red-400';

  return (
    <div className="flex items-center gap-3 py-1.5 text-xs">
      <span className="w-20 shrink-0 truncate text-gray-300" title={item.value}>
        {item.value}
      </span>
      <span className="w-16 shrink-0 text-right text-gray-400">
        {item.current.toLocaleString('zh-CN')}
      </span>
      <span className="w-16 shrink-0 text-right text-gray-500">
        {item.baseline.toLocaleString('zh-CN')}
      </span>
      <span className={`w-16 shrink-0 text-right font-medium ${changeColor}`}>
        {formatPercent(item.change_percent)}
      </span>
      <span className={`w-16 shrink-0 text-right font-medium ${changeColor}`}>
        {formatPercent(item.contribution_percent)}
      </span>
    </div>
  );
}

export default function DrillDownChart({ drillDown }: DrillDownChartProps) {
  const [expanded, setExpanded] = useState(false);

  const { dimension_name, values, top_contributors } = drillDown;
  const displayValues = expanded ? values : top_contributors;
  const hasMore = !expanded && values.length > top_contributors.length;

  // ECharts 水平柱状图配置
  const chartOption: EChartsOption = useMemo(() => {
    // 取贡献度绝对值最大的前 10 项展示图表
    const sorted = [...displayValues]
      .sort((a, b) => Math.abs(b.contribution_percent) - Math.abs(a.contribution_percent))
      .slice(0, 10)
      .reverse(); // reverse 让最大值在顶部

    const yLabels = sorted.map((v) => v.value);
    const data = sorted.map((v) => ({
      value: v.contribution_percent,
      itemStyle: {
        color: v.contribution_percent >= 0 ? '#10b981' : '#f43f5e',
      },
    }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: '#1f2937',
        borderColor: '#374151',
        textStyle: { color: '#e5e7eb', fontSize: 11 },
        formatter: (params: unknown) => {
          const p = params as Array<{ name: string; value: number }>;
          if (!Array.isArray(p) || p.length === 0) return '';
          const item = sorted[Number((p[0] as { dataIndex: number }).dataIndex)];
          if (!item) return '';
          return [
            `<strong>${item.value}</strong><br/>`,
            `当前值: ${item.current.toLocaleString('zh-CN')}<br/>`,
            `基线值: ${item.baseline.toLocaleString('zh-CN')}<br/>`,
            `变化: ${formatPercent(item.change_percent)}<br/>`,
            `贡献度: ${formatPercent(item.contribution_percent)}`,
          ].join('');
        },
      },
      grid: {
        left: '3%',
        right: '8%',
        bottom: '3%',
        top: '3%',
        containLabel: true,
      },
      xAxis: {
        type: 'value',
        axisLine: { lineStyle: { color: '#4b5563' } },
        axisLabel: {
          color: '#9ca3af',
          fontSize: 10,
          formatter: (val: number) => `${val > 0 ? '+' : ''}${val}%`,
        },
        splitLine: { lineStyle: { color: '#374151', type: 'dashed' } },
      },
      yAxis: {
        type: 'category',
        data: yLabels,
        axisLine: { lineStyle: { color: '#4b5563' } },
        axisLabel: { color: '#9ca3af', fontSize: 10 },
        splitLine: { show: false },
      },
      series: [
        {
          type: 'bar',
          data,
          barMaxWidth: 20,
          label: {
            show: true,
            position: 'right',
            color: '#9ca3af',
            fontSize: 10,
            formatter: (params: { value: number }) =>
              `${params.value > 0 ? '+' : ''}${params.value.toFixed(1)}%`,
          },
          itemStyle: { borderRadius: [0, 3, 3, 0] },
        },
      ],
    };
  }, [displayValues]);

  return (
    <div className="rounded-lg border border-gray-700/50 bg-gray-900/50">
      {/* 维度名称标题 */}
      <div className="border-b border-gray-700/50 px-3 py-2">
        <span className="text-xs font-medium text-gray-300">{dimension_name}</span>
        <span className="ml-2 text-xs text-gray-500">
          {values.length} 个维度值
        </span>
      </div>

      {/* ECharts 水平柱状图 */}
      <div className="p-2">
        <ReactEChartsCore
          echarts={echarts}
          option={chartOption}
          style={{ height: `${Math.max(displayValues.length * 28, 120)}px`, width: '100%' }}
          notMerge
          lazyUpdate
          opts={{ renderer: 'canvas' }}
        />
      </div>

      {/* 明细表格 */}
      <div className="border-t border-gray-700/50 px-3 py-2">
        {/* 表头 */}
        <div className="flex items-center gap-3 border-b border-gray-700/30 pb-1 text-xs text-gray-500">
          <span className="w-20 shrink-0">维度值</span>
          <span className="w-16 shrink-0 text-right">当前值</span>
          <span className="w-16 shrink-0 text-right">基线值</span>
          <span className="w-16 shrink-0 text-right">变化</span>
          <span className="w-16 shrink-0 text-right">贡献度</span>
        </div>

        {/* 数据行 */}
        <div className="max-h-40 overflow-y-auto">
          {displayValues.map((item, idx) => (
            <DimensionValueRow key={idx} item={item} />
          ))}
        </div>

        {/* 展开/收起按钮 */}
        {hasMore && (
          <button
            onClick={() => setExpanded(true)}
            className="mt-1 w-full text-center text-xs text-primary-400 hover:text-primary-300 transition-colors"
          >
            展开全部 {values.length} 项
          </button>
        )}
        {expanded && values.length > top_contributors.length && (
          <button
            onClick={() => setExpanded(false)}
            className="mt-1 w-full text-center text-xs text-primary-400 hover:text-primary-300 transition-colors"
          >
            收起
          </button>
        )}
      </div>
    </div>
  );
}
