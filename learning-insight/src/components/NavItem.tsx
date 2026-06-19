import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-navitem{display:flex;align-items:center;gap:14px;width:100%;font-family:var(--font-sans);font-size:var(--text-base);font-weight:var(--weight-medium);color:var(--text-on-nav);background:transparent;border:none;cursor:pointer;text-align:left;text-decoration:none;border-radius:var(--radius-sm);padding:10px 14px;min-height:48px;transition:background var(--dur-fast),color var(--dur-fast);box-sizing:border-box;}
.li-navitem .material-icons{font-size:24px;flex-shrink:0;color:#ECF0F1;transition:color var(--dur-fast);}
.li-navitem:hover{background:rgba(255,255,255,.08);}
.li-navitem--collapsed{flex-direction:column;gap:5px;justify-content:center;padding:10px 4px;font-size:var(--text-xs);text-align:center;line-height:1.15;}
.li-navitem--selected{background:rgba(0,123,255,.16);color:var(--brand-sky);}
.li-navitem--selected .material-icons{color:var(--brand-sky);}
.li-navitem__label{min-width:0;overflow-wrap:anywhere;}
`;

export interface NavItemProps {
  icon: string;
  label: string;
  selected?: boolean;
  collapsed?: boolean;
  href?: string;
  onClick?: (e: React.MouseEvent<HTMLAnchorElement | HTMLButtonElement>) => void;
  className?: string;
}

export const NavItem: React.FC<NavItemProps> = ({
  icon,
  label,
  selected = false,
  collapsed = false,
  href,
  onClick,
  className = '',
  ...rest
}) => {
  injectOnce('li-navitem-styles', CSS);

  const classes = [
    'li-navitem',
    collapsed ? 'li-navitem--collapsed' : '',
    selected ? 'li-navitem--selected' : '',
    className,
  ].filter(Boolean).join(' ');

  const content = (
    <>
      <span className="material-icons">{icon}</span>
      <span className="li-navitem__label">{label}</span>
    </>
  );

  if (href) {
    return (
      <a
        className={classes}
        href={href}
        onClick={onClick as React.MouseEventHandler<HTMLAnchorElement>}
        aria-current={selected ? 'page' : undefined}
        {...rest}
      >
        {content}
      </a>
    );
  }

  return (
    <button
      type="button"
      className={classes}
      onClick={onClick as React.MouseEventHandler<HTMLButtonElement>}
      aria-current={selected ? 'page' : undefined}
      {...rest}
    >
      {content}
    </button>
  );
};
