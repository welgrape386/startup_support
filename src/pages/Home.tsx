import { Link } from 'react-router-dom'
import { buttonClasses } from '@/components/Button'
import { Card } from '@/components/Card'
import { Icon, type IconName } from '@/components/Icon'
import { Container } from '@/layout/Container'

// 판정에 쓰는 핵심 항목. 적지 않은 항목은 '확인 필요'로 남는다 (원칙 2)
const TIPS: { icon: IconName; label: string; body: string }[] = [
  { icon: 'user', label: '나이', body: '만 나이로 적어주세요. 청년 지원은 나이 기준이 많아요.' },
  { icon: 'location', label: '지역', body: '사업장(예정지)의 시·도와 구·군까지 적으면 지역 공고를 가려낼 수 있어요.' },
  { icon: 'building', label: '창업 단계', body: '예비창업자인지, 사업자 등록을 했다면 몇 년 됐는지 알려주세요.' },
  { icon: 'won', label: '필요한 지원', body: '자금(융자·보조금·보증), 교육·멘토링, 공간 중 무엇이 필요한지 적어주세요.' },
]

const POINTS: { icon: IconName; title: string; body: string }[] = [
  {
    icon: 'check',
    title: '자격이 되는 공고만 추천해요',
    body: '나이·지역·창업 단계 같은 자격 조건을 공고마다 하나씩 비교해요. 맞지 않는 공고는 이유와 함께 따로 보여드려요.',
  },
  {
    icon: 'search',
    title: '근거는 공고 원문 그대로',
    body: '왜 맞는지를 공고에 적힌 문장으로 보여줘요. 원문에서 확인되지 않는 설명은 화면에 올리지 않아요.',
  },
  {
    icon: 'info',
    title: '모르는 건 확인 필요로',
    body: '문장에 없는 조건은 맞다고 단정하지 않아요. 무엇을 더 확인해야 하는지 알려드려요.',
  },
]

export function Home() {
  return (
    <Container className="flex flex-col gap-14 py-page-y">
      <section className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-24">
        <div className="flex flex-col gap-6">
          <h1 className="text-[34px] leading-[1.18] font-extrabold tracking-tight text-ink sm:text-[46px]">
            내 상황을 적으면,
            <br />
            자격 되는 창업 지원사업만 골라드려요
          </h1>
          <p className="max-w-xl text-[15px] leading-relaxed text-muted sm:text-base">
            정부·지자체 창업 지원사업 공고의 자격 조건을 내 상황과 하나씩 비교해요. 맞는 이유는 공고 원문
            문장으로 보여드려요.
          </p>
          <div>
            <Link to="/support-match" className={buttonClasses('primary', 'lg')}>
              지원사업 찾기
              <Icon name="arrow-right" size={18} />
            </Link>
          </div>
        </div>

        <Card className="flex flex-col gap-4">
          <h2 className="text-[17px] font-bold text-ink">이렇게 적으면 정확해져요</h2>
          <ul className="flex flex-col gap-3.5">
            {TIPS.map((t) => (
              <li key={t.label} className="flex gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-600">
                  <Icon name={t.icon} size={18} />
                </span>
                <span className="flex flex-col gap-0.5">
                  <span className="text-sm font-semibold text-ink">{t.label}</span>
                  <span className="text-[13px] leading-relaxed text-muted">{t.body}</span>
                </span>
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-1.5 rounded-panel bg-bg-soft px-4 py-3 text-[13px] leading-relaxed text-ink-soft">
            <p>
              <span className="font-semibold text-pos">좋은 예</span> &ldquo;27세, 마포구 거주, 사업자등록 전, 디저트 카페
              준비 중&rdquo;
            </p>
            <p>
              <span className="font-semibold text-warn">부족한 예</span> &lsquo;창업 지원 알려줘&rsquo; → 확인 필요가 많이
              나와요
            </p>
          </div>
          <p className="flex items-start gap-1.5 text-[13px] text-muted">
            <Icon name="info" size={12} className="mt-0.5 shrink-0" />
            적지 않은 항목은 자격을 단정하지 않고 &lsquo;확인 필요&rsquo;로 표시해요.
          </p>
        </Card>
      </section>

      <section className="grid gap-8 border-t border-line pt-10 md:grid-cols-3">
        {POINTS.map((p) => (
          <div key={p.title} className="flex flex-col gap-2.5">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-50 text-primary-600">
              <Icon name={p.icon} size={20} />
            </span>
            <h2 className="text-[17px] font-bold text-ink">{p.title}</h2>
            <p className="max-w-sm text-sm leading-relaxed text-muted">{p.body}</p>
          </div>
        ))}
      </section>
    </Container>
  )
}
