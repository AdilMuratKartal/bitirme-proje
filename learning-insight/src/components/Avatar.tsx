import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-avatar{display:inline-flex;align-items:center;justify-content:center;border-radius:var(--radius-circle);overflow:hidden;flex-shrink:0;font-family:var(--font-sans);font-weight:var(--weight-bold);color:#fff;background:var(--brand-navy);user-select:none;}
.li-avatar img{width:100%;height:100%;object-fit:cover;display:block;}
.li-avatar--xs{width:24px;height:24px;font-size:10px;}.li-avatar--sm{width:32px;height:32px;font-size:13px;}.li-avatar--md{width:40px;height:40px;font-size:15px;}.li-avatar--lg{width:56px;height:56px;font-size:20px;}.li-avatar--xl{width:96px;height:96px;font-size:34px;}
.li-avatar--ring{box-shadow:0 0 0 3px var(--surface-card),0 0 0 5px var(--brand-sky);}
`;

function avInitials(name: string) {
  if (!name) return '?';
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0])
    .join('')
    .toUpperCase();
}

export interface AvatarProps extends React.HTMLAttributes<HTMLSpanElement> {
  src?: string;
  name?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  ring?: boolean;
  color?: string;
}

export const Avatar: React.FC<AvatarProps> = ({
  src,
  name = '',
  size = 'md',
  ring = false,
  color,
  className = '',
  style = {},
  ...rest
}) => {
  injectOnce('li-avatar-styles', CSS);

  const classes = [
    'li-avatar',
    `li-avatar--${size}`,
    ring ? 'li-avatar--ring' : '',
    className,
  ].filter(Boolean).join(' ');

  const computedStyle = color ? { background: color, ...style } : style;

  return (
    <span className={classes} style={computedStyle} title={name || undefined} {...rest}>
      {src ? <img src={src} alt={name || 'avatar'} /> : avInitials(name)}
    </span>
  );
};
