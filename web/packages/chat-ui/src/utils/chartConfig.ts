import type { EChartsOption } from 'echarts';

// ==================== 类型定义 ====================

/** 图表数据列 */
export interface ChartColumn {
  name: string;
  type: 'number' | 'string' | 'date';
  values: unknown[];
}

/** 支持的图表类型 */
export type ChartType = 'line' | 'bar' | 'pie' | 'table';

/** 深色主题配色方案 */
const DARK_COLORS = [
  '#6366f1', // indigo-500
  '#22d3ee', // cyan-400
  '#f59e0b', // amber-500
  '#10b981', // emerald-500
  '#f43f5e', // rose-500
  '#8b5cf6', // violet-500
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
  '#14b8a6', // teal-500
  '#e879f9', // fuchsia-400
];

// ==================== 工具函数 ====================

/** ISO 日期字符串正则 */
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}/;

/** 判断值是否为数字（排除 null/undefined/空字符串） */
function isNumericValue(v: unknown): v is number {
  return typeof v === 'number' && !Number.isNaN(v);
}

/** 判断值是否为日期字符串 */
function isDateValue(v: unknown): boolean {
  if (typeof v !== 'string') return false;
  return ISO_DATE_RE.test(v);
}

/** 检测列数据类型 */
function detectColumnType(values: unknown[]): 'number' | 'string' | 'date' {
  // 从非空值中取样
  const sample = values.filter((v) => v !== null && v !== undefined).slice(0, 20);
  if (sample.length === 0) return 'string';

  const numericCount = sample.filter(isNumericValue).length;
  const dateCount = sample.filter(isDateValue).length;

  if (numericCount / sample.length >= 0.8) return 'number';
  if (dateCount / sample.length >= 0.8) return 'date';
  return 'string';
}

/** 将列名数组 + 行数据转换为 ChartColumn 数组 */
export function parseColumns(
  columnNames: string[],
  rows: Record<string, unknown>[],
): ChartColumn[] {
  return columnNames.map((name) => ({
    name,
    type: detectColumnType(rows.map((row) => row[name])),
    values: rows.map((row) => row[name]),
  }));
}

// ==================== 图表类型推断 ====================

/**
 * 推断图表类型：根据数据列特征自动选择最佳图表
 * - 时间列 + 数值列 -> 折线图
 * - 维度列 + 数值列 -> 柱状图
 * - 少量维度(<=8) + 单数值列 -> 饼图
 * - 其他 -> 表格
 */
export function inferChartType(columns: ChartColumn[]): ChartType {
  if (columns.length === 0) return 'table';

  const stringCols = columns.filter((c) => c.type === 'string');
  const dateCols = columns.filter((c) => c.type === 'date');
  const numberCols = columns.filter((c) => c.type === 'number');

  // 无数值列，无法画图
  if (numberCols.length === 0) return 'table';

  // 时间列 + 数值列 -> 折线图
  if (dateCols.length > 0 && numberCols.length > 0) {
    return 'line';
  }

  // 单数值列 + 少量维度(<=8) -> 饼图
  if (
    numberCols.length === 1 &&
    stringCols.length === 1 &&
    stringCols[0]!.values.filter((v) => v !== null && v !== undefined).length <= 8
  ) {
    return 'pie';
  }

  // 维度列 + 数值列 -> 柱状图
  if (stringCols.length > 0 && numberCols.length > 0) {
    return 'bar';
  }

  // 多数值列无维度 -> 默认表格
  return 'table';
}

// ==================== ECharts 配置生成器 ====================

/** 深色主题通用配置 */
function darkThemeBase(): EChartsOption {
  return {
    backgroundColor: 'transparent',
    textStyle: {
      color: '#9ca3af', // gray-400
    },
    legend: {
      textStyle: {
        color: '#9ca3af',
      },
    },
  };
}

/**
 * 生成折线图 ECharts 配置
 */
export function lineChartOption(
  xAxis: string[],
  series: { name: string; data: number[] }[],
): EChartsOption {
  return {
    ...darkThemeBase(),
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937', // gray-800
      borderColor: '#374151', // gray-700
      textStyle: { color: '#e5e7eb' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: xAxis,
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af' },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#374151', type: 'dashed' } },
    },
    series: series.map((s, idx) => ({
      name: s.name,
      type: 'line' as const,
      data: s.data,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2 },
      itemStyle: { color: DARK_COLORS[idx % DARK_COLORS.length] ?? '#6366f1' },
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: (DARK_COLORS[idx % DARK_COLORS.length] ?? '#6366f1') + '40' },
            { offset: 1, color: (DARK_COLORS[idx % DARK_COLORS.length] ?? '#6366f1') + '05' },
          ],
        },
      },
    })),
  };
}

/**
 * 生成柱状图 ECharts 配置
 */
export function barChartOption(
  xAxis: string[],
  series: { name: string; data: number[] }[],
): EChartsOption {
  return {
    ...darkThemeBase(),
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      axisPointer: { type: 'shadow' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: xAxis,
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisLabel: { color: '#9ca3af', rotate: xAxis.length > 6 ? 30 : 0 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#9ca3af' },
      splitLine: { lineStyle: { color: '#374151', type: 'dashed' } },
    },
    series: series.map((s, idx) => ({
      name: s.name,
      type: 'bar' as const,
      data: s.data,
      barMaxWidth: 48,
      itemStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: DARK_COLORS[idx % DARK_COLORS.length] ?? '#6366f1' },
            { offset: 1, color: (DARK_COLORS[idx % DARK_COLORS.length] ?? '#6366f1') + '80' },
          ],
        },
        borderRadius: [4, 4, 0, 0],
      },
    })),
  };
}

/**
 * 生成饼图 ECharts 配置
 */
export function pieChartOption(
  data: { name: string; value: number }[],
): EChartsOption {
  return {
    ...darkThemeBase(),
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb' },
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'horizontal',
      bottom: 0,
      textStyle: { color: '#9ca3af', fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderColor: '#1f2937',
          borderWidth: 2,
        },
        label: {
          color: '#d1d5db',
          fontSize: 11,
        },
        labelLine: {
          lineStyle: { color: '#4b5563' },
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
        data: data.map((item, idx) => ({
          name: item.name,
          value: item.value,
          itemStyle: { color: DARK_COLORS[idx % DARK_COLORS.length] },
        })),
      },
    ],
  };
}

/**
 * 根据图表类型和数据列生成 ECharts 配置
 */
export function generateChartOption(
  type: ChartType,
  columns: ChartColumn[],
  _title?: string,
): EChartsOption {
  if (type === 'table' || columns.length === 0) {
    return {};
  }

  const stringCols = columns.filter((c) => c.type === 'string' || c.type === 'date');
  const numberCols = columns.filter((c) => c.type === 'number');

  if (stringCols.length === 0 || numberCols.length === 0) {
    return {};
  }

  // X 轴使用第一个维度列（字符串或日期）
  const xCol = stringCols[0]!;
  const xAxisData = xCol.values.map((v) => String(v ?? ''));

  if (type === 'pie') {
    // 饼图只需要一组数据：维度名称 + 第一个数值列
    const numCol = numberCols[0]!;
    const pieData = xAxisData
      .map((name, idx) => ({
        name,
        value: isNumericValue(numCol.values[idx]) ? numCol.values[idx] : 0,
      }))
      .filter((d) => d.value !== 0);
    return pieChartOption(pieData);
  }

  // 折线图 / 柱状图：每个数值列作为一个系列
  const series = numberCols.map((col) => ({
    name: col.name,
    data: col.values.map((v) => (isNumericValue(v) ? v : 0)),
  }));

  if (type === 'line') {
    return lineChartOption(xAxisData, series);
  }

  return barChartOption(xAxisData, series);
}
