import PropTypes from 'prop-types';
import LogoButton from '../../components/LogoButton';
import BrandLogo from '../../components/BrandLogo';
import '../../design/index.css';
import './AuthPage.css';

export default function AuthLayout({ title, children }) {
  return (
    <main className="rt-design auth-container">
      <section className="form-container" aria-labelledby="auth-title">
        <div className="auth-form-content">
          <header className="form-header">
            <LogoButton wordmark />
            <h1 id="auth-title">{title}</h1>
          </header>
          {children}
        </div>
      </section>
      <aside className="auth-landscape" aria-hidden="true">
        <svg className="auth-landscape__route" viewBox="0 0 400 600" fill="none">
          <path d="M-30 120c110-90 150 80 270 30s230 130 50 160-240 100-140 170 70 160 70 160" />
          <path d="M-70 50c160-80 190 110 310 40S530 270 330 350 80 390 140 470" />
          <path
            className="auth-landscape__journey"
            d="M70 510c-60-160 240-130 240-250 0-80-150-40-150-140"
          />
          <circle cx="70" cy="510" r="8" />
          <circle cx="160" cy="120" r="8" />
        </svg>
        <BrandLogo decorative />
      </aside>
    </main>
  );
}
AuthLayout.propTypes = { title: PropTypes.string.isRequired, children: PropTypes.node };
