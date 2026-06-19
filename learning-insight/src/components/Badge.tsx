import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-badge-root{position:relative;display:inline-flex;}
.li-badge{position:absolute;top:0;right:0;transform:translate(40%,-40%);display:inline-flex;align-items:center;justify-content:center;font-family:var(--font-sans);font-weight:var(--weight-bold);font-size:11px;line-height:1;color:#fff;background:var(--danger);border-radius:var(--radius-pill);min-width:16px;height:16px;padding:0 4px;box-shadow:0 0 0 2px var(--surface-nav);font-variant-numeric:tabular-nums;}
.li-badge--dot{min-width:9px;width:9px;height:9px;padding:0;}
.li-badge--primary{background:var(--primary);}.li-badge--success{background:var(--success);}.li-badge--gold{background:var(--gold-500);}.li-badge--neutral{background:var(--neutral-500);}
`;

export interface BadgeProps extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'content'> {
  content?: string | number;
  max?: number;
  dot?: boolean;
  tone?: 'danger' | 'primary' | 'success' | 'gold' | 'neutral';
  showZero?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  content,
  max = 99,
  dot = false,
  tone = 'danger',
  showZero = false,
  children,
  className = '',
  ...rest
}) => {
  injectOnce('li-badge-styles', CSS);

  const num = typeof content === 'number' ? content : null;
  const hide = !dot && num !== null && num === 0 && !showZero;
  const display = num !== null && num > max ? `${max}+` : content;
  const bc = [
    'li-badge',
    dot ? 'li-badge--dot' : '',
    tone !== 'danger' ? `li-badge--${tone}` : '',
  ].filter(Boolean).join(' ');

  return (
    <span className={`li-badge-root ${className}`} {...rest}>
      {children}
      {hide ? null : <span className={bc}>{dot ? '' : display}</span>}
    </span>
  );
};
