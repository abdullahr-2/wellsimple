// Inference for the exported sklearn histogram gradient-boosted binary classifier.
// A numeric node is a leaf; split nodes carry the original threshold and missing-value branch.
function repairProbability(model, features) {
  let logOdds = model.base;
  for (const tree of model.trees) {
    let node = tree[0];
    while (Array.isArray(node)) {
      const [feature, threshold, left, right, missingLeft] = node;
      const value = features[feature];
      const goLeft = value == null ? missingLeft : threshold == null || value <= threshold;
      node = tree[goLeft ? left : right];
    }
    logOdds += node;
  }
  return 1 / (1 + Math.exp(-logOdds));
}

async function scoreHostedWells(query) {
  const [model, fleet] = await Promise.all([api('/api/model'), api('/api/model/inputs?' + query)]);
  const ranked = [];
  let highRisk = 0;
  for (const [well, features, visible] of fleet.rows) {
    const p = repairProbability(model, features);
    if (p >= 0.4) highRisk++;
    if (!visible || p < Number(query.get('min_risk'))) continue;
    const rad = Math.PI / 180, lat = well.surface_latitude, lon = well.surface_longitude;
    const [lat0, lon0] = fleet.origin;
    const h = Math.sin((lat - lat0) * rad / 2) ** 2 +
      Math.cos(lat * rad) * Math.cos(lat0 * rad) * Math.sin((lon - lon0) * rad / 2) ** 2;
    ranked.push({...well, p_repair: p, expected_loss_low: p * well.event_cost_low,
      expected_loss_mid: p * well.event_cost_mid,
      distance_km: lat == null || lon == null ? null : 12742.0176 * Math.asin(Math.sqrt(Math.min(1, h)))});
  }
  ranked.sort((a, b) => b.p_repair - a.p_repair);
  return {scored_wells: fleet.rows.length, high_risk_wells: highRisk, wells: ranked.slice(0, Number(query.get('limit')))};
}
