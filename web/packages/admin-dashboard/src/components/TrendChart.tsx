import { useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  ToolboxComponent,
  DataZoomComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { TrendDataPoint } from '@/types/dashboard';

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  ToolboxComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

/** 趋势图表 Props */
interface TrendChartProps {
  /** 趋势数据 */
  data: TrendDataPoint[];
  /** 图表高度 */
  height?: string;
}

/** ECharts 深色主题色板 */
const COLORS = {
  queries: '#3B82F6',   // 蓝色 — 查询次数
  accuracy: '#10B981',  // 绿色 — 准确率
  errors: '#EF4444',    // 红色 — 错误数
};

export default function TrendChart({ data, height = '380px' }: TrendChartProps) {
  const option = useMemo(() => ({
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      textStyle: { color: '#374151', fontSize: 13 },
      axisPointer: {
        type: 'cross' as const,
        crossStyle: { color: '#999' },
      },
    },
    legend: {
      data: ['查询次数', '准确率 (%)', '错误数'],
      top: 0,
      textStyle: { color: '#6B7280' },
    },
    toolbox: {
      feature: {
        dataZoom: { yAxisIndex: 'none' as const },
        restore: {},
        saveAsImage: {},
      },
      right: 0,
      top: -4,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '12%',
      top: '14%',
      containLabel: true,
    },
    dataZoom: [
      {
        type: 'inside' as const,
        start: 0,
        end: 100,
      },
      {
        start: 0,
        end: 100,
        height: 24,
        bottom: 4,
      },
    ],
    xAxis: {
      type: 'category' as const,
      data: data.map((d) => d.date),
      axisLabel: {
        color: '#9CA3AF',
        formatter: (value: string) => {
          // 只显示月-日
          return value.slice(5);
        },
      },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value' as const,
        name: '次数',
        nameTextStyle: { color: '#9CA3AF', fontSize: 12 },
        position: 'left' as const,
        axisLabel: { color: '#9CA3AF' },
        splitLine: { lineStyle: { color: '#F3F4F6' } },
      },
      {
        type: 'value' as const,
        name: '百分比 (%)',
        nameTextStyle: { color: '#9CA3AF', fontSize: 12 },
        position: 'right' as const,
        axisLabel: { color: '#9CA3AF', formatter: '{value}%' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '查询次数',
        type: 'line',
        yAxisIndex: 0,
        data: data.map((d) => d.queries),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: COLORS.queries },
        itemStyle: { color: COLORS.queries },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.15)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.01)' },
          ]),
        },
      },
      {
        name: '准确率 (%)',
        type: 'line',
        yAxisIndex: 1,
        data: data.map((d) => d.accuracy),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: COLORS.accuracy },
        itemStyle: { color: COLORS.accuracy },
      },
      {
        name: '错误数',
        type: 'line',
        yAxisIndex: 0,
        data: data.map((d) => d.errors),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: COLORS.errors, type: 'dashed' },
        itemStyle: { color: COLORS.errors },
      },
    ],
  }), [data]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-base font-semibold text-gray-800">趋势分析</h3>
      <ReactEChartsCore
        echarts={echarts}
        option={option}
        style={{ height, width: '100%' }}
        notMerge
      />
    </div>
  );
}
