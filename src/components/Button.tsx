import type { ButtonHTMLAttributes } from 'react'
import { cx } from '@/lib/cx'
import { Icon, type IconName } from './Icon'

type Variant = 'primary' | 'secondary' | 'ghost'
type Size = 'md' | 'lg'

const VARIANT: Record<Variant, string> = {
  primary: 'bg-primary-500 text-white hover:bg-primary-600 active:bg-primary-700',
  secondary:
    'bg-surface text-ink-soft border border-line-strong hover:bg-bg active:bg-bg-soft',
  ghost: 'text-primary-600 hover:bg-primary-50',
}

const SIZE: Record<Size, string> = {
  md: 'h-10 px-4 text-sm gap-1.5',
  lg: 'h-12 px-6 text-[15px] gap-2',
}

/** <Link> 등에 버튼 스타일만 입힐 때 사용 */
export function buttonClasses(variant: Variant = 'primary', size: Size = 'md', className?: string) {
  return cx(
    'inline-flex items-center justify-center rounded-btn font-semibold transition-colors disabled:opacity-50',
    VARIANT[variant],
    SIZE[size],
    className,
  )
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
  iconRight?: IconName
  iconLeft?: IconName
}

/** 공통 버튼 (DESIGN.md 7) */
export function Button({
  variant = 'primary',
  size = 'md',
  iconRight,
  iconLeft,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button className={buttonClasses(variant, size, className)} {...rest}>
      {iconLeft && <Icon name={iconLeft} size={size === 'lg' ? 18 : 16} />}
      {children}
      {iconRight && <Icon name={iconRight} size={size === 'lg' ? 18 : 16} />}
    </button>
  )
}
