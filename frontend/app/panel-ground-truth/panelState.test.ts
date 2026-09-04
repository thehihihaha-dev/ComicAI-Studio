import assert from "node:assert/strict";
import test from "node:test";
import {
  deletedBox,
  drawnBox,
  movedBox,
  navigatedIndex,
  pointerToSource,
  renderedImageRect,
  resizedBox,
  sourceBoxToDisplay,
  toggledAmbiguity,
  type PanelBox,
} from "./panelState";

const box: PanelBox = {
  panel_id: "human-1",
  bbox: [10, 20, 110, 120],
  ambiguous: false,
};
test("temporary drawing normalizes drag direction", () =>
  assert.deepEqual(drawnBox([100, 90], [10, 20]), [10, 20, 100, 90]));
test("move clamps bbox inside image", () =>
  assert.deepEqual(movedBox(box.bbox, -50, 500, 200, 200), [0, 100, 100, 200]));
test("resize adjusts selected corner", () =>
  assert.deepEqual(resizedBox(box.bbox, "rb", [150, 170]), [10, 20, 150, 170]));
test("delete and ambiguity are isolated state operations", () => {
  const second: PanelBox = {
    panel_id: "human-2",
    bbox: [1, 1, 5, 5],
    ambiguous: false,
  };
  assert.equal(
    toggledAmbiguity([box, second], box.panel_id)[0].ambiguous,
    true,
  );
  assert.deepEqual(deletedBox([box, second], box.panel_id), [second]);
});
test("navigation stays within six-page queue", () => {
  assert.equal(navigatedIndex(0, -1, 6), 0);
  assert.equal(navigatedIndex(0, 1, 6), 1);
  assert.equal(navigatedIndex(5, 1, 6), 5);
});
test("object-contain mapping removes horizontal letterbox", () => {
  const surface = { width: 900, height: 570 },
    source = { width: 900, height: 1280 };
  assert.deepEqual(renderedImageRect(surface, source), {
    left: 249.609375,
    top: 0,
    width: 400.78125,
    height: 570,
  });
  assert.deepEqual(pointerToSource([249.609375, 0], surface, source), [0, 0]);
  assert.deepEqual(
    pointerToSource([650.390625, 570], surface, source),
    [900, 1280],
  );
});
test("pointer outside rendered image is rejected", () => {
  const surface = { width: 900, height: 570 },
    source = { width: 900, height: 1280 };
  assert.equal(pointerToSource([200, 200], surface, source), null);
  assert.equal(pointerToSource([700, 200], surface, source), null);
});
test("source-display transform round trips and survives resize", () => {
  const source = { width: 900, height: 1280 },
    bbox: PanelBox["bbox"] = [72, 92, 821, 1190];
  for (const surface of [
    { width: 900, height: 570 },
    { width: 1200, height: 800 },
    { width: 400, height: 700 },
  ]) {
    const displayed = sourceBoxToDisplay(bbox, surface, source);
    assert.deepEqual(
      pointerToSource([displayed[0], displayed[1]], surface, source),
      [bbox[0], bbox[1]],
    );
    assert.deepEqual(
      pointerToSource([displayed[2], displayed[3]], surface, source),
      [bbox[2], bbox[3]],
    );
  }
});
