import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import LogoButton from '../components/LogoButton';

function LocationProbe() {
  const { pathname } = useLocation();
  return <output aria-label="Current route">{pathname}</output>;
}

function renderLogo() {
  return render(
    <MemoryRouter initialEntries={['/trips']}>
      <LogoButton />
      <LocationProbe />
    </MemoryRouter>
  );
}

describe('route-pin home control', () => {
  it('shares the favicon vector and exposes one accessible name', () => {
    renderLogo();
    const home = screen.getByRole('button', { name: 'RoadtripsAreFun home' });
    expect(home).toHaveAttribute('type', 'button');
    const mark = home.querySelector('img');
    expect(mark).toHaveAttribute('src', '/favicon.svg');
    expect(mark).toHaveAttribute('alt', '');
    expect(mark).toHaveAttribute('aria-hidden', 'true');
    expect(mark).toHaveAttribute('width', '40');
    expect(mark).toHaveAttribute('height', '40');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('returns home on repeated pointer activation', async () => {
    const user = userEvent.setup();
    renderLogo();
    const home = screen.getByRole('button', { name: 'RoadtripsAreFun home' });
    await user.click(home);
    await user.click(home);
    expect(screen.getByLabelText('Current route')).toHaveTextContent(/^\/$/);
  });

  it.each(['{Enter}', ' '])('returns home with the %s key', async (key) => {
    const user = userEvent.setup();
    renderLogo();
    await user.tab();
    expect(screen.getByRole('button', { name: 'RoadtripsAreFun home' })).toHaveFocus();
    await user.keyboard(key);
    expect(screen.getByLabelText('Current route')).toHaveTextContent(/^\/$/);
  });
});
