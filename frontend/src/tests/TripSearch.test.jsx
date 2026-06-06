/**
 * TripSearch — ⌘K modal for searching and managing saved trips.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { renderWithProviders } from './testUtils';
import TripSearch from '../pages/ChatPage/TripSearch';

const MOCK_CHATS = [
  { id: 1, title: 'Trip to Denver', messages: [] },
  { id: 2, title: 'Trip to Austin', messages: [] },
  { id: 3, title: 'Trip to Seattle', messages: [] },
];

function renderTripSearch(overrides = {}) {
  const defaults = {
    chats: MOCK_CHATS,
    onSelect: vi.fn(),
    onDelete: vi.fn(),
    onClose: vi.fn(),
    selectedChatId: 1,
    getChatInfo: () => ({ step: 1, startCity: null, endCity: null }),
    isFetchingChats: false,
  };
  return renderWithProviders(<TripSearch {...defaults} {...overrides} />);
}

describe('TripSearch', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the search input', () => {
    renderTripSearch();
    expect(screen.getByPlaceholderText(/search trips/i)).toBeInTheDocument();
  });

  it('lists all chats initially', () => {
    renderTripSearch();
    expect(screen.getByText('Denver')).toBeInTheDocument();
    expect(screen.getByText('Austin')).toBeInTheDocument();
    expect(screen.getByText('Seattle')).toBeInTheDocument();
  });

  it('filters results as the user types', async () => {
    const user = userEvent.setup();
    renderTripSearch();
    await user.type(screen.getByPlaceholderText(/search trips/i), 'Den');
    expect(screen.getByText('Denver')).toBeInTheDocument();
    expect(screen.queryByText('Austin')).not.toBeInTheDocument();
    expect(screen.queryByText('Seattle')).not.toBeInTheDocument();
  });

  it('shows "No trips found" when nothing matches', async () => {
    const user = userEvent.setup();
    renderTripSearch();
    await user.type(screen.getByPlaceholderText(/search trips/i), 'zzz');
    expect(screen.getByText(/no trips found/i)).toBeInTheDocument();
  });

  it('calls onSelect when a result is clicked', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderTripSearch({ onSelect });
    await user.click(screen.getByText('Austin'));
    expect(onSelect).toHaveBeenCalledWith(MOCK_CHATS[1]);
  });

  it('calls onDelete with the correct chatId on delete button click', async () => {
    const onDelete = vi.fn();
    const user = userEvent.setup();
    renderTripSearch({ onDelete });
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
    await user.click(deleteButtons[1]); // second result = Austin
    expect(onDelete).toHaveBeenCalledWith(2);
  });

  it('calls onClose when the backdrop is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderTripSearch({ onClose });
    // The backdrop is the outer Box; clicking outside the modal
    const backdrop = document.querySelector('.ts-backdrop');
    await user.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when Escape is pressed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderTripSearch({ onClose });
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('shows "Loading previous trips…" when isFetchingChats is true', () => {
    renderTripSearch({ isFetchingChats: true });
    expect(screen.getByText(/loading previous trips/i)).toBeInTheDocument();
  });
});
