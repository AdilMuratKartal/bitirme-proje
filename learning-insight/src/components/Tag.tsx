import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-tag{display:inline-flex;align-items:center;gap:6px;font-family:var(--font-sans);font-weight:var(--weight-semibold);font-size:var(--text-xs);line-height:1;padding:5px 10px;border-radius:var(--radius-pill);white-space:nowrap;}
.li-tag--md{font-size:var(--text-sm);padding:7px 12px;}
.li-tag__dot{width:7px;height:7px;border-radius:50%;background:currentColor;flex-shrink:0;}
.li-tag__icon{display:inline-flex;font-size:1.1em;}
.li-tag--soft{background:color-mix(in srgb, var(--tag-color) 14%, white);color:var(--tag-color);}
.li-tag--solid{background:var(--tag-color);color:#fff;}
.li-tag--outline{background:transparent;color:var(--tag-color);box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--tag-color) 40%, white);}
`;

const TAG_TONE = {
  green: 'var(--cat-green)',
  emerald: 'var(--cat-emerald)',
  sky: 'var(--cat-sky)',
  blue: 'var(--cat-blue)',
  orange: 'var(--cat-orange)',
  amber: 'var(--cat-amber)',
  red: 'var(--cat-red)',
  purple: 'var(--cat-purple)',
  brown: 'var(--cat-brown)',
  gray: 'var(--cat-gray)',
  primary: 'var(--primary)',
  gold: 'var(--gold-500)',
  success: 'var(--success)',
  warning: 'var(--gold-600)',
  danger: 'var(--danger)',
};

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'soft' | 'solid' | 'outline';
  tone?: keyof typeof TAG_TONE | string;
  size?: 'sm' | 'md';
  dot?: boolean;
  icon?: React.ReactNode;
}

export const Tag: React.FC<TagProps> = ({
  variant = 'soft',
  tone = 'primary',
  size = 'sm',
  dot = false,
  icon = null,
  children,
  className = '',
  style = {},
  ...rest
}) => {
  injectOnce('li-tag-styles', CSS);

  const color = TAG_TONE[tone as keyof typeof TAG_TONE] || tone;
  const classes = ['li-tag', `li-tag--${variant}`, `li-tag--${size}`, className]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes} style={{ '--tag-color': color, ...style } as React.CSSProperties} {...rest}>
      {dot ? <span className="li-tag__dot"></span> : null}
      {icon ? <span className="li-tag__icon">{icon}</span> : null}
      {children}
    </span>
  );
};
