const mongoose = require('mongoose');

const userSchema = new mongoose.Schema({
  name: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  phone: String,
  language: { type: String, default: 'en' },
  preferred_locations: [String],
  role: { type: String, enum: ['public', 'farmer', 'admin', 'researcher'], default: 'public' },
  created_at: { type: Date, default: Date.now }
});

module.exports = mongoose.model('User', userSchema);
