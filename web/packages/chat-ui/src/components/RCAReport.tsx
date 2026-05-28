import { useState } from 'react';
import type { RCAReport } from '@/types/rca';
import DrillDownChart from './DrillDownChart';

interface RCAReportProps {
  report: RCAReport;
}

/** 格式化数字（千分位） */
function formatNumber(value: number): string {
  return value.toLocaleString('zh-CN');
}

/** 格式化百分比 */
function formatPercent(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

/** 获取变化百分比的颜色类名 */
function getChangeColorClass(value: number): string {
  if (value > 0) return 'text-emerald-400';
  if (value < 0) return 'text-red-400';
  return 'text-gray-400';
}

/** 获取变化方向箭头 SVG */
function DirectionArrow({ direction }: { direction: 'up' | 'down' | 'neutral' }) {
  if (direction === 'up') {
    return (
      <svg className="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
      </svg>
    );
  }
  if (direction === 'down') {
    return (
      <svg className="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    );
  }
  return (
    <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
    </svg>
  );
}

/** 置信度指示器 */
function ConfidenceIndicator({ confidence }: { confidence: number }) {
  const percent = Math.round(confidence * 100);
  const colorClass =
    percent >= 80
      ? 'bg-emerald-500'
      : percent >= 60
        ? 'bg-amber-500'
        : 'bg-red-500';

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400">置信度</span>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-gray-700">
        <div
          className={`h-full rounded-full transition-all ${colorClass}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-300">{percent}%</span>
    </div>
  );
}

export default function RCAReportView({ report }: RCAReportProps) {
  const [showDrillDowns, setShowDrillDowns] = useState(false);
  const { anomaly, attribution, drill_downs, summary, execution_time_ms } = report;

  return (
    <div className="space-y-4 rounded-xl border border-gray-700/50 bg-gray-800/50 p-4">
      {/* ========== 顶部：异常概览卡片 ========== */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-gray-200">{anomaly.metric_name}</h4>
            <p className="mt-0.5 text-xs text-gray-500">异常检测结果</p>
          </div>
          <div className="flex items-center gap-2">
            <DirectionArrow direction={anomaly.direction} />
            <span className={`text-2xl font-bold ${getChangeColorClass(anomaly.change_percent)}`}>
              {formatPercent(anomaly.change_percent)}
            </span>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <div className="rounded-md bg-gray-900/50 px-3 py-2">
            <p className="text-xs text-gray-500">当前值</p>
            <p className="text-sm font-semibold text-gray-200">{formatNumber(anomaly.current_value)}</p>
          </div>
          <div className="rounded-md bg-gray-900/50 px-3 py-2">
            <p className="text-xs text-gray-500">基线值</p>
            <p className="text-sm font-semibold text-gray-200">{formatNumber(anomaly.baseline_value)}</p>
          </div>
        </div>

        <div className="mt-2 flex items-center gap-3">
          <ConfidenceIndicator confidence={anomaly.confidence} />
          <span className="text-xs text-gray-500">
            耗时 {execution_time_ms}ms
          </span>
        </div>
      </div>

      {/* ========== 中部：维度贡献度 ========== */}
      <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
        <h4 className="mb-3 text-sm font-semibold text-gray-200">维度贡献度</h4>
        <p className="mb-3 text-xs text-gray-500">
          总变化 {formatPercent(attribution.total_change_percent)}
        </p>
        <div className="space-y-2.5">
          {attribution.dimensions.map((dim) => {
            // 找到最大绝对贡献百分比，用于计算柱状条宽度
            const maxAbsContribution = Math.max(
              ...attribution.dimensions.map((d) => Math.abs(d.contribution_percent)),
            );
            const widthPercent =
              maxAbsContribution > 0
                ? (Math.abs(dim.contribution_percent) / maxAbsContribution) * 100
                : 0;
            const isPositive = dim.contribution_percent >= 0;
            const barColor = isPositive ? 'bg-emerald-500' : 'bg-red-500';

            return (
              <div key={dim.dimension} className="group">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-300">{dim.dimension}</span>
                  <span className={`font-medium ${getChangeColorClass(dim.contribution_percent)}`}>
                    {formatPercent(dim.contribution_percent)}
                  </span>
                </div>
                {/* 水平柱状条 */}
                <div className="mt-1 flex h-2 w-full items-center">
                  {isPositive ? (
                    // 正值向右（绿色）
                    <div
                      className={`h-full rounded-r ${barColor} opacity-70 transition-all group-hover:opacity-100`}
                      style={{ width: `${widthPercent}%` }}
                    />
                  ) : (
                    // 负值向左（红色）：用 flex-end 对齐
                    <div className="flex w-full justify-end">
                      <div
                        className={`h-full rounded-l ${barColor} opacity-70 transition-all group-hover:opacity-100`}
                        style={{ width: `${widthPercent}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ========== 底部：Key Drivers ========== */}
      {attribution.key_drivers.length > 0 && (
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <h4 className="mb-3 text-sm font-semibold text-gray-200">关键驱动因素</h4>
          <div className="flex flex-wrap gap-2">
            {attribution.key_drivers.map((driver, idx) => (
              <span
                key={idx}
                className="inline-flex items-center rounded-full border border-primary-500/30 bg-primary-500/10 px-3 py-1 text-xs font-medium text-primary-300"
              >
                {driver}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ========== 维度下钻（可展开/收起） ========== */}
      {drill_downs.length > 0 && (
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <button
            onClick={() => setShowDrillDowns(!showDrillDowns)}
            className="flex w-full items-center justify-between"
          >
            <h4 className="text-sm font-semibold text-gray-200">维度下钻分析</h4>
            <svg
              className={`h-4 w-4 text-gray-400 transition-transform ${showDrillDowns ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showDrillDowns && (
            <div className="mt-3 space-y-4">
              {drill_downs.map((drillDown) => (
                <DrillDownChart key={drillDown.dimension_name} drillDown={drillDown} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========== 自然语言总结 ========== */}
      {summary && (
        <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
          <h4 className="mb-2 text-sm font-semibold text-gray-200">分析总结</h4>
          <p className="text-xs leading-relaxed text-gray-400">{summary}</p>
        </div>
      )}
    </div>
  );
}
