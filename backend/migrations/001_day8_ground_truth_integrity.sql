BEGIN;

DELETE FROM dialogue_ground_truths older
USING dialogue_ground_truths newer
WHERE older.asset_id = newer.asset_id
  AND older.region_id = newer.region_id
  AND (
    older.created_at < newer.created_at
    OR (
      older.created_at = newer.created_at
      AND older.id < newer.id
    )
  );

ALTER TABLE dialogue_ground_truths
DROP CONSTRAINT IF EXISTS uq_dialogue_ground_truth_asset_region;

ALTER TABLE dialogue_ground_truths
ADD CONSTRAINT uq_dialogue_ground_truth_asset_region
UNIQUE (asset_id, region_id);

ALTER TABLE dialogue_ground_truths
DROP CONSTRAINT IF EXISTS dialogue_ground_truths_asset_id_fkey;

ALTER TABLE dialogue_ground_truths
ADD CONSTRAINT dialogue_ground_truths_asset_id_fkey
FOREIGN KEY (asset_id)
REFERENCES assets(id)
ON DELETE CASCADE;

COMMIT;
