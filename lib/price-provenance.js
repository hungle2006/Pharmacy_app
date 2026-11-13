'use strict';

// Legacy imports and the current source reuse numeric DAV IDs. An ID alone is
// not proof that a legacy price belongs to the current Silver product. Keep the
// original rows in Gold, but do not serve this known ambiguous cross-source join.
function compatiblePriceSource(product='d',price='p') {
  return `NOT (COALESCE(${product}.source,'')='SILVER_R2' AND COALESCE(${price}.source,'')='DAV_PUBLIC_DRUG_PRICE')`;
}
module.exports={compatiblePriceSource};
