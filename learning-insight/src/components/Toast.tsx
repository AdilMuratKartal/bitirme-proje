import React, { useEffect } from 'react';
import { injectOnce } from './inject';

const CSS = `
.li-toast {
  position: fixed;
  bottom: 80px;
  right: 20px;
  z-index: var(--z-toast);
  background: var(--warning-bg);
  border-left: 4px solid var(--warning);
  color: var(--gold-600);
  padding: 12px 18px;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-lg);
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 500;
  max-width: 320px;
  box-sizing: border-box;
  animation: li-toast-in 0.3s cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
.li-toast__icon {
  color: var(--warning);
  font-size: 20px;
  flex-shrink: 0;
}
.li-toast__close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  margin-left: auto;
  color: var(--neutral-500);
  display: flex;
  align-items: center;
  transition: color var(--dur-fast);
}
.li-toast__close:hover {
  color: var(--text-primary);
}
@keyframes li-toast-in {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
`;

export interface ToastProps {
  message: string;
  show: boolean;
  onClose: () => void;
  durationMs?: number;
}

export const Toast: React.FC<ToastProps> = ({ message, show, onClose, durationMs = 6000 }) => {
  injectOnce('li-toast-styles', CSS);

  useEffect(() => {
    if (show && durationMs > 0) {
      const timer = setTimeout(() => {
        onClose();
      }, durationMs);
      return () => clearTimeout(timer);
    }
  }, [show, durationMs, onClose]);

  if (!show) return null;

  return (
    <div className="li-toast">
      <span className="material-icons li-toast__icon">warning</span>
      <span>{message}</span>
      <button className="li-toast__close" onClick={onClose} aria-label="Kapat">
        <span className="material-icons" style={{ fontSize: '18px' }}>close</span>
      </button>
    </div>
  );
};
export default Toast;
