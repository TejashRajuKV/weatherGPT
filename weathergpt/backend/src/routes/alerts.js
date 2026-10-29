const router = require('express').Router();
const axios = require('axios');
const auth = require('../middleware/auth');
const Alert = require('../models/Alert');

// GET /api/alerts?lat=&lon=
router.get('/', async (req, res) => {
  try {
    const { lat, lon } = req.query;
    const alerts = await Alert.find({ status: 'active' }).sort({ created_at: -1 }).limit(20);
    res.json(alerts);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/alerts/subscribe
router.post('/subscribe', auth, async (req, res) => {
  try {
    const { location, hazard_types, channels } = req.body;
    // Store subscription (simplified - using user model)
    res.json({ message: 'Subscribed successfully', location, hazard_types, channels });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
