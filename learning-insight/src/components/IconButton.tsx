import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-iconbtn{display:inline-flex;align-items:center;justify-content:center;border:none;cursor:pointer;border-radius:var(--radius-circle);background:transparent;color:var(--text-secondary);transition:background var(--dur-fast) var(--ease-standard),color var(--dur-fast);}
.li-iconbtn:hover{background:var(--neutral-100);color:var(--text-primary);}
.li-iconbtn:focus-visible{outline:var(--focus-ring-width) solid var(--focus-ring);outline-offset:2px;}
.li-iconbtn:active{transform:translateY(1px);}
.li-iconbtn--sm{width:32px;height:32px;font-size:18px;}.li-iconbtn--md{width:40px;height:40px;font-size:22px;}.li-iconbtn--lg{width:48px;height:48px;font-size:26px;}
.li-iconbtn--onNav{color:var(--text-on-nav-muted);}.li-iconbtn--onNav:hover{background:rgba(255,255,255,.12);color:#fff;}
.li-iconbtn--solid{background:var(--primary);color:#fff;}.li-iconbtn--solid:hover{background:var(--primary-hover);color:#fff;}
.li-iconbtn:disabled{color:var(--text-disabled);cursor:not-allowed;background:transparent;}
`;

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: 'sm' | 'md' | 'lg';
  tone?: 'default' | 'onNav' | 'solid';
}

export const IconButton: React.FC<IconButtonProps> = ({
  size = 'md',
  tone = 'default',
  disabled = false,
  type = 'button',
  className = '',
  'aria-label': ariaLabel,
  children,
  ...rest
}) => {
  injectOnce('li-iconbutton-styles', CSS);

  const classes = [
    'li-iconbtn',
    `li-iconbtn--${size}`,
    tone === 'onNav' ? 'li-iconbtn--onNav' : '',
    tone === 'solid' ? 'li-iconbtn--solid' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <button type={type} className={classes} disabled={disabled} aria-label={ariaLabel} {...rest}>
      {children}
    </button>
  );
};
