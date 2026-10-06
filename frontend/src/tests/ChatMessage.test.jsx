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
  it('omits requests already handled by active location controls and preserves other asks', () => {
    const message = {
      sender: 'bot',
      text: 'fallback',
      presentation: {
        ...presentation,
        needed: [
          'Starting location: Confirm Boulder, Colorado.',
          'Destination: Confirm Minneapolis, Minnesota.',
          'What date would you like to leave?',
        ],
      },
    };
    render(
      <ChatMessage
        message={message}
        pendingLocationFields={['start_address', 'destination_address']}
      />
    );
    expect(screen.queryByText(/Starting location: Confirm/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Destination: Confirm/)).not.toBeInTheDocument();
    expect(screen.getByText('What date would you like to leave?')).toBeInTheDocument();
    expect(screen.getByText('Attraction stops: 6')).toBeInTheDocument();
    expect(message.presentation.needed).toHaveLength(3);
  });

  it('omits an empty location-only reply without falling back to duplicate text', () => {
    const { container } = render(
      <ChatMessage
        message={{
          sender: 'bot',
          text: 'Starting location: Confirm Boulder.',
          presentation: {
            ...presentation,
            updated: [],
            needed: ['Starting location: Confirm Boulder.'],
          },
        }}
        pendingLocationFields={['start_address']}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

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
  it('renders introduction, independent asks and optional questions after a JSON reload', () => {
    const message = JSON.parse(
      JSON.stringify({
        sender: 'bot',
        text: 'duplicate fallback',
        presentation: {
          ...presentation,
          updated: [],
          introduction: 'A few details remain.',
          needed: [
            'What time would you like to leave? You can choose 9:00 AM.',
            'Would you like to provide a car, or skip it?',
          ],
          questions: ['Which evening interests would you like suggestions for (optional)?'],
        },
      })
    );
    render(<ChatMessage message={message} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByText('A few details remain.')).toBeInTheDocument();
    expect(screen.queryByText('duplicate fallback')).not.toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Questions' })).getAllByRole('listitem')
    ).toHaveLength(1);
  });

  it.each([{ introduction: {} }, { questions: [42] }])(
    'falls back for malformed new sections',
    (extra) => {
      render(
        <ChatMessage
          message={{
            sender: 'bot',
            text: 'Safe old reply',
            presentation: { ...presentation, ...extra },
          }}
        />
      );
      expect(screen.getByText('Safe old reply')).toBeInTheDocument();
      expect(screen.queryByRole('list')).not.toBeInTheDocument();
    }
  );
});
