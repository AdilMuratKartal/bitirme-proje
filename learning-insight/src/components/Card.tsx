import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-card{background:var(--surface-card);border-radius:var(--radius-md);box-shadow:var(--shadow-sm);padding:var(--space-4);color:var(--text-primary);display:flex;flex-direction:column;gap:var(--space-3);position:relative;transition:box-shadow var(--dur-base) var(--ease-standard),transform var(--dur-base) var(--ease-emphasis);text-align:left;}
.li-card--hover:hover{box-shadow:var(--shadow-hover);transform:translateY(-2px);}
.li-card--flat{box-shadow:none;border:1px solid var(--border-default);}
.li-card__head{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);}
.li-card__title{font-size:var(--text-xl);font-weight:var(--weight-semibold);line-height:var(--leading-snug);color:var(--text-primary);margin:0;text-align:left;}
.li-card__link{display:inline-flex;align-items:center;gap:2px;font-size:var(--text-sm);font-weight:var(--weight-semibold);color:var(--primary);text-decoration:none;white-space:nowrap;transition:transform var(--dur-fast);}
.li-card__link:hover{transform:translateX(2px);color:var(--primary-hover);}
.li-card__link .material-icons{font-size:20px;}
.li-card__body{display:flex;flex-direction:column;flex:1;min-height:0;}
`;

export interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: React.ReactNode;
  linkLabel?: string;
  linkHref?: string;
  onLinkClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
  hoverable?: boolean;
  flat?: boolean;
}

export const Card: React.FC<CardProps> = ({
  title,
  linkLabel,
  linkHref = '#',
  onLinkClick,
  hoverable = false,
  flat = false,
  className = '',
  style = {},
  children,
  ...rest
}) => {
  injectOnce('li-card-styles', CSS);

  const classes = [
    'li-card',
    hoverable ? 'li-card--hover' : '',
    flat ? 'li-card--flat' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <section className={classes} style={style} {...rest}>
      {title || linkLabel ? (
        <div className="li-card__head">
          {title ? (
            typeof title === 'string' ? (
              <h2 className="li-card__title">{title}</h2>
            ) : (
              title
            )
          ) : (
            <span></span>
          )}
          {linkLabel ? (
            <a className="li-card__link" href={linkHref} onClick={onLinkClick}>
              {linkLabel}
              <span className="material-icons">chevron_right</span>
            </a>
          ) : null}
        </div>
      ) : null}
      <div className="li-card__body">{children}</div>
    </section>
  );
};
