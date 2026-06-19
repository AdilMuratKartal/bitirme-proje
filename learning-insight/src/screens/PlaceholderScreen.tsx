import React from 'react';
import { Card, Button } from '../components';
import certificateBadges from '../assets/assets/certificate_badges.png';
import learningPathImg from '../assets/assets/learning_path.png';

interface PlaceholderScreenProps {
  page: string;
  onNavigate: (page: string) => void;
}

const PH: Record<string, { icon: string; title: string; img: string | null; body: string }> = {
  certificates: {
    icon: 'workspace_premium',
    title: 'Sertifika ve Rozetlerim',
    img: certificateBadges,
    body: 'Kazanılan sertifikalar ve rozetler burada listelenir. Bu ekran henüz orijinal kod tabanında tasarlanmamıştı.',
  },
  learning: {
    icon: 'route',
    title: 'Öğrenme Patikası',
    img: learningPathImg,
    body: 'Önerilen sıradaki modüller ve öğrenme patikan. Bu ekran henüz orijinal kod tabanında tasarlanmamıştı.',
  },
  account: {
    icon: 'manage_accounts',
    title: 'Hesabım',
    img: null,
    body: 'Profil ve hesap ayarları. Bu ekran tasarım önerisi olarak bırakılmıştır.',
  },
};

export const PlaceholderScreen: React.FC<PlaceholderScreenProps> = ({ page, onNavigate }) => {
  const d = PH[page] || PH.account;
  
  return (
    <div className="li-page">
      <div className="li-page__head">
        <h1>{d.title}</h1>
      </div>
      <Card className="li-placeholder" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '16px', padding: '48px' }}>
        <span className="material-icons li-placeholder__icon" style={{ fontSize: '52px', color: 'var(--brand-sky)' }}>{d.icon}</span>
        {d.img ? (
          <div className="li-imgwrap" style={{ maxWidth: 360, margin: '0 auto' }}>
            <img src={d.img} alt={d.title} style={{ maxWidth: '100%', height: 'auto' }} />
          </div>
        ) : null}
        <p style={{ color: 'var(--text-secondary)', maxWidth: 440, lineHeight: 1.55 }}>{d.body}</p>
        <Button
          variant="secondary"
          startIcon={<span className="material-icons">arrow_back</span>}
          onClick={() => onNavigate('home')}
          style={{ alignSelf: 'center' }}
        >
          Panele dön
        </Button>
      </Card>
    </div>
  );
};
