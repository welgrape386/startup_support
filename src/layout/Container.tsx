import type { HTMLAttributes } from 'react'
import { cx } from '@/lib/cx'

export function Container({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('mx-auto w-full max-w-[1440px] px-5 sm:px-8 lg:px-12', className)} {...rest} />
}
