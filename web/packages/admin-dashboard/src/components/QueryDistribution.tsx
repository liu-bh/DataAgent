import { useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { PieChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { QueryDistribution } from '@/types/dashboard';

echarts.use([
  PieChart,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
]);

/** 查询类型分布中文映射 */
const TYPE_LABELS: Record<string, string> = {
  sql_query: 'SQL 查询',
  chitchat: '闲聊',
  out_of_scope: '超出范围',
};

/** 查询类型颜色 */
const TYPE_COLORS: Record<string, string> = {
  sql_query: '#3B82F6',
  chitchat: '#F59E0B',
  out_of_scope: '#EF4444',
};

/** 查询类型分布饼图 Props */
interface QueryDistributionChartProps {
  /** 分布数据 */
  data: QueryDistribution[];
  /** 图表高度 */
  height?: string;
}

export default function QueryDistributionChart({ data, height = '320px' }: QueryDistributionChartProps) {
  const option = useMemo(() => ({
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#E5E7EB',
      borderWidth: 1,
      textStyle: { color: '#374151', fontSize: 13 },
      formatter: (params: { name: string; value: number; percent: number }) => {
        return `<strong>${params.name}</strong><br/>数量: ${params.value}<br/>占比: ${params.percent}%`;
      },
    },
    legend: {
      orient: 'vertical' as const,
      right: '5%',
      top: 'center',
      textStyle: { color: '#6B7280', fontSize: 13 },
      itemGap: 16,
    },
    color: data.map((d) => TYPE_COLORS[d.type] ?? '#9CA3AF'),
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold' as const,
            color: '#374151',
          },
        },
        labelLine: {
          show: false,
        },
        data: data.map((d) => ({
          name: TYPE_LABELS[d.type] ?? d.type,
          value: d.count,
        })),
      },
    ],
  }), [data]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-base font-semibold text-gray-800">查询类型分布</h3>
      <ReactEChartsCore
        echarts={echarts}
        option={option}
        style={{ height, width: '100%' }}
        notMerge
      />
    </div>
  );
}
