const mongoose = require('mongoose');

const messageSchema = new mongoose.Schema({
  role: { type: String, enum: ['user', 'assistant'] },
  content: String,
  timestamp: { type: Date, default: Date.now }
});

const conversationSchema = new mongoose.Schema({
  user_id: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
  messages: [messageSchema],
  language: { type: String, default: 'en' },
  context: { type: Object, default: {} },
  updated_at: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Conversation', conversationSchema);
