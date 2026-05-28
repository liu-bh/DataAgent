import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import AdminLayout from '@/components/Layout/AdminLayout';

/** 懒加载页面组件 */
const DashboardPage = lazy(() => import('@/pages/Dashboard'));
const AnalyticsPage = lazy(() => import('@/pages/Analytics'));
const DataSourcesPage = lazy(() => import('@/pages/DataSources'));
const SemanticModelsPage = lazy(() => import('@/pages/SemanticModels'));
const SemanticModelDetailPage = lazy(() => import('@/pages/SemanticModels/DetailPage'));
const MetricsPage = lazy(() => import('@/pages/Metrics'));
const DimensionsPage = lazy(() => import('@/pages/Dimensions'));
const SessionsPage = lazy(() => import('@/pages/Sessions'));
const UsersPage = lazy(() => import('@/pages/Users'));

/** 路由配置 */
export const router = createBrowserRouter([
  {
    path: '/admin',
    element: <AdminLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/admin/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: <DashboardPage />,
      },
      {
        path: 'analytics',
        element: <AnalyticsPage />,
      },
      {
        path: 'data-sources',
        element: <DataSourcesPage />,
      },
      {
        path: 'semantic-models',
        children: [
          {
            index: true,
            element: <SemanticModelsPage />,
          },
          {
            path: ':id',
            element: <SemanticModelDetailPage />,
          },
        ],
      },
      {
        path: 'metrics',
        element: <MetricsPage />,
      },
      {
        path: 'dimensions',
        element: <DimensionsPage />,
      },
      {
        path: 'sessions',
        element: <SessionsPage />,
      },
      {
        path: 'users',
        element: <UsersPage />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/admin" replace />,
  },
]);
