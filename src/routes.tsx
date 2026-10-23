import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './layout/AppLayout'
import { Home } from './pages/Home'
import { SupportMatch } from './pages/SupportMatch'
import { SupportMatchDetail } from './pages/SupportMatchDetail'
import { SupportMatchResults } from './pages/SupportMatchResults'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'support-match', element: <SupportMatch /> },
      { path: 'support-match/results', element: <SupportMatchResults /> },
      { path: 'support-match/:id', element: <SupportMatchDetail /> },
    ],
  },
])
