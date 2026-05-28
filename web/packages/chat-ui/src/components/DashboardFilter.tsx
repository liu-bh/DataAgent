import { useState } from 'react';
import type { DashboardFilter as DashboardFilterType } from '@/types/dashboard';

interface DashboardFilterBarProps {
  filters: DashboardFilterType[];
  /** 过滤器值变更回调 */
  onFilterChange?: (filterId: string, value: string | string[]) => void;
}

/**
 * Dashboard 过滤器组件
 * 支持 time_range / select / multi_select 三种类型
 */
export default function DashboardFilterBar({
  filters,
  onFilterChange,
}: DashboardFilterBarProps) {
  if (filters.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
      {/* 过滤器图标 */}
      <div className="flex items-center gap-1.5 text-gray-400">
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z"
          />
        </svg>
        <span className="text-xs font-medium">筛选</span>
      </div>

      {filters.map((filter) => (
        <FilterItem
          key={filter.filter_id}
          filter={filter}
          onFilterChange={onFilterChange}
        />
      ))}
    </div>
  );
}

/** 单个过滤器项 */
function FilterItem({
  filter,
  onFilterChange,
}: {
  filter: DashboardFilterType;
  onFilterChange?: (filterId: string, value: string | string[]) => void;
}) {
  const [value, setValue] = useState<string | string[]>(
    filter.default_value ?? '',
  );
  const [multiValues, setMultiValues] = useState<string[]>(
    Array.isArray(filter.default_value) ? filter.default_value : [],
  );

  const handleChange = (newValue: string | string[]) => {
    if (filter.filter_type === 'multi_select') {
      setMultiValues(newValue as string[]);
    } else {
      setValue(newValue as string);
    }
    onFilterChange?.(filter.filter_id, newValue);
  };

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-gray-400 whitespace-nowrap">
        {filter.label}
      </label>

      {filter.filter_type === 'time_range' && (
        <input
          type="date"
          value={String(value)}
          onChange={(e) => handleChange(e.target.value)}
          className="rounded-md border border-gray-600 bg-gray-700 px-2.5 py-1.5 text-xs text-gray-200 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
      )}

      {filter.filter_type === 'select' && (
        <select
          value={String(value)}
          onChange={(e) => handleChange(e.target.value)}
          className="rounded-md border border-gray-600 bg-gray-700 px-2.5 py-1.5 text-xs text-gray-200 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        >
          <option value="">全部</option>
          {filter.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      )}

      {filter.filter_type === 'multi_select' && (
        <div className="flex flex-wrap gap-1.5">
          {filter.options.map((opt) => {
            const isChecked = multiValues.includes(opt);
            return (
              <button
                key={opt}
                onClick={() => {
                  const next = isChecked
                    ? multiValues.filter((v) => v !== opt)
                    : [...multiValues, opt];
                  handleChange(next);
                }}
                className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                  isChecked
                    ? 'border-primary-500 bg-primary-500/20 text-primary-300'
                    : 'border-gray-600 bg-gray-700 text-gray-400 hover:border-gray-500'
                }`}
              >
                {opt}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
