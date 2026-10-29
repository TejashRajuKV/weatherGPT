const router = require('express').Router();
const axios = require('axios');
const auth = require('../middleware/auth');
const Conversation = require('../models/Conversation');

// POST /api/chat - send query, get AI response
router.post('/', auth, async (req, res) => {
  try {
    const { query, location, language, conversationId } = req.body;

    // Load or create conversation
    let conversation = conversationId
      ? await Conversation.findById(conversationId)
      : await Conversation.create({ user_id: req.user.id, language: language || 'en' });

    // Save user message
    conversation.messages.push({ role: 'user', content: query });

    // Call AI service
    const aiRes = await axios.post(`${process.env.AI_SERVICE_URL}/chat`, {
      query,
      location,
      language: language || conversation.language,
      history: conversation.messages.slice(-10)
    });

    const reply = aiRes.data.response;

    // Save assistant reply
    conversation.messages.push({ role: 'assistant', content: reply });
    conversation.updated_at = new Date();
    await conversation.save();

    res.json({ response: reply, conversationId: conversation._id });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/chat/history - get conversation list
router.get('/history', auth, async (req, res) => {
  try {
    const conversations = await Conversation.find({ user_id: req.user.id })
      .sort({ updated_at: -1 })
      .limit(20)
      .select('_id language updated_at messages');
    res.json(conversations);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
