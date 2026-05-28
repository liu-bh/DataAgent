import { useNavigate } from 'react-router-dom';

/**
 * 404 页面
 */
export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="flex h-full flex-col items-center justify-center">
      <h1 className="mb-2 text-6xl font-bold text-gray-600">404</h1>
      <p className="mb-6 text-lg text-gray-400">页面不存在</p>
      <button
        onClick={() => navigate('/')}
        className="rounded-md bg-primary-600 px-6 py-2 text-sm font-medium text-white hover:bg-primary-700"
      >
        返回首页
      </button>
    </div>
  );
}
