import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import ChatMessage from '../pages/ChatPage/ChatMessage';

const presentation = {
  title: 'Updated trip details',
  updated: ['Attraction stops: 6', 'Hotel budget: $200 per night'],
  needed: ['What date would you like to leave?'],
  notes: [],
};

describe('ChatMessage', () => {
  it('renders labeled native lists instead of duplicate fallback text', () => {
    render(<ChatMessage message={{ sender: 'bot', text: 'fallback', presentation }} />);
    expect(screen.queryByText('fallback')).not.toBeInTheDocument();
    expect(screen.getAllByRole('list')).toHaveLength(2);
    expect(
      within(screen.getByRole('region', { name: 'Updated trip details' })).getAllByRole('listitem')
    ).toHaveLength(2);
    expect(screen.getByText('What date would you like to leave?')).toBeInTheDocument();
  });

  it('omits empty receipts and safely escapes arbitrary saved text', () => {
    render(
      <ChatMessage
        message={{
          sender: 'bot',
          text: 'fallback',
          presentation: {
            ...presentation,
            updated: [],
            needed: ['<img src=x onerror=alert(1)>'],
            notes: ['Retry later.'],
          },
        }}
      />
    );
    expect(screen.queryByText('Updated trip details')).not.toBeInTheDocument();
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText('Retry later.')).toBeInTheDocument();
  });

  it.each([undefined, { updated: 'bad' }])(
    'renders old or malformed messages as plain text',
    (value) => {
      render(
        <ChatMessage message={{ sender: 'bot', text: 'Old saved reply', presentation: value }} />
      );
      expect(screen.getByText('Old saved reply')).toBeInTheDocument();
    }
  );
});
