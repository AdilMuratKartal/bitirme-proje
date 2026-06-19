import React, { useState } from 'react';
import { IconButton, Badge, Avatar } from './index';
import { studentProfile } from '../data/mockData';

interface HeaderProps {
  onToggleSidebar: () => void;
  onNavigate: (page: string) => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar, onNavigate }) => {
  const [searching, setSearching] = useState(false);
  const [menu, setMenu] = useState<'lang' | 'profile' | null>(null);

  const handleLogoClick = (e: React.MouseEvent) => {
    e.preventDefault();
    onNavigate('home');
  };

  return (
    <header className="li-header">
      <div className="li-header__left">
        <IconButton aria-label="Menü" tone="onNav" onClick={onToggleSidebar}>
          <span className="material-icons">menu</span>
        </IconButton>
        <a className="li-header__logo" href="#" onClick={handleLogoClick}>
          <span className="li-logo li-logo--reversed">
            <span className="li-logo__mark">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M3.5 15.5l4.5-4.5 3 3 6.5-7.5"
                  stroke="currentColor"
                  strokeWidth="2.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M14 6.5h4v4"
                  stroke="currentColor"
                  strokeWidth="2.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="3.5" cy="15.5" r="1.5" fill="currentColor" />
                <circle cx="8" cy="11" r="1.5" fill="currentColor" />
                <circle cx="11" cy="14" r="1.5" fill="currentColor" />
              </svg>
            </span>
            <span className="li-logo__text">
              <b>Learning</b>
              <i>Insight</i>
            </span>
          </span>
        </a>
      </div>

      <div className="li-header__right">
        <div className={`li-header__search ${searching ? 'is-open' : ''}`}>
          <IconButton aria-label="Ara" tone="onNav" onClick={() => setSearching((s) => !s)}>
            <span className="material-icons">{searching ? 'search_off' : 'search'}</span>
          </IconButton>
          <input className="li-header__search-input" placeholder="Kurs, ödev, sınav ara…" />
        </div>

        <Badge content={2} tone="danger">
          <IconButton aria-label="Bildirimler" tone="onNav">
            <span className="material-icons">notifications</span>
          </IconButton>
        </Badge>

        <div className="li-header__menuwrap">
          <IconButton aria-label="Dil" tone="onNav" onClick={() => setMenu(menu === 'lang' ? null : 'lang')}>
            <span className="material-icons">language</span>
          </IconButton>
          {menu === 'lang' && (
            <ul className="li-menu" onMouseLeave={() => setMenu(null)}>
              {['Türkçe', 'English', 'Deutsch', 'Français', '中文'].map((l) => (
                <li key={l} className="li-menu__item" onClick={() => setMenu(null)}>
                  {l}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="li-header__menuwrap">
          <button
            className="li-header__avatar"
            onClick={() => setMenu(menu === 'profile' ? null : 'profile')}
            aria-label="Profil"
          >
            <Avatar src={studentProfile.photo} name={studentProfile.name} size="sm" />
          </button>
          {menu === 'profile' && (
            <ul className="li-menu li-menu--right" onMouseLeave={() => setMenu(null)}>
              <li
                className="li-menu__item"
                onClick={() => {
                  setMenu(null);
                  onNavigate('account');
                }}
              >
                Profil
              </li>
              <li
                className="li-menu__item"
                onClick={() => {
                  setMenu(null);
                  onNavigate('account');
                }}
              >
                Hesabım
              </li>
              <li
                className="li-menu__item"
                onClick={() => {
                  setMenu(null);
                  onNavigate('lineage');
                }}
              >
                Veri Hattı
              </li>
              <li
                className="li-menu__item li-menu__item--danger"
                onClick={() => {
                  setMenu(null);
                  onNavigate('logout');
                }}
              >
                Çıkış Yap
              </li>
            </ul>
          )}
        </div>
      </div>
    </header>
  );
};
