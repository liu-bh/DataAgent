import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Loading from '@/components/Loading';

const Login = lazy(() => import('@/pages/Login'));
const Chat = lazy(() => import('@/pages/Chat'));
const Settings = lazy(() => import('@/pages/Settings'));

function SuspenseWrapper({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<Loading />}>{children}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <SuspenseWrapper>
        <Login />
      </SuspenseWrapper>
    ),
  },
  {
    path: '/chat',
    element: (
      <SuspenseWrapper>
        <Chat />
      </SuspenseWrapper>
    ),
  },
  {
    path: '/chat/:sessionId',
    element: (
      <SuspenseWrapper>
        <Chat />
      </SuspenseWrapper>
    ),
  },
  {
    path: '/settings',
    element: (
      <SuspenseWrapper>
        <Settings />
      </SuspenseWrapper>
    ),
  },
  {
    path: '/',
    element: <Navigate to="/chat" replace />,
  },
  {
    path: '*',
    element: <Navigate to="/chat" replace />,
  },
]);
