// ==================== Dashboard 面板 ====================

/** 面板类型 */
export interface DashboardPanel {
  panel_id: string;
  title: string;
  panel_type: 'chart' | 'table' | 'metric' | 'text';
  width: number;
  height: number;
  chart_spec?: Record<string, unknown>;
  metric_config?: {
    metric: string;
    label: string;
    unit: string;
    trend?: 'up' | 'down' | 'flat';
    value?: number;
    change_percent?: number;
  };
  content?: string;
  position?: { row: number; col: number };
}

// ==================== Dashboard 过滤器 ====================

export interface DashboardFilter {
  filter_id: string;
  field: string;
  label: string;
  filter_type: 'time_range' | 'select' | 'multi_select';
  options: string[];
  default_value?: string | string[];
}

// ==================== Dashboard 布局 ====================

export interface DashboardLayout {
  dashboard_id: string;
  title: string;
  description: string;
  panels: DashboardPanel[];
  filters: DashboardFilter[];
  columns: number;
  created_at: string;
  updated_at: string;
}

// ==================== 图表推荐 ====================

export interface ChartRecommendRequest {
  columns: Array<{ name: string; type: string }>;
  rows: Record<string, unknown>[];
  user_question?: string;
}

export interface ChartRecommendResponse {
  recommended_types: Array<{
    type: string;
    confidence: number;
    title: string;
    description: string;
  }>;
  x_field: string;
  y_fields: string[];
}
