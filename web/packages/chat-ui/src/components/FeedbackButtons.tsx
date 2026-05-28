import { useState, useCallback } from 'react';

interface FeedbackButtonsProps {
  /** 消息 ID */
  messageId: string;
  /** 反馈回调 */
  onFeedback: (
    rating: 'thumbs_up' | 'thumbs_down',
    comment?: string,
  ) => void;
}

export default function FeedbackButtons({
  messageId,
  onFeedback,
}: FeedbackButtonsProps) {
  const [selectedRating, setSelectedRating] = useState<
    'thumbs_up' | 'thumbs_down' | null
  >(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  /** 选择评分 */
  const handleRate = useCallback(
    (rating: 'thumbs_up' | 'thumbs_down') => {
      if (submitted) return;
      setSelectedRating(rating);
      setShowComment(true);
    },
    [submitted],
  );

  /** 提交反馈 */
  const handleSubmit = useCallback(async () => {
    if (!selectedRating) return;
    setIsSubmitting(true);
    try {
      onFeedback(
        selectedRating,
        comment.trim() || undefined,
      );
      setSubmitted(true);
      setShowComment(false);
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedRating, comment, onFeedback]);

  /** 取消选择 */
  const handleCancel = useCallback(() => {
    setSelectedRating(null);
    setShowComment(false);
    setComment('');
  }, []);

  return (
    <div className="flex flex-col gap-2">
      {/* 评分按钮组 */}
      <div className="flex items-center gap-2">
        {!submitted ? (
          <>
            <button
              onClick={() => handleRate('thumbs_up')}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors ${
                selectedRating === 'thumbs_up'
                  ? 'bg-green-50 text-green-600 ring-1 ring-green-300'
                  : 'text-gray-400 hover:bg-gray-50 hover:text-gray-600'
              }`}
              title="有帮助"
            >
              <span role="img" aria-label="thumbs up">
                👍
              </span>
              <span>有帮助</span>
            </button>
            <button
              onClick={() => handleRate('thumbs_down')}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors ${
                selectedRating === 'thumbs_down'
                  ? 'bg-red-50 text-red-600 ring-1 ring-red-300'
                  : 'text-gray-400 hover:bg-gray-50 hover:text-gray-600'
              }`}
              title="没帮助"
            >
              <span role="img" aria-label="thumbs down">
                👎
              </span>
              <span>没帮助</span>
            </button>
          </>
        ) : (
          <span className="flex items-center gap-1 text-xs text-green-600">
            <svg
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
            已反馈
          </span>
        )}
      </div>

      {/* 评论输入区域 */}
      {showComment && !submitted && (
        <div className="space-y-2">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="请输入补充说明（可选）"
            className="w-full resize-none rounded-md border border-gray-200 bg-white px-3 py-2 text-xs text-gray-700 placeholder-gray-400 focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-400"
            rows={3}
            maxLength={500}
          />
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={handleCancel}
              className="rounded-md px-2.5 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="rounded-md bg-primary-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {isSubmitting ? '提交中...' : '提交反馈'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
