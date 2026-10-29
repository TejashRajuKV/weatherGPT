const router = require('express').Router();
const axios = require('axios');

// GET /api/climate/history?location=&from=&to=
router.get('/history', async (req, res) => {
  try {
    const { location, from, to, lat, lon } = req.query;
    const response = await axios.get(`${process.env.DATA_SERVICE_URL}/climate/history`, {
      params: { location, from, to, lat, lon }
    });
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
