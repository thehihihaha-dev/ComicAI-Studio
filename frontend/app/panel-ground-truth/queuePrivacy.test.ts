import assert from "node:assert/strict";
import test from "node:test";
import { sanitizeQueue } from "./queuePrivacy.ts";

test("queue sanitizer strips every prediction-derived field", () => {
  const sanitized = sanitizeQueue({ checkpoint:"12.4", cohort:"12.4-unseen", total:6, verified:0, pending:6,
    items:[{review_id:"r",page_order:3,source_hash:"h",state:"PENDING",revision:0,source_compatible:true,
      image_dimensions:{width:900,height:1280},human_panels:[],image_url:"/image",
      candidates:[1],selected_panels:[1],detected_panel_count:4,ambiguous_panel_count:2,unresolved:true,
      confidence:0.9,iou:1,rejection_reasons:["x"],expected_panel_count:4}] });
  const encoded=JSON.stringify(sanitized);
  for(const forbidden of ["candidates","selected_panels","detected_panel_count","ambiguous_panel_count",
    "unresolved","confidence","iou","rejection_reasons","expected_panel_count"]){
    assert.equal(encoded.includes(forbidden),false);
  }
  assert.equal(sanitized.items.length,1); assert.equal(sanitized.total,6);
});
