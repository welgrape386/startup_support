import { NavLink, Outlet } from 'react-router-dom'
import { cx } from '@/lib/cx'
import { Container } from './Container'

const NAV = [
  { to: '/', label: '홈', end: true },
  { to: '/support-match', label: '지원사업 찾기', end: false },
]

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <Container className="flex h-16 items-center justify-between">
          <NavLink to="/" className="text-[17px] font-extrabold tracking-tight text-ink">
            창업지원 매칭
          </NavLink>
          <nav className="flex items-center gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  cx(
                    'rounded-btn px-3.5 py-2 text-sm font-semibold transition-colors',
                    isActive ? 'bg-primary-50 text-primary-600' : 'text-muted hover:text-ink',
                  )
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </Container>
      </header>
      <main className="flex-1 bg-surface">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-surface py-6">
        <Container className="text-[13px] text-muted">
          자격 판정은 공고 문구를 기반으로 한 자동 분석이며, 최종 자격은 공고 기관 심사로 결정됩니다.
        </Container>
      </footer>
    </div>
  )
}
