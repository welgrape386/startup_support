import { useState } from 'react'
import { Card } from '@/components/Card'
import { Icon } from '@/components/Icon'
import { SectionTitle } from '@/components/SectionTitle'
import { cx } from '@/lib/cx'
import type { BizStage, UserProfile } from '@/services/supportMatch/types'

type Props = {
  /** 사용자가 입력한 문장. 칩 바로 위에 원문으로 보여준다 */
  text: string
  profile: UserProfile
  missing: (keyof UserProfile)[]
  disabled?: boolean
  /** 펼침 상태는 부모가 가진다 (칩 수정으로 재요청하는 동안 이 카드가 사라졌다 다시 그려져도 유지) */
  open: boolean
  onToggle: () => void
  onOverride: (key: keyof UserProfile, value: unknown) => void
}

const BIZ_STAGES: BizStage[] = ['예비창업', '업력3년이하', '업력7년이하', '기창업']

type FieldKey = 'age' | 'sido' | 'bizStage' | 'industryCategory'
const FIELD_LABEL: Record<FieldKey, string> = {
  age: '나이',
  sido: '지역',
  bizStage: '창업 단계',
  industryCategory: '업종',
}
const SIDO = ['서울특별시', '경기도', '인천광역시', '부산광역시', '대구광역시', '대전광역시', '광주광역시', '울산광역시', '세종특별자치시', '강원특별자치도', '충청북도', '충청남도', '전북특별자치도', '전라남도', '경상북도', '경상남도', '제주특별자치도']
const INDUSTRY = ['카페', '음식점', '소매', '서비스', '기타']

const chipBase =
  'inline-flex min-h-10 items-center gap-1.5 rounded-chip px-3.5 text-[13px] font-semibold transition-colors'
const inputCls =
  'h-10 rounded-input border border-line bg-surface px-3 text-sm text-ink-soft outline-none focus:border-primary-400'

/** 추출 결과를 칩으로 보여주고, 클릭하면 인라인으로 수정해 overrides 로 재요청한다 */
export function ProfileChips({ text, profile, missing, disabled, open: expanded, onToggle, onOverride }: Props) {
  const [editing, setEditing] = useState<FieldKey | null>(null)
  const [draft, setDraft] = useState('')

  const display: Record<FieldKey, string | null> = {
    age: profile.age.value != null ? `${profile.age.value}세` : null,
    sido: profile.sido.value
      ? [profile.sido.value.replace(/(특별시|광역시|특별자치시|특별자치도)$/, ''), profile.sigungu.value]
          .filter(Boolean)
          .join(' ')
      : null,
    bizStage: profile.bizStage.value,
    industryCategory: profile.industryCategory.value,
  }
  const raw: Record<FieldKey, string> = {
    age: profile.age.value?.toString() ?? '',
    sido: profile.sido.value ?? '',
    bizStage: profile.bizStage.value ?? '',
    industryCategory: profile.industryCategory.value ?? '',
  }

  const open = (k: FieldKey) => {
    setEditing(k)
    setDraft(raw[k] || (k === 'bizStage' ? BIZ_STAGES[0] : k === 'sido' ? SIDO[0] : k === 'industryCategory' ? INDUSTRY[0] : ''))
  }
  const commit = () => {
    if (!editing) return
    const v = draft.trim()
    if (v) onOverride(editing, editing === 'age' ? Number(v) : v)
    setEditing(null)
  }

  const gap = profile.fundingGapManwon.value
  const extras: string[] = []
  if (gap != null) extras.push(`자금 ${gap.toLocaleString()}만원`)
  for (const g of profile.targetGroups) extras.push(g)
  for (const n of profile.needs) extras.push(`${n} 필요`)

  return (
    <Card className="flex flex-col gap-3">
      {/* 좁은 화면에서는 배지·버튼이 제목 아래 줄로 내려간다 (제목이 글자 단위로 끊기지 않게) */}
      <SectionTitle
        icon="user"
        className="flex-wrap gap-y-1"
        right={
          <span className="flex shrink-0 items-center gap-2 whitespace-nowrap">
            <button
              type="button"
              aria-expanded={expanded}
              aria-controls="profile-chips-body"
              onClick={onToggle}
              className="inline-flex min-h-10 items-center gap-1 rounded-btn px-2 text-sm font-semibold text-primary-600 hover:bg-primary-50"
            >
              <Icon name={expanded ? 'chevron-down' : 'pencil'} size={14} />
              {expanded ? '접기' : '수정'}
            </button>
          </span>
        }
      >
        이렇게 이해했어요
      </SectionTitle>

      {/* 접힌 상태: 핵심 4항목 한 줄 + 입력 문장 2줄까지 */}
      {!expanded && (
        <p className="text-[15px] font-semibold text-ink">
          {(Object.keys(FIELD_LABEL) as FieldKey[]).map((k) => display[k] ?? `${FIELD_LABEL[k]} 미입력`).join(' · ')}
        </p>
      )}
      <p className={cx('text-sm leading-relaxed text-ink-soft', !expanded && 'line-clamp-2')}>&ldquo;{text}&rdquo;</p>

      {expanded && (
        <div id="profile-chips-body" className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {(Object.keys(FIELD_LABEL) as FieldKey[]).map((k) => {
              const val = display[k]
              if (editing === k) {
                return (
                  <span key={k} className="flex items-center gap-2">
                    {k === 'age' ? (
                      <input
                        autoFocus
                        type="number"
                        min={14}
                        max={100}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && commit()}
                        aria-label={FIELD_LABEL[k]}
                        className={cx(inputCls, 'w-24')}
                      />
                    ) : (
                      <select
                        autoFocus
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        aria-label={FIELD_LABEL[k]}
                        className={inputCls}
                      >
                        {(k === 'bizStage' ? BIZ_STAGES : k === 'sido' ? SIDO : INDUSTRY).map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    )}
                    <button type="button" onClick={commit} className="min-h-10 px-2 text-sm font-semibold text-primary-600">
                      적용
                    </button>
                    <button type="button" onClick={() => setEditing(null)} className="min-h-10 px-1 text-sm text-muted">
                      취소
                    </button>
                  </span>
                )
              }
              return val ? (
                <button
                  key={k}
                  type="button"
                  disabled={disabled}
                  onClick={() => open(k)}
                  aria-label={`${FIELD_LABEL[k]} ${val}, 눌러서 수정`}
                  className={cx(chipBase, 'bg-primary-50 text-primary-700 hover:bg-primary-100 disabled:opacity-50')}
                >
                  {val}
                  <Icon name="pencil" size={12} />
                </button>
              ) : (
                <button
                  key={k}
                  type="button"
                  disabled={disabled}
                  onClick={() => open(k)}
                  className={cx(
                    chipBase,
                    'border border-dashed border-warn text-warn hover:bg-warn-soft disabled:opacity-50',
                  )}
                >
                  <span aria-hidden="true">+</span> {FIELD_LABEL[k]} 알려주기
                  {missing.includes(k) && <span className="sr-only"> (정확한 판정에 필요)</span>}
                </button>
              )
            })}
            {extras.map((e) => (
              <span key={e} className={cx(chipBase, 'bg-bg-soft text-muted')}>
                {e}
              </span>
            ))}
          </div>

          <p className="flex items-center gap-1.5 text-[13px] text-muted">
            <Icon name="info" size={12} />
            칩을 누르면 값을 고쳐서 다시 판정해요. 비어 있는 항목은 자격을 단정하지 않고 &lsquo;확인 필요&rsquo;로
            표시해요.
          </p>
        </div>
      )}
    </Card>
  )
}
