import { useEffect, useRef, useState } from 'react'
import { buttonClasses } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { cx } from '@/lib/cx'
import { SIDO, SIGUNGU } from '@/lib/regions'
import { TOP_CARD, TOP_CARD_TITLE } from './topCard'
import type { BizStage, UserProfile } from '@/services/supportMatch/types'

type Props = {
  /** 사용자가 입력한 문장. 칩 아래에 원문으로 보여준다 */
  text: string
  profile: UserProfile
  missing: (keyof UserProfile)[]
  disabled?: boolean
  /** "저장" 시 바뀐 항목을 한 번에 넘긴다 (지역은 시도·시군구 함께) */
  onOverride: (patch: Partial<Record<keyof UserProfile, unknown>>) => void
}

const BIZ_STAGES: BizStage[] = ['예비창업', '업력3년이하', '업력7년이하', '기창업']

type FieldKey = 'age' | 'sido' | 'bizStage' | 'industryCategory'
const FIELDS: FieldKey[] = ['age', 'sido', 'bizStage', 'industryCategory']
const FIELD_LABEL: Record<FieldKey, string> = {
  age: '나이',
  sido: '지역',
  bizStage: '창업 단계',
  industryCategory: '업종',
}
const INDUSTRY = ['카페', '음식점', '소매', '서비스', '기타']

/** 칩으로 고칠 수 있는 값. 지역은 시도·시군구 두 개 */
type Values = {
  age: number | null
  sido: string | null
  sigungu: string | null
  bizStage: string | null
  industryCategory: string | null
}

const chipBase =
  'inline-flex min-h-10 items-center gap-1.5 rounded-chip border px-3.5 text-[13px] font-semibold transition-colors'
// 누를 수 있는 칩: hover 진하게, 키보드 포커스 링
const chipAction =
  'cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500 disabled:cursor-default disabled:opacity-50'
const inputCls =
  'h-10 rounded-input border border-line bg-surface px-3 text-sm text-ink-soft'
// 숫자 입력칸은 마우스 클릭에도 :focus-visible 이 걸려 전역 외곽선(index.css, 레이어 밖이라 ! 로만 덮인다)이 생긴다.
// 편집칸 자체가 편집 위치를 보여주므로 외곽선을 끈다. select 는 키보드로 옮길 때만 전역 외곽선이 나온다
const numberInputCls = cx(inputCls, 'w-24 outline-none!')

const shortSido = (s: string) => s.replace(/(특별시|광역시|특별자치시|특별자치도)$/, '')

/** 추출 결과를 칩으로 보여준다. 칩을 눌러 그 자리에서 고치고, "저장"을 누르면 바뀐 값을 한 번에 overrides 로 재요청한다 */
export function ProfileChips({ text, profile, missing, disabled, onOverride }: Props) {
  const saved: Values = {
    age: profile.age.value,
    sido: profile.sido.value,
    sigungu: profile.sigungu.value,
    bizStage: profile.bizStage.value,
    industryCategory: profile.industryCategory.value,
  }
  // 저장 전 변경값. 저장하면 비우고, 재판정 결과의 profile 이 새 값이 된다
  const [pending, setPending] = useState<Partial<Values>>({})
  const [editing, setEditing] = useState<FieldKey | null>(null)
  const editorRef = useRef<HTMLSpanElement>(null)
  // 시군구 목록. 기본 select 는 브라우저·화면 위치에 따라 위로 열리므로 항상 아래로 펼치는 목록을 쓴다
  const [guOpen, setGuOpen] = useState(false)

  const v: Values = { ...saved, ...pending }
  const changed = (Object.keys(pending) as (keyof Values)[]).filter((k) => pending[k] !== saved[k])
  const set = (patch: Partial<Values>) => setPending((p) => ({ ...p, ...patch }))

  // 편집 중인 칩은 Esc 또는 바깥 클릭으로 닫는다 (고친 값은 저장 전까지 유지)
  useEffect(() => {
    setGuOpen(false)
    if (!editing) return
    const onDown = (e: MouseEvent) => {
      if (!editorRef.current?.contains(e.target as Node)) setEditing(null)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setEditing(null)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [editing])

  const display: Record<FieldKey, string | null> = {
    age: v.age != null ? `${v.age}세` : null,
    sido: v.sido ? [shortSido(v.sido), v.sigungu].filter(Boolean).join(' ') : null,
    bizStage: v.bizStage,
    industryCategory: v.industryCategory,
  }

  const save = () => {
    if (!changed.length) return
    onOverride(Object.fromEntries(changed.map((k) => [k, v[k]])))
    setPending({})
    setEditing(null)
  }

  const editor = (k: FieldKey) => {
    if (k === 'age')
      return (
        <input
          autoFocus
          type="number"
          min={14}
          max={100}
          value={v.age ?? ''}
          onChange={(e) => set({ age: e.target.value ? Number(e.target.value) : saved.age })}
          onKeyDown={(e) => e.key === 'Enter' && setEditing(null)}
          aria-label={FIELD_LABEL.age}
          className={numberInputCls}
        />
      )
    if (k === 'sido') {
      const sido = v.sido ?? ''
      const gu = v.sigungu && SIGUNGU[sido]?.includes(v.sigungu) ? v.sigungu : ''
      return (
        <>
          <select
            autoFocus
            value={sido}
            // 시도를 바꾸면 시군구는 시도 전체로 되돌린다
            onChange={(e) => {
              set({ sido: e.target.value, sigungu: null })
              // 시도를 고른 직후 시군구 목록을 바로 펼친다
              setGuOpen(true)
            }}
            aria-label="시도"
            className={inputCls}
          >
            {!sido && <option value="">시도 선택</option>}
            {SIDO.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          {!!SIGUNGU[sido]?.length && (
            <span className="relative">
              <button
                type="button"
                aria-haspopup="listbox"
                aria-expanded={guOpen}
                aria-label={`시군구 ${gu || '전체'}`}
                onClick={() => setGuOpen((o) => !o)}
                className={cx(inputCls, 'inline-flex items-center gap-1.5')}
              >
                {gu || '시군구 전체'}
                <Icon name="chevron-down" size={14} className="text-faint" />
              </button>
              {guOpen && (
                <ul
                  role="listbox"
                  aria-label="시군구"
                  className="absolute top-full left-0 z-20 mt-1 max-h-64 min-w-full overflow-y-auto rounded-input border border-line bg-surface py-1 shadow-card"
                >
                  {['', ...SIGUNGU[sido]].map((g) => (
                    <li key={g || 'all'} role="option" aria-selected={g === gu}>
                      <button
                        type="button"
                        onClick={() => {
                          set({ sido, sigungu: g || null })
                          setGuOpen(false)
                        }}
                        className={cx(
                          'flex min-h-10 w-full items-center px-3 text-left text-sm whitespace-nowrap hover:bg-primary-50',
                          g === gu ? 'font-semibold text-primary-700' : 'text-ink-soft',
                        )}
                      >
                        {g || '시군구 전체'}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </span>
          )}
        </>
      )
    }
    const options = k === 'bizStage' ? BIZ_STAGES : INDUSTRY
    return (
      <select
        autoFocus
        value={v[k] ?? ''}
        onChange={(e) => set({ [k]: e.target.value })}
        aria-label={FIELD_LABEL[k]}
        className={inputCls}
      >
        {!v[k] && <option value="">{FIELD_LABEL[k]} 선택</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    )
  }

  return (
    <section aria-labelledby="profile-chips-title" className={TOP_CARD}>
      <div className="flex items-center justify-between gap-3">
        <h2 id="profile-chips-title" className={TOP_CARD_TITLE}>
          <Icon name="user" size={16} className="text-faint" />
          이렇게 이해했어요
        </h2>
        {/* 바뀐 값이 없으면 연한 톤으로 비활성 */}
        <button
          type="button"
          disabled={disabled || changed.length === 0}
          onClick={save}
          className={buttonClasses('primary', 'md', '-my-2 disabled:bg-bg-soft disabled:text-faint disabled:opacity-100')}
        >
          저장
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {FIELDS.map((k) => {
          const val = display[k]
          if (editing === k) {
            // 편집 중: 테두리는 칩과 같은 1px·같은 색, 배경만 한 단계 진하게
            return (
              <span
                key={k}
                ref={editorRef}
                className="inline-flex flex-wrap items-center gap-1.5 rounded-panel border border-primary-100 bg-primary-100 p-1"
              >
                <span className="px-1.5 text-[13px] font-medium text-muted">{FIELD_LABEL[k]}</span>
                {editor(k)}
              </span>
            )
          }
          // 저장 전 바뀐 칩은 테두리를 진하게
          const isChanged = changed.includes(k) || (k === 'sido' && changed.includes('sigungu'))
          return val ? (
            <button
              key={k}
              type="button"
              disabled={disabled}
              onClick={() => setEditing(k)}
              aria-label={`${FIELD_LABEL[k]} ${val}${isChanged ? ' (저장 전)' : ''}, 눌러서 수정`}
              className={cx(
                chipBase,
                chipAction,
                'bg-primary-50 text-primary-700 hover:border-primary-400 hover:bg-primary-100',
                isChanged ? 'border-primary-400' : 'border-primary-100',
              )}
            >
              <span className="font-medium text-muted">{FIELD_LABEL[k]}</span>
              {val}
              <Icon name="pencil" size={12} />
            </button>
          ) : (
            <button
              key={k}
              type="button"
              disabled={disabled}
              onClick={() => setEditing(k)}
              aria-label={`${FIELD_LABEL[k]} 확인 필요, 눌러서 입력`}
              className={cx(chipBase, chipAction, 'border-dashed border-warn bg-warn-soft text-warn hover:bg-surface')}
            >
              <span className="font-medium">{FIELD_LABEL[k]}</span>
              확인 필요
              {missing.includes(k) && <span className="sr-only"> (정확한 판정에 필요)</span>}
              <Icon name="pencil" size={12} />
            </button>
          )
        })}
      </div>

      {/* 원문 인용 (항상 전체 표시) */}
      <p className="mt-4 border-t border-line pt-4 text-sm leading-[1.6] text-muted">&ldquo;{text}&rdquo;</p>
    </section>
  )
}
