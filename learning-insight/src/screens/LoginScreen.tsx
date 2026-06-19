import React, { useState } from 'react';
import { signInWithEmailAndPassword } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { Input, Button } from '../components';

interface LoginScreenProps {
  onLogin: () => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onLogin }) => {
  const [show, setShow] = useState(false);
  const [username, setUsername] = useState('busra.kirencioglu');
  const [password, setPassword] = useState('moodle123');
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | undefined>(undefined);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorText(undefined);

    const email = username.includes('@') ? username : `${username}@learninginsight.com`;

    try {
      await signInWithEmailAndPassword(auth, email, password);
      onLogin();
    } catch (err: any) {
      console.error("Giriş hatası:", err);
      if (err.code === 'auth/invalid-credential' || err.code === 'auth/wrong-password' || err.code === 'auth/user-not-found') {
        setErrorText('Kullanıcı adı veya şifre hatalı.');
      } else if (err.code === 'auth/invalid-email') {
        setErrorText('Geçersiz e-posta veya kullanıcı adı formatı.');
      } else {
        setErrorText('Kimlik doğrulama başarısız oldu.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="li-login">
      <div className="li-login__panel">
        <div className="li-login__brand">
          <span className="li-logo li-logo--lg">
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
        </div>
        <form className="li-login__form" onSubmit={handleSubmit}>
          <Input
            label="Kullanıcı Adınızı Giriniz"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={loading}
            endIcon={<span className="material-icons">account_circle</span>}
          />
          <Input
            label="Şifrenizi Giriniz"
            type={show ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading}
            error={!!errorText}
            helperText={errorText}
            endIcon={
              <span
                className="material-icons"
                style={{ cursor: 'pointer', userSelect: 'none' }}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShow((s) => !s);
                }}
              >
                {show ? 'visibility' : 'visibility_off'}
              </span>
            }
          />
          <Button type="submit" variant="primary" block disabled={loading}>
            {loading ? 'Giriş Yapılıyor...' : 'Giriş Yapınız'}
          </Button>
          <div className="li-login__links">
            <a href="#" onClick={(e) => e.preventDefault()}>
              Şifremi Unuttum
            </a>
            <a href="#" onClick={(e) => e.preventDefault()}>
              Kaydol <span className="material-icons">person_add</span>
            </a>
          </div>
        </form>
      </div>
      <div className="li-login__aside">
        <div className="li-login__aside-inner">
          <h2>Öğrenme verilerin, tek bir panelde.</h2>
          <p>Moodle’daki ilerlemeni analiz et, güçlü ve zayıf yönlerini gör, kişisel önerilerle çalış.</p>
        </div>
      </div>
    </div>
  );
};
