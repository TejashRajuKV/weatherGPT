const mongoose = require('mongoose');

const alertSchema = new mongoose.Schema({
  hazard_type: { type: String, required: true },
  severity: { type: String, enum: ['low', 'medium', 'high', 'extreme'], required: true },
  area: { type: Object }, // GeoJSON Polygon
  start: Date,
  end: Date,
  message: { type: String, required: true },
  source: String,
  status: { type: String, enum: ['draft', 'active', 'expired'], default: 'active' },
  created_at: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Alert', alertSchema);
