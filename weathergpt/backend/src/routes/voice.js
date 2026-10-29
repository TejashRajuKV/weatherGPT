const router = require('express').Router();
const axios = require('axios');
const auth = require('../middleware/auth');

// POST /api/voice/transcribe - audio to text
router.post('/transcribe', auth, async (req, res) => {
  try {
    const response = await axios.post(`${process.env.AI_SERVICE_URL}/voice/transcribe`, req.body);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/voice/speak - text to speech
router.post('/speak', auth, async (req, res) => {
  try {
    const response = await axios.post(`${process.env.AI_SERVICE_URL}/voice/speak`, req.body);
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
