import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-family:var(--font-sans);font-weight:var(--weight-semibold);border:none;cursor:pointer;border-radius:var(--radius-sm);line-height:1;white-space:nowrap;text-decoration:none;transition:background var(--dur-fast) var(--ease-standard),box-shadow var(--dur-fast),transform var(--dur-fast),color var(--dur-fast);}
.li-btn:focus-visible{outline:var(--focus-ring-width) solid var(--focus-ring);outline-offset:2px;}
.li-btn:active{transform:translateY(1px);}
.li-btn__icon{display:inline-flex;align-items:center;justify-content:center;font-size:1.25em;}
.li-btn--sm{padding:7px 14px;font-size:var(--text-sm);}.li-btn--md{padding:10px 18px;font-size:var(--text-sm);}.li-btn--lg{padding:13px 24px;font-size:var(--text-base);}
.li-btn--pill{border-radius:var(--radius-pill);}.li-btn--block{display:flex;width:100%;}
.li-btn--primary{background:var(--primary);color:var(--text-on-primary);}.li-btn--primary:hover{background:var(--primary-hover);}.li-btn--primary:active{background:var(--primary-active);}
.li-btn--secondary{background:var(--surface-card);color:var(--primary);box-shadow:inset 0 0 0 1px var(--border-default);}.li-btn--secondary:hover{background:var(--neutral-50);box-shadow:inset 0 0 0 1px var(--border-strong);}
.li-btn--ghost{background:transparent;color:var(--text-secondary);}.li-btn--ghost:hover{background:var(--neutral-100);color:var(--text-primary);}
.li-btn--danger{background:var(--danger);color:#fff;}.li-btn--danger:hover{filter:brightness(.93);}
.li-btn--success{background:var(--success);color:#fff;}.li-btn--success:hover{filter:brightness(.93);}
.li-btn:disabled{background:var(--neutral-200);color:var(--text-disabled);box-shadow:none;cursor:not-allowed;transform:none;}
`;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success';
  size?: 'sm' | 'md' | 'lg';
  pill?: boolean;
  block?: boolean;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  pill = false,
  block = false,
  startIcon = null,
  endIcon = null,
  disabled = false,
  type = 'button',
  className = '',
  children,
  ...rest
}) => {
  injectOnce('li-button-styles', CSS);

  const classes = [
    'li-btn',
    `li-btn--${variant}`,
    `li-btn--${size}`,
    pill ? 'li-btn--pill' : '',
    block ? 'li-btn--block' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <button type={type} className={classes} disabled={disabled} {...rest}>
      {startIcon ? <span className="li-btn__icon">{startIcon}</span> : null}
      {children ? <span>{children}</span> : null}
      {endIcon ? <span className="li-btn__icon">{endIcon}</span> : null}
    </button>
  );
};
