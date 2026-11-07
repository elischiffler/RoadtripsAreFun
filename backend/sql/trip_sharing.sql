-- Additive, explicit migration. No startup DDL; review/apply to an approved target.
-- Existing chats remain owner-only. Never copy trips into a recipient's chats.
CREATE TABLE IF NOT EXISTS trip_shares (
    id UUID PRIMARY KEY,
    owner_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    token_digest TEXT UNIQUE CHECK (token_digest IS NULL OR token_digest ~ '^[0-9a-f]{64}$'),
    link_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, chat_id),
    FOREIGN KEY (owner_id, chat_id) REFERENCES chats(user_id, chat_id) ON DELETE CASCADE,
    CHECK ((token_digest IS NULL) = (link_expires_at IS NULL))
);
CREATE TABLE IF NOT EXISTS trip_share_members (
    id UUID PRIMARY KEY,
    share_id UUID NOT NULL REFERENCES trip_shares(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL,
    display_name TEXT NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 80),
    connected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (share_id, account_id)
);
CREATE INDEX IF NOT EXISTS trip_share_members_account ON trip_share_members(account_id, share_id);
