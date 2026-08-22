BEGIN;
ALTER TABLE reader_logical_reviews ADD COLUMN IF NOT EXISTS human_ordered_region_ids JSON;
ALTER TABLE reader_logical_reviews ADD COLUMN IF NOT EXISTS human_excluded_region_ids JSON;
ALTER TABLE reader_logical_reviews ADD COLUMN IF NOT EXISTS human_transcriptions JSON NOT NULL DEFAULT '{}';
ALTER TABLE reader_logical_reviews ADD COLUMN IF NOT EXISTS human_representation_version VARCHAR NOT NULL DEFAULT 'click-dialogue-order.v2';
COMMIT;
