import React from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-field{display:flex;flex-direction:column;gap:6px;font-family:var(--font-sans);}
.li-field__label{font-size:var(--text-sm);font-weight:var(--weight-medium);color:var(--text-primary);text-align:left;}
.li-field__req{color:var(--danger);margin-left:2px;}
.li-field__wrap{display:flex;align-items:center;gap:8px;background:var(--surface-card);border:1px solid var(--border-default);border-radius:var(--radius-sm);padding:0 12px;height:44px;transition:border-color var(--dur-fast),box-shadow var(--dur-fast);}
.li-field__wrap:focus-within{border-color:var(--primary);box-shadow:0 0 0 3px var(--focus-ring);}
.li-field__input{flex:1;border:none;outline:none;background:transparent;font-family:inherit;font-size:var(--text-base);color:var(--text-primary);min-width:0;}
.li-field__input::placeholder{color:var(--text-disabled);}
.li-field__icon{display:inline-flex;color:var(--text-secondary);font-size:20px;flex-shrink:0;}
.li-field__help{font-size:var(--text-xs);color:var(--text-secondary);text-align:left;}
.li-field--error .li-field__wrap{border-color:var(--danger);}
.li-field--error .li-field__wrap:focus-within{box-shadow:0 0 0 3px var(--danger-bg);}
.li-field--error .li-field__help{color:var(--danger);}
.li-field--disabled .li-field__wrap{background:var(--neutral-100);border-color:var(--border-subtle);}
.li-field--disabled .li-field__input{color:var(--text-disabled);cursor:not-allowed;}
`;

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  required?: boolean;
  helperText?: string;
  error?: boolean;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  required = false,
  helperText,
  error = false,
  startIcon = null,
  endIcon = null,
  disabled = false,
  id,
  className = '',
  ...rest
}) => {
  injectOnce('li-input-styles', CSS);

  const fieldId = id || (label ? `li-${String(label).replace(/\s+/g, '-').toLowerCase()}` : undefined);
  const classes = [
    'li-field',
    error ? 'li-field--error' : '',
    disabled ? 'li-field--disabled' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      {label ? (
        <label className="li-field__label" htmlFor={fieldId}>
          {label}
          {required ? <span className="li-field__req">*</span> : null}
        </label>
      ) : null}
      <div className="li-field__wrap">
        {startIcon ? <span className="li-field__icon">{startIcon}</span> : null}
        <input id={fieldId} className="li-field__input" disabled={disabled} {...rest} />
        {endIcon ? <span className="li-field__icon">{endIcon}</span> : null}
      </div>
      {helperText ? <span className="li-field__help">{helperText}</span> : null}
    </div>
  );
};
