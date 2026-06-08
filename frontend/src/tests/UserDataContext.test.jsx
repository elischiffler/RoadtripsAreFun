/**
 * UserDataContext — tests for the Data / ChatLogs / ChatData class layer
 * and the React context provider.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React, { useContext } from 'react';
import {
  UserDataProvider,
  UserDataContext,
  Data,
  ChatLogs,
  ChatData,
} from '../states/UserDataContext';

// ─── Data / ChatLogs / ChatData class tests ──────────────────────────────────

describe('ChatLogs', () => {
  it('starts empty', () => {
    const logs = new ChatLogs();
    expect(logs.chatdata).toHaveLength(0);
    expect(logs.currentId).toBe(1);
  });

  it('createChatData adds a new ChatData instance', () => {
    const logs = new ChatLogs();
    const cd = logs.createChatData(42);
    expect(cd).toBeInstanceOf(ChatData);
    expect(cd.chatId).toBe(42);
    expect(logs.chatdata).toHaveLength(1);
  });

  it('createChatData replaces an existing entry with the same id', () => {
    const logs = new ChatLogs();
    logs.createChatData(1);
    logs.createChatData(1); // replace
    expect(logs.chatdata).toHaveLength(1);
  });

  it('getChatDataById returns the correct entry', () => {
    const logs = new ChatLogs();
    logs.createChatData(5);
    logs.createChatData(10);
    const found = logs.getChatDataById(10);
    expect(found.chatId).toBe(10);
  });

  it('getChatDataById returns undefined for a missing id', () => {
    const logs = new ChatLogs();
    expect(logs.getChatDataById(99)).toBeUndefined();
  });

  it('removeChatData removes the correct entry', () => {
    const logs = new ChatLogs();
    logs.createChatData(1);
    logs.createChatData(2);
    logs.removeChatData(1);
    expect(logs.chatdata).toHaveLength(1);
    expect(logs.chatdata[0].chatId).toBe(2);
  });
});

describe('ChatData defaults', () => {
  it('initialises with sensible defaults', () => {
    const cd = new ChatData(7);
    expect(cd.chatId).toBe(7);
    expect(cd.route).toBeNull();
    expect(cd.itinerary).toBeNull();
    expect(cd.stops).toBe(1);
    expect(cd.isComplete).toBe(false);
    expect(cd.carDetails).toEqual(['', '', '']);
  });
});

// ─── Context provider ────────────────────────────────────────────────────────

describe('UserDataContext provider', () => {
  const wrapper = ({ children }) => <UserDataProvider>{children}</UserDataProvider>;

  it('provides UserData, chats, and currentStep', () => {
    const { result } = renderHook(() => useContext(UserDataContext), { wrapper });
    expect(result.current.UserData).toBeInstanceOf(Data);
    expect(result.current.chats).toEqual([]);
    expect(result.current.currentStep).toBe(1);
  });

  it('setChats updates the chats array', () => {
    const { result } = renderHook(() => useContext(UserDataContext), { wrapper });
    act(() => {
      result.current.setChats([{ id: 1, title: 'Test Trip', messages: [] }]);
    });
    expect(result.current.chats).toHaveLength(1);
    expect(result.current.chats[0].title).toBe('Test Trip');
  });

  it('setCurrentStep updates step', () => {
    const { result } = renderHook(() => useContext(UserDataContext), { wrapper });
    act(() => result.current.setCurrentStep(3));
    expect(result.current.currentStep).toBe(3);
  });
});
