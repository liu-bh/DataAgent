import { useState } from 'react';

interface OnboardingGuideProps {
  /** 引导完成回调 */
  onComplete: () => void;
  /** 点击示例查询发送 */
  onSendExample: (question: string) => void;
}

/** 引导示例查询 */
const EXAMPLE_QUERIES = [
  '上个月各城市的销售额是多少？',
  '统计本季度用户注册趋势',
  '哪些产品库存低于安全库存？',
];

/** localStorage 存储 key */
const ONBOARDING_STORAGE_KEY = 'datapilot_onboarding_completed';

/** 总步骤数 */
const TOTAL_STEPS = 3;

/**
 * 新手引导组件 —— 步骤式引导，帮助用户快速上手
 */
export default function OnboardingGuide({
  onComplete,
  onSendExample,
}: OnboardingGuideProps) {
  const [currentStep, setCurrentStep] = useState(1);

  /** 完成引导并记录到 localStorage */
  const handleComplete = () => {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, 'true');
    onComplete();
  };

  /** 跳过引导 */
  const handleSkip = () => {
    handleComplete();
  };

  /** 下一步 */
  const handleNext = () => {
    if (currentStep < TOTAL_STEPS) {
      setCurrentStep((prev) => prev + 1);
    } else {
      handleComplete();
    }
  };

  /** 点击示例查询后完成引导 */
  const handleExampleClick = (question: string) => {
    onSendExample(question);
    handleComplete();
  };

  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/95 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-8 shadow-xl">
        {/* 步骤指示器 */}
        <div className="mb-8 flex items-center justify-center gap-2">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => (
            <div
              key={i}
              className={`h-2 rounded-full transition-all duration-300 ${
                i + 1 <= currentStep
                  ? 'w-8 bg-primary-500'
                  : 'w-2 bg-gray-200'
              }`}
            />
          ))}
        </div>

        {/* Step 1: 欢迎语 */}
        {currentStep === 1 && (
          <div className="animate-fadeIn text-center">
            {/* 欢迎图标 */}
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-primary-100">
              <svg
                className="h-8 w-8 text-primary-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"
                />
              </svg>
            </div>
            <h2 className="mb-3 text-xl font-semibold text-gray-900">
              欢迎使用 DataPilot 数据助手
            </h2>
            <p className="text-sm leading-relaxed text-gray-500">
              DataPilot 可以帮您用自然语言查询数据，自动生成 SQL
              并以可视化图表呈现结果。让我们快速了解一下吧！
            </p>
          </div>
        )}

        {/* Step 2: 示例查询 */}
        {currentStep === 2 && (
          <div className="animate-fadeIn">
            <h3 className="mb-2 text-center text-lg font-semibold text-gray-900">
              试试用自然语言提问
            </h3>
            <p className="mb-5 text-center text-sm text-gray-500">
              点击下方示例快速体验，或直接在输入框中输入您的问题
            </p>
            <div className="space-y-3">
              {EXAMPLE_QUERIES.map((query, index) => (
                <button
                  key={index}
                  onClick={() => handleExampleClick(query)}
                  className="flex w-full items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-600 transition-all duration-200 hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700"
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-xs font-medium text-gray-500">
                    {index + 1}
                  </span>
                  <span className="flex-1">{query}</span>
                  <svg
                    className="h-4 w-4 text-gray-300"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                    />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: 查看语义模型 */}
        {currentStep === 3 && (
          <div className="animate-fadeIn text-center">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <svg
                className="h-8 w-8 text-green-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125"
                />
              </svg>
            </div>
            <h3 className="mb-3 text-lg font-semibold text-gray-900">
              查看语义模型了解可用数据
            </h3>
            <p className="mb-6 text-sm leading-relaxed text-gray-500">
              语义模型定义了您可以查询的数据表、指标和维度。
              <br />
              了解这些信息可以帮助您更准确地提问。
            </p>

            {/* 功能亮点 */}
            <div className="mb-6 grid grid-cols-3 gap-3">
              {[
                { icon: 'M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z', label: '可视化图表' },
                { icon: 'M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z', label: '安全可控' },
                { icon: 'M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5', label: '智能分析' },
              ].map((feature, index) => (
                <div
                  key={index}
                  className="flex flex-col items-center rounded-xl bg-gray-50 px-3 py-4"
                >
                  <svg
                    className="mb-2 h-6 w-6 text-primary-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d={feature.icon}
                    />
                  </svg>
                  <span className="text-xs font-medium text-gray-600">
                    {feature.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 底部操作区 */}
        <div className="mt-8 flex items-center justify-between">
          <button
            onClick={handleSkip}
            className="text-sm text-gray-400 transition-colors hover:text-gray-600"
          >
            跳过引导
          </button>
          <button
            onClick={handleNext}
            className="rounded-xl bg-primary-600 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-700"
          >
            {currentStep < TOTAL_STEPS ? '下一步' : '开始使用'}
          </button>
        </div>
      </div>
    </div>
  );
}
