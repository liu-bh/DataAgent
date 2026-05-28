import { useState, useMemo } from 'react';
import type { ChartType } from '@/utils/chartConfig';
import { inferChartType, parseColumns } from '@/utils/chartConfig';

interface UseChartTypeResult {
  /** 当前图表类型 */
  chartType: ChartType;
  /** 解析后的图表数据列 */
  chartColumns: ReturnType<typeof parseColumns>;
  /** 手动切换图表类型 */
  setChartType: (type: ChartType) => void;
}

/**
 * 根据查询结果数据推断图表类型
 * 支持用户手动切换图表类型
 */
export function useChartType(
  columns: string[],
  rows: Record<string, unknown>[],
): UseChartTypeResult {
  /** 解析数据列 */
  const parsedColumns = useMemo(() => {
    if (columns.length === 0 || rows.length === 0) return [];
    return parseColumns(columns, rows);
  }, [columns, rows]);

  /** 自动推断的图表类型 */
  const inferredType = useMemo(() => {
    return inferChartType(parsedColumns);
  }, [parsedColumns]);

  /** 手动覆盖的图表类型（null 表示使用推断结果） */
  const [manualType, setManualType] = useState<ChartType | null>(null);

  /** 最终图表类型：手动覆盖优先，否则使用推断结果 */
  const chartType = manualType ?? inferredType;

  /** 手动切换图表类型 */
  const setChartType = (type: ChartType) => {
    setManualType(type);
  };

  return {
    chartType,
    chartColumns: parsedColumns,
    setChartType,
  };
}
