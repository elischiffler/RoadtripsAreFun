-- Explicit destructive rollback for sharing metadata ONLY, after taking sharing
-- endpoints out of service and approving the target/backup. Never run at startup.
-- This revokes all links and connected memberships; it does not delete chats,
-- route_segments, steps, profiles, catalogs or any owner trip content.
DROP TABLE IF EXISTS trip_share_members;
DROP TABLE IF EXISTS trip_shares;
